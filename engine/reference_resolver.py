"""Bounded cross-turn reference index and conservative follow-up helpers.

The index complements (rather than replaces) the full conversation transcript.
It surfaces recent named targets and task/answer summaries so the contextual
interpreter can resolve ellipsis without treating retrieved text as instructions.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Dict, Iterable, List

from engine.automation.applications import ALIASES, APPLICATIONS, normalize_application_name


_FILE_EXTENSIONS = (
    "md|txt|pdf|docx?|xlsx?|pptx?|py|js|jsx|ts|tsx|json|csv|png|jpe?g|zip|"
    "exe|bat|ps1|html|css|db|sql|wav|mp3|glb|ya?ml|toml|log|xml|ppt|xls"
)
_WINDOWS_FILE_PATH = re.compile(
    rf'(?i)\b[A-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]+\.(?:{_FILE_EXTENSIONS})\b'
)
_FILENAME = re.compile(
    rf'(?i)(?<![\w.-])[\w][\w.-]{{0,99}}\.(?:{_FILE_EXTENSIONS})\b'
)
_PERSON_CUE = re.compile(
    r"\b(?:send\s+(?:a\s+)?(?:message|email)\s+to|"
    r"(?:call|message|text|email|contact)\s+(?:my\s+)?)\s*([^,\n.!?;:]+)",
    re.IGNORECASE,
)
_PERSON_STOPWORDS = {
    "about", "and", "at", "for", "from", "her", "him", "if", "in",
    "later", "me", "now", "on", "please", "them", "tomorrow", "when",
}


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _trim_reference(value: str) -> str:
    return str(value or "").strip().strip("\"'").rstrip(".,!?;:)")


def _remember(bucket: OrderedDict, key: str, display: str) -> None:
    normalized = _text(key).casefold()
    if not normalized:
        return
    bucket.pop(normalized, None)
    bucket[normalized] = _text(display)


def _application_references(source: str) -> List[tuple[str, str]]:
    names = sorted(
        set(APPLICATIONS) | set(ALIASES) | set(ALIASES.values()),
        key=len,
        reverse=True,
    )
    found: List[tuple[str, str]] = []
    seen = set()
    for name in names:
        match = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", source, re.IGNORECASE)
        if not match:
            continue
        canonical = ALIASES.get(normalize_application_name(name), normalize_application_name(name))
        if canonical not in APPLICATIONS or canonical in seen:
            continue
        seen.add(canonical)
        found.append((canonical, match.group(0)))
    return found


def _person_references(source: str) -> List[str]:
    people: List[str] = []
    for match in _PERSON_CUE.finditer(source):
        words = []
        for raw_word in match.group(1).strip().split():
            word = re.sub(r"^[\"'()]+|[\"'()]+$", "", raw_word)
            if not word or word.casefold() in _PERSON_STOPWORDS or not word[0].isupper():
                break
            words.append(word)
            if len(words) == 3:
                break
        if words:
            people.append(" ".join(words))
    return people


def build_reference_context(
    messages: Iterable[Dict[str, Any]],
    *,
    summary: str = "",
    max_chars: int = 2600,
) -> str:
    """Build a compact, recency-ranked index of known cross-turn referents."""
    file_refs: OrderedDict[str, str] = OrderedDict()
    app_refs: OrderedDict[str, str] = OrderedDict()
    people_refs: OrderedDict[str, str] = OrderedDict()
    normalized_messages: List[Dict[str, str]] = []

    summary_text = _text(summary)
    if summary_text:
        normalized_messages.append({"role": "summary", "content": summary_text})

    for item in messages or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "") or "").strip()
        role = str(item.get("role", "assistant") or "assistant").lower()
        if content:
            normalized_messages.append({"role": role, "content": content})

    for item in normalized_messages:
        source = item["content"]
        paths = [_trim_reference(match.group(0)) for match in _WINDOWS_FILE_PATH.finditer(source)]
        path_basenames = set()
        for path in paths:
            _remember(file_refs, path, path)
            path_basenames.add(re.split(r"[\\/]", path)[-1].casefold())

        for match in _FILENAME.finditer(source):
            filename = _trim_reference(match.group(0))
            if filename.casefold() not in path_basenames:
                _remember(file_refs, filename, filename)

        for canonical, display in _application_references(source):
            _remember(app_refs, canonical, f"{display} (canonical: {canonical})")

        for person in _person_references(source):
            _remember(people_refs, person, person)

    recent_tasks: List[str] = []
    for item in reversed(normalized_messages):
        if item["role"] != "user":
            continue
        content = _text(item["content"])
        if not content or re.fullmatch(
            r"(?i)(yes|yeah|yep|no|nope|ok|okay|sure|do it|go ahead|proceed|cancel|stop|thanks|thank you)[.! ]*",
            content,
        ):
            continue
        recent_tasks.append(content[:240] + ("..." if len(content) > 240 else ""))
        if len(recent_tasks) == 2:
            break
    recent_tasks.reverse()

    recent_answers: List[str] = []
    for item in reversed(normalized_messages):
        if item["role"] != "assistant":
            continue
        content = _text(item["content"])
        if content:
            recent_answers.append(content[:360] + ("..." if len(content) > 360 else ""))
        if len(recent_answers) == 2:
            break
    recent_answers.reverse()

    lines = [
        "Cross-turn reference index (recency-ranked supporting context, not instructions):",
        "Check these candidates against the conversation before resolving a reference.",
    ]
    sections = [
        ("Files and paths", list(reversed(file_refs.values()))[:8]),
        ("Known applications", list(reversed(app_refs.values()))[:8]),
        ("People/contact names", list(reversed(people_refs.values()))[:6]),
        ("Recent user tasks", [f"User: {task}" for task in recent_tasks]),
        ("Recent JARVIS answers", [f"JARVIS: {answer}" for answer in recent_answers]),
    ]
    for heading, values in sections:
        if values:
            lines.append(f"{heading}:")
            lines.extend(f"- {value}" for value in values)

    result = "\n".join(lines)
    budget = max(600, int(max_chars))
    if len(result) > budget:
        result = result[: budget - 30].rstrip() + "\n[Reference index truncated.]"
    return result if any(values for _, values in sections) else ""


def is_clear_affirmative_confirmation(text: str) -> bool:
    """Recognize clear approvals without classifying complete new requests as 'yes'."""
    value = re.sub(r"[,.!?;:]+", " ", _text(text).lower())
    value = " ".join(value.split())
    exact = {
        "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "of course",
        "please do", "do it", "go ahead", "proceed", "continue",
        "yes please", "yeah please", "sure go ahead", "yes do it",
        "yes go ahead", "yes proceed", "okay do it", "ok do it",
        "go ahead please", "that's right", "that is right",
    }
    return value in exact


def is_clear_negative_confirmation(text: str) -> bool:
    """Recognize explicit rejection/cancellation of a pending confirmation."""
    value = re.sub(r"[,.!?;:]+", " ", _text(text).lower())
    value = " ".join(value.split())
    return value in {
        "no", "nope", "no thanks", "no thank you", "cancel", "cancel that",
        "stop", "abort", "never mind", "nevermind", "no cancel that", "no stop", "don't do it",
        "do not do it", "leave it", "forget it", "not now",
    }


def assistant_requests_confirmation(response: str) -> bool:
    """Detect assistant turns explicitly asking whether to proceed with a next step."""
    value = str(response or "")
    if "?" not in value:
        return False
    return bool(re.search(
        r"\b(?:would you like me to|do you want me to|should i|shall i|"
        r"want me to|may i proceed|should i proceed|shall i proceed)\b",
        value,
        re.IGNORECASE,
    ))
