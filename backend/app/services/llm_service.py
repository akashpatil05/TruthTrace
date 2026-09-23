"""
LLM Service — Google Gemini integration for TruthTrace (High-Speed Optimized).

Uses the current `google-genai` SDK (google.genai).
Optimized for low-latency JSON reasoning with strict token budgeting and
native system instruction caching.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# ── Prompt template ────────────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """You are TruthTrace, an expert AI fact-checker.
Evaluate the factual claim using ONLY the provided evidence excerpts. Do NOT use outside knowledge.

Rules:
- Clearly supports claim -> verdict: "TRUE"
- Clearly refutes claim -> verdict: "FALSE"
- Conflicting evidence -> verdict: "MISLEADING"
- Insufficient / unrelated -> verdict: "INSUFFICIENT_EVIDENCE"
- confidence: float between 0.0 and 1.0
- reasoning: 2-3 concise, grounded sentences
- summary: 1 clear sentence citing the primary source

Respond strictly with valid JSON:
{
  "verdict": "TRUE" | "FALSE" | "MISLEADING" | "INSUFFICIENT_EVIDENCE",
  "confidence": 0.95,
  "summary": "Source states that...",
  "reasoning": ["point 1", "point 2"]
}"""


def _build_user_prompt(claim: str, evidence_snippets: List[Dict[str, Any]]) -> str:
    # Limit to top 3 most relevant snippets to keep prompt lightweight and fast
    top_snippets = evidence_snippets[:3]
    lines = [f'CLAIM: "{claim}"\n\nEVIDENCE:']
    for i, ev in enumerate(top_snippets):
        lines.append(
            f"[{i+1}] {ev.get('source', 'Unknown')} ({ev.get('date', 'Recent')}):\n"
            f'"{ev.get("text", "")[:300]}"'
        )
    lines.append("\nReturn JSON verdict.")
    return "\n".join(lines)


# ── LLM Service ────────────────────────────────────────────────────────────────

class GeminiLLMService:
    """
    High-Speed Google Gemini service (google.genai SDK).
    """

    def __init__(self):
        self._client = None
        self._model_name = None
        self._available: Optional[bool] = None

    def _init_client(self):
        try:
            from google import genai
            if not settings.GEMINI_API_KEY:
                self._available = False
                return

            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self._model_name = settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
            self._available = True
            logger.info(f"Gemini LLM service ready (model: {self._model_name})")

        except Exception as exc:
            logger.error(f"Failed to initialize Gemini client: {exc}")
            self._available = False

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self._init_client()
        return bool(self._available)

    def analyze(
        self,
        claim: str,
        evidence_snippets: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Send claim + top evidence snippets to Gemini and return structured verdict.
        """
        if not self.is_available or not evidence_snippets:
            return None

        from google import genai
        from google.genai import types

        prompt = _build_user_prompt(claim, evidence_snippets)

        # Use native system_instruction configuration for fast server-side caching
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.0,
            max_output_tokens=300,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
            raw = response.text.strip() if response.text else ""

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)

            # Validate required fields
            required = {"verdict", "confidence", "summary", "reasoning"}
            if not required.issubset(result.keys()):
                logger.warning("Gemini response missing fields, falling back to heuristic")
                return None

            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            valid_verdicts = {"TRUE", "FALSE", "MISLEADING", "INSUFFICIENT_EVIDENCE"}
            if result["verdict"] not in valid_verdicts:
                return None

            return result

        except Exception as exc:
            logger.warning(f"Gemini API call error: {exc}")
            return None


# Singleton default LLM service
llm_service = GeminiLLMService()
