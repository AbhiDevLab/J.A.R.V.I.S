from __future__ import annotations
import re
from engine.auth import recognizer


FIRST_CONFIRMATION = {
    "confirm",
}

CANCELLATION_PHRASES = {
    "cancel",
    "stop",
    "abort",
    "no",
    "don't",
    "do not",
}


def _normalize(text: str) -> str:
    normalized = str(
        text or ""
    ).strip().lower()

    normalized = re.sub(
        r"[^\w\s]",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split()
    )


def _is_cancelled(text: str) -> bool:
    return _normalize(text) in CANCELLATION_PHRASES


def request_authorization(action) -> bool:
    """
    Require one explicit voice confirmation followed by
    successful face authentication.

    Fail closed:
    any failed step means the action is cancelled.
    """

    # Lazy imports avoid introducing an import cycle with command.py.
    from engine.command import speak, takecommand

    action_type = action.action_type

    # ---------------------------------------------------------
    # STEP 1 — Voice confirmation
    # ---------------------------------------------------------

    speak(
        f"The requested action is {action_type} "
        "and requires authorization. "
        "Say 'confirm' to continue."
    )

    first_response = takecommand()

    if _is_cancelled(first_response):
        speak("Action cancelled.")
        return False

    if _normalize(first_response) not in FIRST_CONFIRMATION:
        speak(
            "Confirmation was not recognized. "
            "The action has been cancelled."
        )
        return False

    speak(
        "Confirmation accepted. "
        "Starting face authentication."
    )

    # ---------------------------------------------------------
    # STEP 2 — Face authentication
    # ---------------------------------------------------------

    try:
        face_result = recognizer.AuthenticateFace()
    except Exception as exc:
        print(
            f"Automation face authentication error: {exc}"
        )
        face_result = 0

    if face_result != 1:
        speak(
            "Face authentication failed. "
            "The action has been cancelled."
        )
        return False

    # ---------------------------------------------------------
    # STEP 3 — Authorization complete
    # ---------------------------------------------------------

    speak(
        "Face authentication successful. "
        "Authorization successful."
    )

    return True