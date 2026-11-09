from __future__ import annotations

from engine.auth import recognizer
from engine.interaction_state import get_interaction_state
from .policy import describe_action, action_fingerprint


FIRST_CONFIRMATION = {
    "confirm",
    "i confirm",
    "approve",
    "i approve",
}

CANCELLATION_PHRASES = {
    "cancel",
    "stop",
    "abort",
    "no",
    "don't",
    "do not",
    "deny",
    "reject",
}


def _normalize(text: str) -> str:
    import re

    normalized = str(text or "").strip().lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


def _is_cancelled(text: str) -> bool:
    return _normalize(text) in CANCELLATION_PHRASES


def request_authorization(action, *, require_face: bool = True) -> bool:
    """Obtain a one-operation voice approval, optionally followed by face auth.

    Approval is never stored or reused. The executor binds it to the action
    fingerprint and rejects any parameter mutation before execution.
    """
    # Lazy import avoids the command/security import cycle.
    from engine.command import speak, takecommand

    description = describe_action(action)
    fingerprint = action_fingerprint(action)
    state = get_interaction_state()
    state.set(
        "authorization_confirmation",
        prompt=f"approve this exact operation: {description}",
        action_type=action.action_type,
        approval_fingerprint=fingerprint[:16],
    )

    try:
        speak(
            f"Permission required. I am about to {description}. "
            "Say 'confirm' to approve this operation, or 'cancel' to reject it."
        )
        response = takecommand()
        if isinstance(response, (tuple, list)):
            response = response[0] if response else ""
        normalized = _normalize(response)

        if _is_cancelled(normalized):
            speak("Action cancelled. No changes were made.")
            return False

        if normalized not in FIRST_CONFIRMATION:
            speak("Confirmation was not recognized. The action has been cancelled.")
            return False

        # Detect accidental in-memory mutation during the approval interaction.
        if action_fingerprint(action) != fingerprint:
            speak("The requested operation changed during approval. It has been cancelled.")
            return False

        if not require_face:
            speak("Voice confirmation accepted. Proceeding with the approved operation.")
            return True

        speak("Voice confirmation accepted. Starting face authentication.")
        try:
            face_result = recognizer.AuthenticateFace()
        except Exception as exc:
            print(f"Automation face authentication error: {type(exc).__name__}")
            face_result = 0

        if face_result != 1:
            speak("Face authentication failed. The action has been cancelled.")
            return False

        speak("Face authentication successful. Authorization accepted for this operation.")
        return True
    finally:
        state.clear()
