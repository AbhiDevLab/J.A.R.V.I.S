"""Conservative matchers for the legacy JARVIS command fallbacks.

Structured automation routing runs before these helpers. These predicates keep
legacy feature handlers from treating a word mentioned inside a question or
statement as an instruction to launch an application or start another action.
"""
from __future__ import annotations

import re


_OPEN_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:open|launch|start|run)\b",
    re.IGNORECASE,
)
_YOUTUBE_COMMAND = re.compile(
    r"^\s*(?:(?:please\s+)?(?:play|watch|search|find)\b(?=[^\r\n]*\byoutube\b)"
    r"|youtube(?:\s|$))",
    re.IGNORECASE,
)
_MESSAGE_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:"
    r"send\s+(?:a\s+)?(?:message|sms)\b"
    r"|(?:make\s+a\s+)?phone\s+call\b"
    r"|(?:make\s+a\s+)?video\s+call\b"
    r")",
    re.IGNORECASE,
)


def is_legacy_open_command(text: str) -> bool:
    """True only when a message starts with an explicit open/launch command."""
    return bool(_OPEN_COMMAND.search(str(text or "")))


def is_legacy_youtube_command(text: str) -> bool:
    """Require an explicit media/search command or the legacy 'youtube ...' prefix."""
    return bool(_YOUTUBE_COMMAND.search(str(text or "")))


def is_legacy_message_command(text: str) -> bool:
    """Require an explicit message/call request at the start of the utterance."""
    return bool(_MESSAGE_COMMAND.search(str(text or "")))
