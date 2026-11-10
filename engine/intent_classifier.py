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

from engine.automation.applications import (
    canonical_application_name,
    find_application_reference,
    parse_hindi_application_command,
)


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
    r"^(?:(?:no|nope)(?:\s*[,;.!?]\s*|\s+)(?:cancel(?:\s+(?:that|it))?|stop|abort|"
    r"never\s+mind|nevermind|forget it|leave it|don't do it|do not do it)|"
    r"no|nope|cancel(?:\s+(?:that|it))?|stop|abort|never\s+mind|nevermind|"
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
    r"^\s*(?:please\s+)?(?:open|launch|start|run|close|quit|exit|read|delete|remove|rename|move|copy|"
    r"create|make|install|uninstall|kill|terminate|play)\b",
    re.IGNORECASE,
)
_KNOWN_APPLICATION_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:open|launch|start|run|close|quit|exit)\s+"
    r"(?:the\s+)?(?P<target>.+?)\s*[.!?]*$",
    re.IGNORECASE,
)

_CONTEXTUAL_TARGET_REFERENCE = re.compile(
    r"\b(?:it|that|this|those|these|there|the\s+(?:previous|first|second|other|same)\s+"
    r"(?:one|file|folder|document|report|application))\b",
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




_APPLICATION_CONTENT_MARKER = re.compile(
    r"\b(?:read|content|contents|text|written|project\s+(?:name|title)|"
    r"document\s+title|file\s+name|author|meeting\s+time|summary|"
    r"summarize|summarise|extract|how\s+many|contains?)\b|"
    r"\bwhat(?:'s| is|s)?\s+(?:currently\s+)?in\b",
    re.IGNORECASE,
)


def _application_content_request(text: str) -> bool:
    value = str(text or "").strip()
    return bool(
        _APPLICATION_CONTENT_MARKER.search(value)
        and find_application_reference(value)
    )


_TEXT_ENTRY_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:type|enter|write)\b|"
    r"^\s*(?:please\s+)?(?:open|launch|start)\b.*"
    r"\b(?:and\s+then|then|and)\s+(?:type|enter|write)\b",
    re.IGNORECASE,
)


def _application_type_request(text: str) -> bool:
    value = str(text or "").strip()
    return bool(
        _TEXT_ENTRY_COMMAND.search(value)
        and find_application_reference(value)
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
        or _application_content_request(value)
        or _application_type_request(value)
        or _FILE_SEARCH_COMMAND.match(value)
        or _FILE_LIST_COMMAND.match(value)
        or _CONTACT_COMMAND.match(value)
        or _COMPOUND_FILE_COMMAND.match(value)
        or _YOUTUBE_COMMAND.match(value)
        or _SHELL_COMMAND.match(value)
        or _DIRECTORY_LIST_QUESTION.match(value)
    )


def _command_family(text: str) -> str:
    """Return a normalized action family for conservative spoken correction."""
    match = re.match(
        r"^\s*(?:please\s+)?(?P<verb>open|launch|start|run|close|quit|exit|"
        r"read|delete|remove|rename|move|copy|create|make|install|uninstall|"
        r"kill|terminate|play)\b",
        str(text or ""),
        re.IGNORECASE,
    )
    if not match:
        return ""
    verb = match.group("verb").casefold()
    if verb in {"open", "launch", "start", "run"}:
        return "launch"
    if verb in {"close", "quit", "exit"}:
        return "close"
    if verb in {"delete", "remove"}:
        return "delete"
    if verb in {"kill", "terminate"}:
        return "terminate"
    if verb in {"create", "make"}:
        return "create"
    return verb


def _is_known_application_command(text: str) -> bool:
    """Recognize a complete command whose target is a known installed app."""
    match = _KNOWN_APPLICATION_COMMAND.match(str(text or "").strip())
    if not match:
        return False
    return canonical_application_name(match.group("target")) is not None


def _voice_correction_threshold(default: float = 0.85) -> float:
    """Use a higher confidence floor before correcting a spoken target."""
    try:
        configured = float(os.getenv("JARVIS_VOICE_CORRECTION_MIN_CONFIDENCE", str(default)))
    except (TypeError, ValueError):
        configured = default
    return max(_minimum_confidence(), min(1.0, max(0.0, configured)))


def classify_intent(
    query: str,
    *,
    raw_text: str | None = None,
    interpretation: Any = None,
    interaction_state: Any = None,
    voice_input: bool = False,
) -> IntentClassification:
    """Classify an utterance conservatively without executing it.

    Typed explicit commands retain deterministic routing. Spoken target commands
    require a high-confidence contextual interpretation, and any correction must
    preserve the requested operation family. An unresolved confirmation cannot
    become executable merely because the user said "yes".
    """
    raw = str(raw_text if raw_text is not None else query or "").strip()
    normalized = str(query or "").strip()
    state_type = str(_state_value(interaction_state, "state_type", "") or "").strip().lower()
    threshold = _minimum_confidence()
    control_text = " ".join(
        re.sub(r"[,.!?;:]+", " ", raw.casefold()).split()
    )

    if not raw and not normalized:
        return _result(SemanticIntent.UNKNOWN, "", 0.0, "deterministic", "empty utterance")

    if state_type == "confirmation" and _CANCEL.fullmatch(control_text):
        return _result(SemanticIntent.CANCELLATION, raw, 1.0, "pending_state", "explicitly cancelled the pending continuation")

    if state_type == "confirmation" and _AFFIRMATIVE.fullmatch(control_text):
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

    # A complete command naming a known application remains executable even
    # when the contextual model is unavailable. If a model does propose a
    # different target, retain the stricter correction threshold; otherwise
    # preserve the exact recognized application and use normal authorization.
    if voice_input and _is_known_application_command(raw):
        if voice_input and interpretation is not None:
            contextual_query = str(
                getattr(interpretation, "query", "") or normalized
            ).strip()
            target_changed = contextual_query.casefold() != raw.casefold()
            if target_changed:
                try:
                    contextual_confidence = float(
                        getattr(interpretation, "confidence", 0.0) or 0.0
                    )
                except (TypeError, ValueError):
                    contextual_confidence = 0.0
                contextual_intent = str(
                    getattr(interpretation, "intent", "unknown") or "unknown"
                ).strip().lower()
                needs_clarification = bool(
                    getattr(interpretation, "needs_clarification", False)
                )
                if (
                    not needs_clarification
                    and contextual_confidence >= max(_voice_correction_threshold(), 0.97)
                    and contextual_intent == "automation"
                    and _explicit_automation(contextual_query)
                    and _command_family(raw)
                    and _command_family(raw) == _command_family(contextual_query)
                ):
                    return _result(
                        SemanticIntent.AUTOMATION,
                        contextual_query,
                        contextual_confidence,
                        "context_interpreter",
                        "near-certain voice correction preserved the requested application action",
                    )
                return _result(
                    SemanticIntent.CLARIFICATION,
                    raw,
                    contextual_confidence,
                    "voice_interpretation_unresolved",
                    "a known application target was changed without near-certain evidence",
                    needs_clarification=True,
                )

        return _result(
            SemanticIntent.AUTOMATION,
            raw,
            0.99,
            "known_application_command",
            "complete command names a known application; contextual interpretation is not required",
        )

    # Explicit text-entry requests must win over broad application-content
    # markers such as "text" or "inside". Otherwise a command to type into
    # Notepad can be misclassified as a request to read Notepad.
    if _application_type_request(raw):
        return _result(
            SemanticIntent.AUTOMATION,
            raw,
            0.99,
            "application_type_request",
            "explicit request to enter text into a named application",
        )

    # App-content requests are information-shaped but require a live desktop
    # accessibility read, not a language-model guess. Normalize Hinglish app
    # control phrases before the question-vs-command guard as well.
    hindi_app_command = parse_hindi_application_command(raw)
    if hindi_app_command:
        operation, application = hindi_app_command
        return _result(
            SemanticIntent.AUTOMATION,
            f"{operation} {application}",
            0.99,
            "hindi_application_command",
            "explicit Hinglish desktop application command",
        )

    if _application_content_request(raw):
        return _result(
            SemanticIntent.AUTOMATION,
            raw,
            0.98,
            "application_content_request",
            "explicit request to inspect text in a known application window",
        )

    # Preserve self-contained raw desktop commands, but do not discard a
    # contextual target resolution for commands such as "open that report" or
    # "close it". A referential target must resolve to a concrete command with
    # sufficient confidence; otherwise it must not fall through to a guessed
    # application/executable route.
    if _DIRECT_COMMAND.match(raw) and _explicit_automation(raw):
        if voice_input:
            try:
                contextual_confidence = float(
                    getattr(interpretation, "confidence", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                contextual_confidence = 0.0
            contextual_intent = str(
                getattr(interpretation, "intent", "unknown") or "unknown"
            ).strip().lower()
            contextual_query = str(
                getattr(interpretation, "query", "") or normalized
            ).strip()
            needs_clarification = bool(
                getattr(interpretation, "needs_clarification", False)
            )
            confidence_floor = _voice_correction_threshold()

            # If the raw target already names a known app, require near-certain
            # evidence before changing it to a different application.
            raw_known_app = find_application_reference(raw)
            target_changed = contextual_query.casefold() != raw.casefold()
            if target_changed and raw_known_app:
                confidence_floor = max(confidence_floor, 0.97)

            same_operation = (
                _command_family(raw)
                and _command_family(raw) == _command_family(contextual_query)
            )
            if (
                not needs_clarification
                and contextual_confidence >= confidence_floor
                and contextual_intent == "automation"
                and contextual_query
                and _explicit_automation(contextual_query)
                and same_operation
            ):
                return _result(
                    SemanticIntent.AUTOMATION,
                    contextual_query,
                    contextual_confidence,
                    "context_interpreter",
                    "high-confidence voice interpretation preserved the spoken action and corrected its target",
                )

            return _result(
                SemanticIntent.CLARIFICATION,
                raw,
                contextual_confidence,
                "voice_interpretation_unresolved",
                "spoken command was not sufficiently clear to execute safely",
                needs_clarification=True,
            )

        if _CONTEXTUAL_TARGET_REFERENCE.search(raw):
            try:
                contextual_confidence = float(
                    getattr(interpretation, "confidence", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                contextual_confidence = 0.0
            contextual_intent = str(
                getattr(interpretation, "intent", "unknown") or "unknown"
            ).strip().lower()
            contextual_query = str(
                getattr(interpretation, "query", "") or normalized
            ).strip()
            if (
                contextual_confidence >= threshold
                and contextual_intent == "automation"
                and contextual_query
                and contextual_query.casefold() != raw.casefold()
                and _explicit_automation(contextual_query)
                and not _CONTEXTUAL_TARGET_REFERENCE.search(contextual_query)
            ):
                return _result(
                    SemanticIntent.AUTOMATION,
                    contextual_query,
                    contextual_confidence,
                    "context_interpreter",
                    "contextual interpretation resolved the command target",
                )
            return _result(
                SemanticIntent.CLARIFICATION,
                raw,
                contextual_confidence,
                "context_reference_unresolved",
                "the command contains a reference whose target is not safely resolved",
                needs_clarification=True,
            )
        return _result(
            SemanticIntent.AUTOMATION,
            raw,
            0.99,
            "deterministic_raw_command",
            "explicit self-contained desktop command preserved from the original transcript",
        )

    # Polite imperative forms ("Could you open ...?") are requests to act,
    # unlike questions that merely ask about an earlier action ("Which file
    # did you open?"). Check both original and rewritten text before applying
    # the question guard.
    polite = _POLITE_COMMAND.match(normalized) or _POLITE_COMMAND.match(raw)

    # A question about an action is not itself an instruction to execute it.
    # Keep natural directory-listing queries routed to their existing safe action.
    if _QUESTION.match(raw) and not _DIRECTORY_LIST_QUESTION.match(raw) and not polite:
        # Preserve the original question if contextual rewriting accidentally
        # turned it into a command-shaped string; do not pass that rewrite on
        # to either the automation router or the conversational model.
        return _result(SemanticIntent.INFORMATION_REQUEST, raw, 0.94, "question_heuristic", "utterance asks for information rather than direct execution")

    if polite:
        command_query = polite.group("command").strip().rstrip(".,!?;:")
        return _result(SemanticIntent.AUTOMATION, command_query, 0.94, "polite_command_heuristic", "polite request normalized to a concrete command")

    if _CANCEL.fullmatch(control_text) and state_type in {"clarification", "selection", "selection_or_all", "authorization_confirmation"}:
        return _result(SemanticIntent.CANCELLATION, raw, 1.0, "pending_state", "explicitly cancelled a pending interaction")

    if bool(getattr(interpretation, "needs_clarification", False)):
        return _result(SemanticIntent.CLARIFICATION, raw, float(getattr(interpretation, "confidence", 0.0) or 0.0), "context_interpreter", "contextual interpreter requested clarification", needs_clarification=True)

    if _explicit_automation(normalized or raw):
        return _result(SemanticIntent.AUTOMATION, normalized or raw, 0.97, "deterministic", "explicit action command")

    if state_type in {"confirmation", "clarification"} and _AFFIRMATIVE.fullmatch(control_text):
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
