"""Context-aware user-intent interpretation for J.A.R.V.I.S.

Phase 8.1:
- Treat STT output as an imperfect transcript rather than unquestionable truth.
- Use recent conversation context and active interaction state to infer intended meaning.
- Return a conservative normalized query that can be passed to the existing
  deterministic automation router or conversational LLM.
- Never execute actions or bypass the existing security/authorization layer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from engine.llm_client import ask_llm
from engine.interaction_state import get_interaction_state


@dataclass(frozen=True)
class InterpretationResult:
    """The interpreted meaning of one user utterance."""

    raw_transcript: str
    interpreted_query: str
    intent: str
    confidence: float
    needs_clarification: bool = False
    clarification_question: str = ""
    used_context: bool = False

    @property
    def query(self) -> str:
        """Return the safest query for downstream processing."""
        return self.interpreted_query or self.raw_transcript


_ALLOWED_INTENTS = {
    "automation",
    "conversation",
    "clarification",
    "confirmation",
    "cancellation",
    "unknown",
}


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract one JSON object from an otherwise noisy model response."""
    value = str(text or "").strip()

    if not value:
        return None

    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", value)

    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, confidence))


def _normalize_intent(value: Any) -> str:
    intent = str(value or "unknown").strip().lower()

    if intent not in _ALLOWED_INTENTS:
        return "unknown"

    return intent


def _fallback(
    transcript: str,
    *,
    used_context: bool = False,
) -> InterpretationResult:
    return InterpretationResult(
        raw_transcript=transcript,
        interpreted_query=transcript,
        intent="unknown",
        confidence=0.0,
        used_context=used_context,
    )


def interpret_query(
    transcript: str,
    *,
    conversation_context: str = "",
    interaction_state: str = "",
    language: str = "en",
) -> InterpretationResult:
    """Infer intended meaning from a possibly imperfect transcript.

    The model is explicitly forbidden from inventing missing details.
    If interpretation is uncertain, the original transcript is preserved
    so the downstream system can ask for clarification or handle it normally.
    """

    raw = str(transcript or "").strip()

    if not raw:
        return _fallback(raw)

    active_state = get_interaction_state()

    if not interaction_state:
        interaction_state = active_state.as_context()

    has_context = bool(
        str(conversation_context or "").strip()
        or str(interaction_state or "").strip()
    )

    prompt = f"""
You are the contextual interpretation layer inside J.A.R.V.I.S., a desktop AI assistant.

Your job is NOT to answer the user and NOT to execute anything.
Your job is to infer what the user most likely meant from an imperfect speech-to-text transcript.

The transcript may contain:
- speech recognition mistakes,
- missing words,
- phonetic substitutions,
- punctuation mistakes,
- pronoun/reference ambiguity,
- incomplete follow-up commands.

Use the supplied conversation context and active interaction state when relevant.

IMPORTANT RULES:
1. Preserve the user's intended meaning; do not rewrite it into a different request.
2. Correct obvious STT mistakes when context strongly supports the correction.
3. Resolve references such as "it", "that", "this", "there", "the previous one", "the first one", etc. when the context identifies the referent.
4. If the user is continuing a pending task, interpret the utterance as a continuation of that task.
5. Never invent a filename, person, application, destination, amount, or other missing detail.
6. Never invent confirmation for a dangerous action.
7. Never treat uncertain inference as certain.
8. If the meaning genuinely cannot be determined, set needs_clarification=true and provide a short clarification question.
9. Keep the interpreted_query concise and directly usable by the downstream J.A.R.V.I.S. router/LLM.
10. The interpreted query should be in the same language as the user's utterance where practical.
11. Output ONLY valid JSON. No Markdown and no explanation.

Intent must be one of:
- automation
- conversation
- clarification
- confirmation
- cancellation
- unknown

Output schema:
{{
  "interpreted_query": "string",
  "intent": "automation|conversation|clarification|confirmation|cancellation|unknown",
  "confidence": 0.0,
  "needs_clarification": false,
  "clarification_question": ""
}}

Detected language: {language}

Previous conversation context:
{conversation_context or "(none)"}

Active interaction state:
{interaction_state or "(none)"}

Raw speech-to-text transcript:
{raw}
"""

    try:
        response = ask_llm(prompt)
        data = _extract_json(response)

        if not data:
            print("Context interpreter returned invalid JSON; preserving raw transcript.")
            return _fallback(raw, used_context=has_context)

        interpreted = str(
            data.get("interpreted_query", "")
        ).strip()

        if not interpreted:
            interpreted = raw

        confidence = _normalize_confidence(
            data.get("confidence", 0.0)
        )
        intent = _normalize_intent(
            data.get("intent")
        )
        needs_clarification = bool(
            data.get("needs_clarification", False)
        )
        clarification_question = str(
            data.get("clarification_question", "")
        ).strip()

        # Conservative safety boundary: low-confidence interpretation never
        # replaces the original transcript.
        try:
            minimum_confidence = float(
                __import__("os").getenv(
                    "JARVIS_INTERPRETATION_MIN_CONFIDENCE",
                    "0.70",
                )
            )
        except (TypeError, ValueError):
            minimum_confidence = 0.70

        if confidence < minimum_confidence:
            interpreted = raw
            needs_clarification = False
            clarification_question = ""

        return InterpretationResult(
            raw_transcript=raw,
            interpreted_query=interpreted,
            intent=intent,
            confidence=confidence,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            used_context=has_context,
        )

    except Exception as exc:
        print(
            "Context interpretation unavailable; "
            f"preserving raw transcript: {exc}"
        )
        return _fallback(
            raw,
            used_context=has_context,
        )
