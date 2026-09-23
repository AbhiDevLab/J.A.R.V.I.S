from __future__ import annotations

from engine.auth import recognizer


FIRST_CONFIRMATION = {
    "confirm",
}

SECOND_CONFIRMATION = {
    "confirm again",
    "confirm action again",
    "execute",
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
    return " ".join(
        str(text or "")
        .strip()
        .lower()
        .split()
    )


def _is_cancelled(text: str) -> bool:
    return _normalize(text) in CANCELLATION_PHRASES


def request_authorization(action) -> bool:
    """
    Require two explicit voice confirmations with a successful
    face authentication in between.

    Fail closed:
    any failed step means the action is cancelled.
    """

    # Lazy imports avoid introducing an import cycle with command.py.
    from engine.command import speak, takecommand

    action_type = action.action_type

    # ---------------------------------------------------------
    # STEP 1 — First voice confirmation
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
            "First confirmation was not recognized. "
            "The action has been cancelled."
        )
        return False

    speak(
        "First confirmation accepted. "
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

    speak(
        "Face authentication successful. "
        "Say 'confirm again' to execute the action."
    )

    # ---------------------------------------------------------
    # STEP 3 — Second voice confirmation
    # ---------------------------------------------------------

    second_response = takecommand()

    if _is_cancelled(second_response):
        speak("Action cancelled.")
        return False

    if _normalize(second_response) not in SECOND_CONFIRMATION:
        speak(
            "Second confirmation was not recognized. "
            "The action has been cancelled."
        )
        return False

    speak("Authorization successful.")

    return True