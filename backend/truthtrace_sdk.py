"""
TruthTrace Python SDK

A clean, importable interface for all TruthTrace operations:
embedding lookups, claim verification, news ingestion, and knowledge-base stats.

Quick Start:
    from truthtrace_sdk import TruthTrace

    tt = TruthTrace()

    # Verify a claim
    result = tt.verify("WHO declared COVID-19 a pandemic in 2020")
    print(result.verdict, result.confidence)
    print(result.summary)

    # Ingest latest news
    stats = tt.ingest(sources=["rss"], limit=50)
    print(f"Indexed {stats['fresh_indexed_docs']} new articles")

    # Query knowledge base
    docs = tt.search("climate change sea level rise", top_k=5)
    for doc in docs:
        print(doc["title"], doc["score"])

    # Knowledge base statistics
    kb = tt.status()
    print(kb["total_documents"], kb["newest_article_date"])
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Bootstrap path so the SDK works from any working directory ─────────────────
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ── Result dataclasses ──────────────────────────────────────────────────────────

@dataclass
class VerifyResult:
    """Structured result from a verification call."""
    verdict: str                        # TRUE | FALSE | MISLEADING | INSUFFICIENT_EVIDENCE
    confidence: float                   # 0.0 – 1.0
    summary: str
    reasoning: List[str]
    supporting_evidence: List[Dict[str, Any]]
    contradicting_evidence: List[Dict[str, Any]]
    total_evidence_analyzed: int
    processing_time_ms: float
    knowledge_base_freshness: Optional[str] = None
    news_sources_used: int = 0
    llm_powered: bool = False           # True = Gemini, False = heuristic fallback

    @property
    def is_true(self) -> bool:
        return self.verdict == "TRUE"

    @property
    def is_false(self) -> bool:
        return self.verdict == "FALSE"

    @property
    def is_misleading(self) -> bool:
        return self.verdict == "MISLEADING"

    @property
    def is_uncertain(self) -> bool:
        return self.verdict == "INSUFFICIENT_EVIDENCE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "summary": self.summary,
            "reasoning": self.reasoning,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "total_evidence_analyzed": self.total_evidence_analyzed,
            "processing_time_ms": self.processing_time_ms,
            "knowledge_base_freshness": self.knowledge_base_freshness,
            "news_sources_used": self.news_sources_used,
            "llm_powered": self.llm_powered,
        }


@dataclass
class SearchHit:
    """A single semantic search result from the knowledge base."""
    title: str
    source: str
    text: str
    url: str
    publication_date: str
    category: str
    score: float
    reliability_level: str
    document_id: str


# ── Main SDK class ──────────────────────────────────────────────────────────────

class TruthTrace:
    """
    Python SDK for the TruthTrace fact-verification and news ingestion system.

    All operations run in-process (no HTTP). The vector store, embedding model,
    and preprocessing pipeline are shared singletons loaded once on first use.
    """

    def __init__(self):
        # Lazy-import heavy services to keep import time low
        from app.services.verification import verification_service
        from app.services.retrieval import vector_store
        from app.services.embeddings import embedding_service

        self._verification_service = verification_service
        self._vector_store = vector_store
        self._embedding_service = embedding_service

    # ── Claim Verification ──────────────────────────────────────────────────────

    def verify(
        self,
        claim: str,
        *,
        news_only: bool = False,
        top_k: int = 5,
    ) -> VerifyResult:
        """
        Verify a claim, headline, or article text against the indexed knowledge base.

        Args:
            claim: The claim text to verify (e.g. "Vaccine prevents COVID hospitalisation").
            news_only: If True, restrict evidence to news-category chunks only.
            top_k: Number of evidence chunks to retrieve per query variant (1–20).

        Returns:
            VerifyResult with verdict, confidence, evidence, and freshness metadata.

        Example:
            result = tt.verify("NASA landed on the Moon in 1969")
            if result.is_true:
                print(f"Confirmed with {result.confidence*100:.0f}% confidence")
        """
        from app.models.schemas import VerificationRequest

        req = VerificationRequest(text=claim, news_only=news_only, top_k=top_k)
        resp = self._verification_service.verify(req)

        return VerifyResult(
            verdict=resp.verdict.value,
            confidence=resp.confidence,
            summary=resp.summary,
            reasoning=resp.reasoning,
            supporting_evidence=[e.model_dump() for e in resp.supporting_evidence],
            contradicting_evidence=[e.model_dump() for e in resp.contradicting_evidence],
            total_evidence_analyzed=resp.total_evidence_analyzed,
            processing_time_ms=resp.processing_time_ms,
            knowledge_base_freshness=resp.knowledge_base_freshness,
            news_sources_used=resp.news_sources_used,
            llm_powered=resp.llm_powered,
        )

    # ── Semantic Search ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[SearchHit]:
        """
        Semantic search across the knowledge base without running the full verification pipeline.

        Args:
            query: Free-text search query.
            top_k: Number of results to return.
            category: Optional filter (e.g. 'news', 'science', 'health').

        Returns:
            List of SearchHit objects sorted by relevance score.

        Example:
            hits = tt.search("vaccine efficacy clinical trials", top_k=10, category="science")
            for hit in hits:
                print(hit.score, hit.title, hit.source)
        """
        from app.services.preprocessing import preprocessor

        q_vec = self._embedding_service.embed_query(preprocessor.clean_text(query))

        if category:
            results = self._vector_store.search_filtered(q_vec, top_k=top_k, category=category)
        else:
            results = self._vector_store.search(q_vec, top_k=top_k)

        return [
            SearchHit(
                title=r.chunk.title,
                source=r.chunk.source,
                text=r.chunk.text,
                url=r.chunk.url,
                publication_date=r.chunk.publication_date,
                category=r.chunk.category,
                score=round(float(r.score), 4),
                reliability_level=r.chunk.reliability_level.value,
                document_id=r.chunk.document_id,
            )
            for r in results
        ]

    # ── News Ingestion ──────────────────────────────────────────────────────────

    def ingest(
        self,
        sources: Optional[List[str]] = None,
        *,
        limit: int = 50,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch and index the latest news articles into the knowledge base.

        Args:
            sources: List of source identifiers. Options: 'rss', 'factcheck', 'newsapi'.
                     Defaults to ['rss'] (no API key required).
            limit: Maximum number of fresh articles to ingest per call.
            dry_run: If True, fetch and deduplicate but do NOT write to the vector store.

        Returns:
            Dict with ingestion statistics:
            {
                "fresh_indexed_docs": int,
                "chunks_added": int,
                "raw_candidates": int,
                "total_store_documents": int,
                "total_store_chunks": int,
                "elapsed_sec": float,
            }

        Example:
            stats = tt.ingest(sources=["rss", "factcheck"], limit=100)
            print(f"Added {stats['chunks_added']} new chunks in {stats['elapsed_sec']:.1f}s")
        """
        from ingest_pipeline import IngestionOrchestrator

        src = sources if sources is not None else ["rss"]
        orchestrator = IngestionOrchestrator(dry_run=dry_run)
        try:
            return orchestrator.run_cycle(sources=src, limit_per_cycle=limit)
        finally:
            orchestrator.close()

    # ── Batch Document Ingestion ────────────────────────────────────────────────

    def ingest_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ingest a batch of pre-structured documents directly into the knowledge base.

        Each document must include: title, content, source, url, publication_date.
        Optional: category, source_type, reliability_level.

        Args:
            documents: List of document dicts.

        Returns:
            {
                "total_submitted": int,
                "total_indexed": int,
                "total_chunks": int,
                "failed": int,
                "errors": List[str],
            }

        Example:
            tt.ingest_documents([
                {
                    "title": "Scientists confirm climate warming trend",
                    "content": "A new study published in Nature...",
                    "source": "Nature",
                    "url": "https://nature.com/articles/...",
                    "publication_date": "2026-09-01",
                    "category": "science",
                    "reliability_level": "VERY_HIGH",
                }
            ])
        """
        from app.models.schemas import DocumentIngestRequest
        from app.services.preprocessing import preprocessor

        total_indexed = 0
        total_chunks = 0
        errors: List[str] = []

        for raw in documents:
            try:
                req = DocumentIngestRequest(**raw)
                doc_res = preprocessor.process_document(req)
                chunks = self._vector_store.ingest_document(doc_res)
                if chunks > 0:
                    total_indexed += 1
                    total_chunks += chunks
            except Exception as exc:
                title = raw.get("title", "Unknown")[:60]
                errors.append(f"{title}: {exc}")

        return {
            "total_submitted": len(documents),
            "total_indexed": total_indexed,
            "total_chunks": total_chunks,
            "failed": len(documents) - total_indexed,
            "errors": errors,
        }

    # ── Knowledge Base Statistics ───────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """
        Return detailed statistics about the current knowledge base.

        Returns:
            {
                "total_documents": int,
                "total_chunks": int,
                "unique_sources": int,
                "newest_article_date": str,
                "oldest_article_date": str,
                "categories": {category: chunk_count},
                "reliability_breakdown": {level: chunk_count},
                "sources": [source_name, ...],
            }

        Example:
            kb = tt.status()
            print(f"Knowledge base has {kb['total_documents']} documents")
            print(f"Newest article: {kb['newest_article_date']}")
        """
        return self._vector_store.get_stats()

    def list_documents(
        self,
        category: Optional[str] = None,
        reliability_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List documents in the knowledge base with optional filtering.

        Args:
            category: Filter by category (e.g. 'news', 'science', 'health').
            reliability_level: Filter by reliability (VERY_HIGH, HIGH, MEDIUM, LOW).

        Returns:
            List of document metadata dicts.
        """
        return self._vector_store.list_documents(
            category=category,
            reliability_level=reliability_level,
        )
