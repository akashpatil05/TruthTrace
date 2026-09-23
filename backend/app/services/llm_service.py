"""
LLM Service — Google Gemini integration for TruthTrace (Ultra Low-Latency REST).

Uses direct HTTP REST API with connection pooling and strict timeout budgets (2.5s).
If Google AI Studio encounters cloud queuing or throttling, TruthTrace immediately
returns the high-accuracy grounded heuristic verdict in milliseconds instead of
hanging the user for 20-30 seconds.
"""

from __future__ import annotations

import json
import logging
import requests
from typing import Any, Dict, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Persistent connection pool session for sub-second REST roundtrips
_HTTP_SESSION = requests.Session()

# ── Prompt template ────────────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """You are TruthTrace, an expert AI fact-checker.
Evaluate the claim using ONLY the provided evidence. Do NOT use outside knowledge.

Rules:
- Clearly supports claim -> verdict: "TRUE"
- Clearly refutes claim -> verdict: "FALSE"
- Conflicting evidence -> verdict: "MISLEADING"
- Insufficient / unrelated -> verdict: "INSUFFICIENT_EVIDENCE"
- confidence: float between 0.0 and 1.0
- reasoning: 2 concise sentences
- summary: 1 clear sentence citing the primary source

JSON schema:
{
  "verdict": "TRUE" | "FALSE" | "MISLEADING" | "INSUFFICIENT_EVIDENCE",
  "confidence": 0.95,
  "summary": "Source states that...",
  "reasoning": ["point 1", "point 2"]
}"""


def _build_user_prompt(claim: str, evidence_snippets: List[Dict[str, Any]]) -> str:
    top_snippets = evidence_snippets[:3]
    lines = [f'CLAIM: "{claim}"\n\nEVIDENCE:']
    for i, ev in enumerate(top_snippets):
        lines.append(
            f"[{i+1}] {ev.get('source', 'Unknown')} ({ev.get('date', 'Recent')}):\n"
            f'"{ev.get("text", "")[:280]}"'
        )
    lines.append("\nReturn JSON only.")
    return "\n".join(lines)


# ── LLM Service ────────────────────────────────────────────────────────────────

class GeminiLLMService:
    """
    Ultra-Low Latency Google Gemini service with strict timeout enforcement.
    """

    def __init__(self):
        self._model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self._api_key = settings.GEMINI_API_KEY
        self._timeout_seconds = 2.5  # Strict 2.5s maximum budget for LLM response

    @property
    def is_available(self) -> bool:
        return bool(settings.GEMINI_API_KEY)

    def analyze(
        self,
        claim: str,
        evidence_snippets: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Send claim + top evidence snippets to Gemini REST API with strict 2.5s timeout.
        Returns parsed dict or None (triggering instant 10ms heuristic fallback).
        """
        if not self.is_available or not evidence_snippets:
            return None

        api_key = settings.GEMINI_API_KEY
        model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        
        # Fast direct REST endpoint with HTTP keep-alive connection reuse
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        prompt = _build_user_prompt(claim, evidence_snippets)

        payload = {
            "system_instruction": {
                "parts": [{"text": _SYSTEM_INSTRUCTION}]
            },
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
                "maxOutputTokens": 250,
            }
        }

        try:
            resp = _HTTP_SESSION.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout_seconds,
            )

            if resp.status_code != 200:
                logger.warning(f"Gemini REST returned {resp.status_code}, using instant fallback")
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return None

            raw = parts[0].get("text", "").strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)

            # Validate required fields
            required = {"verdict", "confidence", "summary", "reasoning"}
            if not required.issubset(result.keys()):
                return None

            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            valid_verdicts = {"TRUE", "FALSE", "MISLEADING", "INSUFFICIENT_EVIDENCE"}
            if result["verdict"] not in valid_verdicts:
                return None

            return result

        except Exception as exc:
            # On timeout or network lag, fallback instantly without blocking
            logger.info(f"Gemini call bypassed/timed out ({exc}), returning instant heuristic verdict.")
            return None


# Singleton default LLM service
llm_service = GeminiLLMService()
