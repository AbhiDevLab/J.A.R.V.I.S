"""Structured semantic intent detection for J.A.R.V.I.S. Phase 8.6.

Classification informs the existing command pipeline; it never executes an
action. Automation still has to be translated by route_command() into an
AutomationAction and passes through the existing authorization gates.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SemanticIntent(str, Enum):
    AUTOMATION = "automation"
    INFORMATION_REQUEST = "information_request"
    CONVERSATION = "conversation"
    CLARIFICATION = "clarification"
    CONFIRMATION = "confirmation"
    CANCELLATION = "cancellation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentClassification:
    """Normalized intent metadata for one user utterance."""

    intent: SemanticIntent
    normalized_query: str
    confidence: float
    source: str
    needs_clarification: bool = False
    reason: str = ""

    @property
    def should_route_automation(self) -> bool:
        """Whether the deterministic automation router may inspect this query."""
        return self.intent is SemanticIntent.AUTOMATION and not self.needs_clarification


_CANCEL = re.compile(
    r"^(?:no|nope|cancel|cancel that|cancel it|stop|abort|never mind|nevermind|"
    r"forget it|leave it|don't do it|do not do it|not now)[.! ]*$",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"^\s*(?:what|which|who|when|where|why|how|is|are|was|were|"
    r"do|does|did|would|should|will|have|has|had)\b",
    re.IGNORECASE,
)
_DIRECTORY_LIST_QUESTION = re.compile(
    r"^\s*(?:what(?:'s| is|s) in|list (?:the )?files|show (?:the )?(?:files|contents|directory))\b",
    re.IGNORECASE,
)
_DIRECT_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:open|launch|start|run|delete|remove|rename|move|copy|"
    r"create|make|install|uninstall|kill|terminate|play)\b",
    re.IGNORECASE,
)
_FILE_SEARCH_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:find|locate|search for)\s+"
    r"(?:(?:a|the)\s+)?(?:file|folder|document|directory|filename|file named|file called)\b",
    re.IGNORECASE,
)
_FILE_LIST_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:list|show)\s+(?:me\s+)?(?:the\s+)?"
    r"(?:files|contents|directory|folder)\b",
    re.IGNORECASE,
)
_CONTACT_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:send\s+(?:a\s+)?(?:message|sms|email)\b|"
    r"(?:make\s+a\s+)?(?:phone|video)\s+call\b)",
    re.IGNORECASE,
)
_COMPOUND_FILE_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:find|search for|locate)\s+.+?\s+"
    r"(?:and then|then|and)\s+(?:open|delete|remove|move|copy|rename)\b",
    re.IGNORECASE,
)
_YOUTUBE_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:(?:play|watch|search|find)\b.*\byoutube\b|youtube(?:\s|$))",
    re.IGNORECASE,
)
_SHELL_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:run|execute)\s+(?:a\s+)?(?:shell\s+)?command\b",
    re.IGNORECASE,
)
_POLITE_COMMAND = re.compile(
    r"^\s*(?:can|could|would)\s+you\s+(?:please\s+)?"
    r"(?P<command>(?:open|launch|start|run|delete|remove|rename|move|copy|"
    r"create|make|install|uninstall|kill|terminate|play|find|locate|send)\b.+)$",
    re.IGNORECASE,
)
_AFFIRMATIVE = re.compile(
    r"^(?:yes|yeah|yep|yup|sure|okay|ok|of course|please do|do it|go ahead|"
    r"proceed|continue|yes please|yeah please|yes do it|yes go ahead|"
    r"yes proceed|okay do it|ok do it|go ahead please|that's right|that is right)[.! ]*$",
    re.IGNORECASE,
)


def _minimum_confidence() -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv("JARVIS_INTERPRETATION_MIN_CONFIDENCE", "0.70"))))
    except (TypeError, ValueError):
        return 0.70


def _result(intent: SemanticIntent, query: str, confidence: float, source: str, reason: str, needs_clarification: bool = False) -> IntentClassification:
    return IntentClassification(
        intent=intent,
        normalized_query=str(query or "").strip(),
        confidence=max(0.0, min(1.0, float(confidence))),
        source=source,
        needs_clarification=needs_clarification,
        reason=reason,
    )


def _state_value(state: Any, name: str, default: Any = "") -> Any:
    if isinstance(state, dict):
        return state.get(name, default)
    return getattr(state, name, default)


def _explicit_automation(text: str) -> bool:
    value = str(text or "").strip()
    return bool(
        _DIRECT_COMMAND.match(value)
        or _FILE_SEARCH_COMMAND.match(value)
        or _FILE_LIST_COMMAND.match(value)
        or _CONTACT_COMMAND.match(value)
        or _COMPOUND_FILE_COMMAND.match(value)
        or _YOUTUBE_COMMAND.match(value)
        or _SHELL_COMMAND.match(value)
        or _DIRECTORY_LIST_QUESTION.match(value)
    )


def classify_intent(
    query: str,
    *,
    raw_text: str | None = None,
    interpretation: Any = None,
    interaction_state: Any = None,
) -> IntentClassification:
    """Classify an utterance conservatively without executing it.

    Explicit command forms are deterministic. Contextual model intent is used
    only above the configured confidence threshold. An unresolved confirmation
    cannot become an executable command just because the user said "yes".
    """
    raw = str(raw_text if raw_text is not None else query or "").strip()
    normalized = str(query or "").strip()
    state_type = str(_state_value(interaction_state, "state_type", "") or "").strip().lower()
    threshold = _minimum_confidence()

    if not raw and not normalized:
        return _result(SemanticIntent.UNKNOWN, "", 0.0, "deterministic", "empty utterance")

    if state_type == "confirmation" and _CANCEL.fullmatch(raw):
        return _result(SemanticIntent.CANCELLATION, raw, 1.0, "pending_state", "explicitly cancelled the pending continuation")

    if state_type == "confirmation" and _AFFIRMATIVE.fullmatch(raw):
        interpreted_query = str(getattr(interpretation, "query", "") or normalized).strip()
        try:
            confidence = float(getattr(interpretation, "confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        model_intent = str(getattr(interpretation, "intent", "unknown") or "unknown").lower()
        if confidence >= threshold and interpreted_query and not _AFFIRMATIVE.fullmatch(interpreted_query) and (
            _explicit_automation(interpreted_query) or model_intent == "automation"
        ):
            return _result(SemanticIntent.AUTOMATION, interpreted_query, confidence, "context_interpreter", "affirmative reply resolved to the pending concrete action")
        return _result(SemanticIntent.CONFIRMATION, raw, confidence, "pending_state", "approval target is unresolved", needs_clarification=True)

    # A question about an action is not itself an instruction to execute it.
    # Keep natural directory-listing queries routed to their existing safe action.
    if _QUESTION.match(raw) and not _DIRECTORY_LIST_QUESTION.match(raw):
        # Preserve the original question if contextual rewriting accidentally
        # turned it into a command-shaped string; do not pass that rewrite on
        # to either the automation router or the conversational model.
        return _result(SemanticIntent.INFORMATION_REQUEST, raw, 0.94, "question_heuristic", "utterance asks for information rather than direct execution")

    polite = _POLITE_COMMAND.match(normalized)
    if polite:
        command_query = polite.group("command").strip().rstrip(".,!?;:")
        return _result(SemanticIntent.AUTOMATION, command_query, 0.94, "polite_command_heuristic", "polite request normalized to a concrete command")

    if _CANCEL.fullmatch(raw) and state_type in {"clarification", "selection", "selection_or_all", "authorization_confirmation"}:
        return _result(SemanticIntent.CANCELLATION, raw, 1.0, "pending_state", "explicitly cancelled a pending interaction")

    if bool(getattr(interpretation, "needs_clarification", False)):
        return _result(SemanticIntent.CLARIFICATION, raw, float(getattr(interpretation, "confidence", 0.0) or 0.0), "context_interpreter", "contextual interpreter requested clarification", needs_clarification=True)

    if _explicit_automation(normalized or raw):
        return _result(SemanticIntent.AUTOMATION, normalized or raw, 0.97, "deterministic", "explicit action command")

    if state_type in {"confirmation", "clarification"} and _AFFIRMATIVE.fullmatch(raw):
        return _result(SemanticIntent.CONFIRMATION, raw, 0.6, "pending_state", "short approval does not identify an action", needs_clarification=True)

    if interpretation is not None:
        try:
            confidence = max(0.0, min(1.0, float(getattr(interpretation, "confidence", 0.0) or 0.0)))
        except (TypeError, ValueError):
            confidence = 0.0
        model_intent = str(getattr(interpretation, "intent", "unknown") or "unknown").lower()
        model_query = str(getattr(interpretation, "query", "") or normalized or raw).strip()
        if confidence >= threshold:
            if model_intent == "automation" and _explicit_automation(model_query):
                return _result(SemanticIntent.AUTOMATION, model_query, confidence, "context_interpreter", "high-confidence contextual automation intent")
            if model_intent == "clarification":
                return _result(SemanticIntent.CLARIFICATION, raw, confidence, "context_interpreter", "contextual interpretation remains unresolved", needs_clarification=True)
            if model_intent == "confirmation":
                return _result(SemanticIntent.CONFIRMATION, model_query, confidence, "context_interpreter", "contextual confirmation intent")
            if model_intent == "cancellation":
                return _result(SemanticIntent.CANCELLATION, model_query, confidence, "context_interpreter", "contextual cancellation intent")
            if model_intent in {"conversation", "information_request"}:
                if _QUESTION.match(raw):
                    return _result(SemanticIntent.INFORMATION_REQUEST, model_query, confidence, "context_interpreter", "contextual information request")
                return _result(SemanticIntent.CONVERSATION, model_query, confidence, "context_interpreter", "contextual conversational intent")

    if _QUESTION.match(normalized or raw):
        return _result(SemanticIntent.INFORMATION_REQUEST, normalized or raw, 0.86, "question_heuristic", "question-shaped utterance")

    return _result(SemanticIntent.CONVERSATION, normalized or raw, 0.72, "fallback", "no explicit automation intent was identified")
