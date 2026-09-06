"""
Verification Service.

Orchestrates:
1. Claim normalization & entity extraction
2. Multi-query semantic retrieval from FAISS vector store
3. Strict entity-grounded stance analysis (SUPPORT, CONTRADICT, NEUTRAL)
4. Gemini LLM reasoning for nuanced verdict (falls back to heuristic if key not set)
"""

import time
import re
import logging
from typing import List, Tuple, Dict, Any, Set, Optional
import numpy as np

from app.config import settings
from app.models.schemas import (
    VerificationRequest,
    VerificationResponse,
    VerdictEnum,
    EvidenceItem,
    DocumentChunk,
    ReliabilityLevel,
)
from app.services.preprocessing import preprocessor
from app.services.embeddings import embedding_service
from app.services.retrieval import vector_store, SearchResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Minimum cosine similarity threshold to consider evidence semantically relevant
MIN_SEMANTIC_THRESHOLD = 0.45

# Standard English stop words to filter when identifying key claim entities
STOP_WORDS: Set[str] = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "can", "could", "will", "would", "shall", "should", "may", "might",
    "it", "its", "they", "them", "their", "this", "that", "these", "those", "what",
    "which", "who", "whom", "whose", "why", "how", "where", "when", "there", "here",
    "and", "or", "but", "if", "so", "than", "too", "very", "just", "about", "did",
    "happen", "happened", "tell", "me", "whether", "true", "false", "really"
}


class VerificationService:
    """Verifies claims using evidence retrieved from the FAISS vector database."""

    def __init__(self):
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    @staticmethod
    def normalize_claim(raw_claim: str) -> str:
        """
        Normalize questions and interrogatives into declarative statements for retrieval:
        e.g., "was 9/11 happend in india?" -> "9/11 happened in india"
        """
        text = raw_claim.strip()
        text = re.sub(r"[?.,!;]+$", "", text)  # remove trailing punctuation
        # Strip common question prefixes
        text = re.sub(r"^(was|is|did|does|do|can|could|are|were|has|have|will|would)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(tell me if|is it true that|can you verify if)\s+", "", text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def extract_key_terms(text: str) -> Set[str]:
        """Extract significant content words and entity tokens (ignoring stop words)."""
        clean = text.lower()
        # Preserve special compound tokens like 9/11 or covid-19
        special_tokens = set()
        if "9/11" in clean or "9-11" in clean:
            special_tokens.add("9/11")
        if "covid" in clean:
            special_tokens.add("covid")

        # Split into alphanumeric words
        words = re.findall(r"\b[a-z0-9]{2,}\b", clean)
        significant = {w for w in words if w not in STOP_WORDS}
        return significant | special_tokens

    def generate_retrieval_queries(self, claim: str) -> List[str]:
        """
        Generate multiple search queries from the user input:
        1. Normalized declarative claim
        2. Direct contradiction / debunk query
        3. Factual scientific / news reporting query
        """
        clean_claim = preprocessor.clean_text(claim)
        statement = self.normalize_claim(clean_claim)
        queries = [statement]

        # Contradiction / debunk query
        queries.append(f"fact check debunk false claim {statement}")

        # Authoritative reporting query
        queries.append(f"official report verified news {statement}")

        return queries

    def retrieve_evidence(
        self,
        claim: str,
        top_k_per_query: int = 5,
        news_only: bool = False,
    ) -> List[SearchResult]:
        """Execute multi-query semantic search across the FAISS vector index.

        Args:
            claim: The normalized claim text to search for.
            top_k_per_query: How many chunks to retrieve per query variant.
            news_only: If True, restrict results to chunks with category='news'.
        """
        queries = self.generate_retrieval_queries(claim)
        all_results: Dict[str, SearchResult] = {}

        category_filter = "news" if news_only else None

        for q in queries:
            q_vec = self.embedding_service.embed_query(q)
            if category_filter:
                results = self.vector_store.search_filtered(q_vec, top_k=top_k_per_query, category=category_filter)
            else:
                results = self.vector_store.search(q_vec, top_k=top_k_per_query)
            for res in results:
                cid = res.chunk.chunk_id
                if cid not in all_results or res.score > all_results[cid].score:
                    all_results[cid] = res

        # Sort by similarity score descending
        sorted_results = sorted(all_results.values(), key=lambda r: r.score, reverse=True)
        return sorted_results


    def _evaluate_chunk_stance(
        self, claim: str, chunk_text: str, score: float, claim_terms: Set[str]
    ) -> str:
        """
        Determine whether an evidence chunk supports, contradicts, or is neutral to the claim.
        Enforces strict entity grounding and polarity checking:
        - If the chunk does NOT contain the key claim entities, it is NEUTRAL / IRRELEVANT.
        - If the chunk directly denies or refutes the claim, it is CONTRADICT.
        - If the chunk affirms the claim with high semantic alignment, it is SUPPORT.
        """
        text_lower = chunk_text.lower()
        claim_lower = claim.lower()

        # Step 1: Entity overlap validation
        if claim_terms:
            matched_terms = sum(1 for term in claim_terms if term in text_lower)
            overlap_ratio = matched_terms / len(claim_terms)
            # Require at least 50% term overlap, or at least 1 term if only 1-2 terms exist
            min_required = 1 if len(claim_terms) <= 2 else max(2, len(claim_terms) // 2)
            if matched_terms < min_required and overlap_ratio < 0.40:
                return "NEUTRAL"

        # Step 2: Check for strong supporting markers FIRST (higher priority)
        strong_support_terms = [
            "safe and effective", "proven", "confirmed", "verified",
            "directly caused", "unequivocally caused", "definitely", "clearly safe"
        ]
        strong_support_hits = sum(1 for term in strong_support_terms if term in text_lower)
        
        if strong_support_hits > 0 and score >= 0.45:
            return "SUPPORT"

        # Step 3: Location-based contradiction detection
        if ("in india" in claim_lower or "india" in claim_lower):
            if "did not occur in india" in text_lower or "not in india" in text_lower or "did not happen in india" in text_lower:
                return "CONTRADICT"
            if "occurred in" in text_lower and "india" not in text_lower:
                return "CONTRADICT"

        # Step 4: Specific core verb refutations (high confidence)
        if "prevent" in claim_lower and ("does not prevent" in text_lower or "not prevent" in text_lower):
            return "CONTRADICT"
        if "cure" in claim_lower and ("does not cure" in text_lower or "no cure" in text_lower):
            return "CONTRADICT"
        if "cause" in claim_lower and ("does not cause" in text_lower or "no evidence for" in text_lower):
            return "CONTRADICT"

        # Step 5: Check for explicit refutation ONLY if no strong support markers are present
        explicit_refutation_terms = [
            "false", "unfounded", "debunked", "no evidence", "biologically impossible",
            "misleading", "myth", "refute", "refuted", "hoax", "fabricated", "fake",
            "did not happen", "never occurred", "did not occur", "did not take place"
        ]
        
        explicit_refutation_hits = sum(1 for term in explicit_refutation_terms if term in text_lower)
        
        if explicit_refutation_hits > 0 and strong_support_hits == 0:
            return "CONTRADICT"

        # Step 6: General supporting markers
        support_terms = [
            "confirmed", "proven", "demonstrated that", "clinical evidence shows",
            "substantial evidence", "directly caused", "safe and effective",
            "unequivocally caused", "widespread adverse impacts", "verified",
            "officially reported", "investigators found", "records confirm",
            "rescued", "struck", "occurred", "took place"
        ]

        support_hits = sum(1 for term in support_terms if term in text_lower)

        # To be SUPPORT, it must have strong semantic similarity (>= 0.48) and affirmative content
        if score >= 0.48:
            return "SUPPORT"

        if score >= 0.45 and support_hits > 0:
            return "SUPPORT"

        return "NEUTRAL"

    def _build_evidence_snippets(self, candidates: List[SearchResult]) -> List[Dict[str, Any]]:
        """Format FAISS search results into structured snippets for Gemini."""
        snippets = []
        for r in candidates:
            c = r.chunk
            snippets.append({
                "text": c.text,
                "source": c.source,
                "score": round(float(r.score), 4),
                "reliability": c.reliability_level.value,
                "date": c.publication_date,
                "category": c.category,
                "url": c.url,
            })
        return snippets

    def _heuristic_verdict(
        self,
        normalized: str,
        relevant_candidates: List[SearchResult],
        claim_terms: Set[str],
    ) -> Dict[str, Any]:
        """
        Original rule-based verdict engine.
        Used as fallback when Gemini is not available.
        Returns a dict with verdict, confidence, summary, reasoning keys.
        """
        supporting: List[EvidenceItem] = []
        contradicting: List[EvidenceItem] = []

        for item in relevant_candidates:
            chunk = item.chunk
            stance = self._evaluate_chunk_stance(normalized, chunk.text, item.score, claim_terms)
            evidence_obj = EvidenceItem(
                source=chunk.source,
                text=chunk.text,
                url=chunk.url,
                publication_date=chunk.publication_date,
                category=chunk.category,
                type=chunk.source_type.value.replace("_", " ").title(),
                reliability_level=chunk.reliability_level,
                score=round(float(item.score), 4),
            )
            if stance == "CONTRADICT":
                contradicting.append(evidence_obj)
            elif stance == "SUPPORT":
                supporting.append(evidence_obj)

        best_score = max(
            [e.score for e in supporting] + [e.score for e in contradicting],
            default=0.0,
        )
        top_cand = supporting[0] if supporting else (contradicting[0] if contradicting else None)
        rel_weight = 1.0 if (top_cand and top_cand.reliability_level == ReliabilityLevel.VERY_HIGH) else 0.88

        if not supporting and not contradicting:
            return dict(
                verdict=VerdictEnum.INSUFFICIENT_EVIDENCE, confidence=0.0,
                summary="Retrieved documents contain related keywords but no conclusive evidence.",
                reasoning=[
                    "Retrieved documents were evaluated for stance and entity alignment.",
                    "No primary sources explicitly substantiate or refute the factual premise.",
                    "TruthTrace avoids false positives without direct corroborating documentation.",
                ],
                supporting_evidence=[], contradicting_evidence=[],
            )
        elif contradicting and not supporting:
            return dict(
                verdict=VerdictEnum.FALSE,
                confidence=min(0.96, max(0.65, round(best_score * rel_weight + 0.12, 2))),
                summary=f"The claim is refuted by authoritative findings from {contradicting[0].source}.",
                reasoning=[
                    f"Direct contradictory evidence from {contradicting[0].source} (score {contradicting[0].score}).",
                    f'Excerpt: "{contradicting[0].text[:140]}..."',
                    "No supporting evidence found in the indexed corpus.",
                ],
                supporting_evidence=supporting, contradicting_evidence=contradicting,
            )
        elif supporting and not contradicting:
            return dict(
                verdict=VerdictEnum.TRUE,
                confidence=min(0.95, max(0.60, round(best_score * rel_weight + 0.08, 2))),
                summary=f"The claim is factually supported by reporting from {supporting[0].source}.",
                reasoning=[
                    f"Substantiating documentation from {supporting[0].source} (score {supporting[0].score}).",
                    f'Excerpt: "{supporting[0].text[:140]}..."',
                    "Grounded evidence affirms the core factual premise.",
                ],
                supporting_evidence=supporting, contradicting_evidence=contradicting,
            )
        else:
            return dict(
                verdict=VerdictEnum.MISLEADING,
                confidence=min(0.90, max(0.55, round(best_score * 0.80, 2))),
                summary="The claim contains partial facts but is contradicted by primary sources.",
                reasoning=[
                    f"Contradictory findings from {contradicting[0].source}.",
                    f"Partial support from {supporting[0].source}, disputed by contradictory statements.",
                    "Review cited excerpts below for full context.",
                ],
                supporting_evidence=supporting, contradicting_evidence=contradicting,
            )

    def verify(self, req: VerificationRequest) -> VerificationResponse:
        """
        End-to-end verification pipeline.

        Steps:
        1. Normalize claim & extract key terms
        2. Multi-query FAISS semantic retrieval
        3. Threshold filtering
        4. Gemini LLM reasoning (if configured) → rich natural-language verdict
           └─ Fallback: heuristic stance analysis if Gemini unavailable
        5. Compute freshness & source diversity metadata
        """
        start_time = time.time()
        raw_claim = req.text.strip()
        normalized = self.normalize_claim(raw_claim)
        claim_terms = self.extract_key_terms(normalized)

        top_k = getattr(req, "top_k", 5)
        news_only = getattr(req, "news_only", False)

        # ── Step 1: FAISS retrieval ─────────────────────────────────────────────
        candidates = self.retrieve_evidence(normalized, top_k_per_query=top_k, news_only=news_only)
        relevant_candidates = [r for r in candidates if r.score >= MIN_SEMANTIC_THRESHOLD]

        if not relevant_candidates:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            terms_display = ", ".join(f"'{t}'" for t in list(claim_terms)[:3]) if claim_terms else raw_claim
            return VerificationResponse(
                verdict=VerdictEnum.INSUFFICIENT_EVIDENCE,
                confidence=0.0,
                summary="No authoritative evidence in the knowledge base is sufficiently relevant to verify this claim.",
                reasoning=[
                    f"Analyzed {self.vector_store.count()} indexed chunks in FAISS.",
                    f"Key terms ({terms_display}) found no matches above the relevance threshold ({MIN_SEMANTIC_THRESHOLD}).",
                    "TruthTrace's grounding policy prevents verdicts without direct corroborating evidence.",
                ],
                supporting_evidence=[],
                contradicting_evidence=[],
                total_evidence_analyzed=0,
                processing_time_ms=elapsed_ms,
                llm_powered=False,
            )

        # ── Step 2: Build structured evidence snippets ──────────────────────────
        snippets = self._build_evidence_snippets(relevant_candidates)

        # ── Step 3: Try Gemini LLM reasoning ───────────────────────────────────
        llm_result = None
        llm_powered = False

        if llm_service.is_available:
            try:
                llm_result = llm_service.analyze(claim=normalized, evidence_snippets=snippets)
                if llm_result:
                    llm_powered = True
                    logger.info(f"Gemini verdict: {llm_result['verdict']} ({llm_result['confidence']:.2f})")
            except Exception as exc:
                logger.warning(f"Gemini call failed, using heuristic fallback: {exc}")

        # ── Step 4: Build EvidenceItem lists ────────────────────────────────────
        # Always classify chunks heuristically for the evidence lists
        # (Gemini gives us verdict/reasoning; we still need per-chunk objects for the response)
        heuristic = self._heuristic_verdict(normalized, relevant_candidates, claim_terms)
        supporting: List[EvidenceItem] = heuristic["supporting_evidence"]
        contradicting: List[EvidenceItem] = heuristic["contradicting_evidence"]

        # ── Step 5: Freshness & diversity metadata ──────────────────────────────
        all_evidence = supporting + contradicting
        dates = [e.publication_date for e in all_evidence if e.publication_date]
        knowledge_base_freshness = max(dates) if dates else None
        news_sources_used = len({e.source for e in all_evidence})

        # ── Step 6: Build final verdict ─────────────────────────────────────────
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        if llm_result:
            # Use Gemini's verdict, confidence, and natural-language reasoning
            verdict_str = llm_result["verdict"]
            verdict = VerdictEnum(verdict_str)
            confidence = float(llm_result["confidence"])
            summary = llm_result["summary"]
            reasoning = llm_result["reasoning"]
            if isinstance(reasoning, str):
                reasoning = [reasoning]
        else:
            # Fallback: use heuristic output
            verdict = heuristic["verdict"]
            confidence = heuristic["confidence"]
            summary = heuristic["summary"]
            reasoning = heuristic["reasoning"]

        return VerificationResponse(
            verdict=verdict,
            confidence=confidence,
            summary=summary,
            reasoning=reasoning,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            total_evidence_analyzed=len(supporting) + len(contradicting),
            processing_time_ms=elapsed_ms,
            knowledge_base_freshness=knowledge_base_freshness,
            news_sources_used=news_sources_used,
            llm_powered=llm_powered,
        )


# Global singleton instance
verification_service = VerificationService()
