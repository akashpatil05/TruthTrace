"""
LLM Service — Google Gemini integration for TruthTrace.

Uses the current `google-genai` SDK (google.genai), which supersedes
the deprecated `google-generativeai` package.

Flow:
    FAISS evidence chunks
          ↓
    Gemini (gemini-2.0-flash) with structured JSON prompt
          ↓
    {verdict, confidence, summary, reasoning, evidence_assessment}
          ↓
    Falls back to heuristic engine if GEMINI_API_KEY is not set or call fails
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Prompt template ────────────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """You are TruthTrace, an expert AI fact-checker.

Your job is to evaluate a factual claim using ONLY the evidence excerpts provided.
You must NOT use any outside knowledge — every conclusion must cite the provided evidence.

Rules:
- If the evidence clearly supports the claim → verdict: TRUE
- If the evidence clearly refutes the claim → verdict: FALSE
- If evidence both supports and refutes → verdict: MISLEADING
- If evidence is insufficient or unrelated → verdict: INSUFFICIENT_EVIDENCE
- confidence must be between 0.0 and 1.0
- reasoning must be a list of 2–4 concise, evidence-grounded sentences
- evidence_assessment must list each snippet's stance

Respond ONLY with valid JSON matching this exact schema — no markdown, no extra text:
{
  "verdict": "TRUE" | "FALSE" | "MISLEADING" | "INSUFFICIENT_EVIDENCE",
  "confidence": float,
  "summary": "One sentence verdict summary citing source name.",
  "reasoning": ["sentence 1", "sentence 2", "..."],
  "evidence_assessment": [
    {"snippet_index": 0, "source": "...", "stance": "SUPPORT" | "CONTRADICT" | "NEUTRAL", "reason": "..."},
    ...
  ]
}"""


def _build_user_prompt(claim: str, evidence_snippets: List[Dict[str, Any]]) -> str:
    lines = [f'CLAIM TO VERIFY:\n"{claim}"\n\nEVIDENCE EXCERPTS:']
    for i, ev in enumerate(evidence_snippets):
        lines.append(
            f"\n[{i}] Source: {ev.get('source', 'Unknown')} | "
            f"Reliability: {ev.get('reliability', 'HIGH')} | "
            f"Date: {ev.get('date', 'unknown')} | "
            f"Category: {ev.get('category', 'general')}\n"
            f"Similarity score: {ev.get('score', 0.0):.3f}\n"
            f'Text: "{ev.get("text", "")[:400]}"'
        )
    lines.append("\nRespond with JSON only.")
    return "\n".join(lines)


# ── LLM Service ────────────────────────────────────────────────────────────────

class GeminiLLMService:
    """
    Wraps Google Gemini (google.genai SDK) for structured fact-check verdicts.

    Usage:
        from app.services.llm_service import llm_service

        result = llm_service.analyze(
            claim="WHO declared COVID-19 a pandemic in 2020",
            evidence_snippets=[{"source": "BBC", "text": "...", "score": 0.82, ...}]
        )
        if result:
            print(result["verdict"], result["confidence"])
    """

    def __init__(self):
        self._client = None
        self._model_name: Optional[str] = None
        self._available: Optional[bool] = None

    def _init_client(self):
        """Lazy-initialize Gemini client on first use."""
        if self._available is not None:
            return

        try:
            from google import genai
            from app.config import settings  # re-read on every init so .env changes take effect

            if not settings.GEMINI_API_KEY:
                logger.info("GEMINI_API_KEY not set — using heuristic verdict engine.")
                self._available = False
                return

            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self._model_name = settings.GEMINI_MODEL   # picked up fresh from .env every time
            self._available = True
            logger.info(f"Gemini LLM service ready (model: {self._model_name})")

        except ImportError:
            logger.warning("google-genai not installed. Run: pip install google-genai")
            self._available = False
        except Exception as exc:
            logger.error(f"Failed to initialize Gemini client: {exc}")
            self._available = False

    @property
    def is_available(self) -> bool:
        """True if a valid GEMINI_API_KEY is configured and the SDK is installed."""
        if self._available is None:
            self._init_client()
        return bool(self._available)

    def analyze(
        self,
        claim: str,
        evidence_snippets: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Send claim + evidence to Gemini and return a structured verdict dict.

        Args:
            claim: Normalized claim text.
            evidence_snippets: List of dicts with keys: text, source, score,
                               reliability, date, category, url.

        Returns:
            Dict with: verdict, confidence, summary, reasoning, evidence_assessment
            Returns None if Gemini is unavailable or the call fails (triggers fallback).
        """
        if not self.is_available or not evidence_snippets:
            return None

        from google import genai
        from google.genai import types

        prompt = _build_user_prompt(claim, evidence_snippets)

        # Combine system instruction + user prompt into a single contents list
        contents = [
            types.Content(
                role="user",
                parts=[types.Part(text=_SYSTEM_INSTRUCTION + "\n\n" + prompt)],
            )
        ]

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=1024,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=config,
            )
            raw = response.text.strip() if response.text else ""

            # Strip markdown fences if accidentally present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)

            # Validate required fields
            required = {"verdict", "confidence", "summary", "reasoning"}
            missing = required - result.keys()
            if missing:
                logger.warning(f"Gemini response missing fields: {missing}")
                return None

            # Clamp + validate
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            valid_verdicts = {"TRUE", "FALSE", "MISLEADING", "INSUFFICIENT_EVIDENCE"}
            if result["verdict"] not in valid_verdicts:
                result["verdict"] = "INSUFFICIENT_EVIDENCE"

            return result

        except json.JSONDecodeError as exc:
            logger.error(f"Gemini returned non-JSON: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Gemini API call failed: {exc}")
            return None


# ── Singleton ──────────────────────────────────────────────────────────────────
llm_service = GeminiLLMService()
