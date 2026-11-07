"""Small, deterministic recovery helpers for J.A.R.V.I.S LLM failures.

These helpers only manage the user's explicit retry/cancel choice. They never
execute an automation action or approve an authorization request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


_RETRY_REPLIES = {
    "retry",
    "try again",
    "retry request",
    "try that again",
    "please retry",
    "retry it",
}

_CANCEL_REPLIES = {
    "cancel",
    "stop",
    "no",
    "never mind",
    "nevermind",
    "don't retry",
    "do not retry",
}


@dataclass(frozen=True)
class RetryResolution:
    action: str
    pending_request: str = ""
    raw_transcript: str = ""
    language: str = "en"
    is_voice_input: bool = False


def resolve_pending_retry(reply: str, state: Any) -> RetryResolution | None:
    """Resolve a reply while an LLM request is waiting for explicit retry.

    A different utterance is treated as a new request. On retry, any prior
    selection/clarification/confirmation state captured before the LLM failure
    is restored so the interpreter can resume the same dialogue safely.
    """
    if getattr(state, "state_type", "") != "llm_retry":
        return None

    normalized = " ".join(str(reply or "").casefold().strip().split())

    if normalized in _RETRY_REPLIES:
        data: Dict[str, Any] = dict(getattr(state, "data", {}) or {})
        previous = data.get("previous_interaction_state") or {}
        state.clear()

        if previous.get("state_type"):
            state.set(
                previous.get("state_type", ""),
                prompt=previous.get("prompt", ""),
                action_type=previous.get("action_type", ""),
                candidates=previous.get("candidates", []),
                **(previous.get("data") or {}),
            )

        return RetryResolution(
            action="retry",
            pending_request=str(data.get("pending_request") or ""),
            raw_transcript=str(data.get("raw_transcript") or ""),
            language=str(data.get("language") or "en"),
            is_voice_input=bool(data.get("is_voice_input", False)),
        )

    if normalized in _CANCEL_REPLIES:
        state.clear()
        return RetryResolution(action="cancel")

    # A new request supersedes the pending retry, but is not interpreted as
    # consent to repeat the failed request.
    state.clear()
    return RetryResolution(action="new_request")
