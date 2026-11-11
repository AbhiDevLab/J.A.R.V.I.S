"""Command-layer Phase 8.7 recovery regression tests."""

from engine import command
from engine.interaction_state import get_interaction_state
from engine.llm_client import LLMRequestError


def setup_function():
    get_interaction_state().clear()


def teardown_function():
    get_interaction_state().clear()


def test_tts_failure_keeps_text_response_available(monkeypatch):
    displays = []

    def broken_tts(*args, **kwargs):
        raise OSError("audio device unavailable")

    monkeypatch.setattr(command, "_tts_speak", broken_tts)
    monkeypatch.setattr(
        command,
        "_safe_display",
        lambda name, *args, **kwargs: displays.append((name, args)),
    )

    assert command.speak("The answer is 42.") is False
    assert displays[0][0] == "receiverText"
    assert displays[0][1][0] == "The answer is 42."
    assert displays[1][0] == "DisplayMessage"
    assert "text response remains visible" in displays[1][1][0].lower()


def test_llm_failure_preserves_pending_task_and_existing_dialogue_state(monkeypatch):
    state = get_interaction_state()
    state.set(
        "selection",
        prompt="Choose one of the matching files.",
        action_type="select_file",
        candidates=["C:/Reports/a.pdf", "C:/Downloads/b.pdf"],
        description="report",
    )
    spoken = []
    displayed = []
    recorded = []

    monkeypatch.setattr(command, "speak", lambda text, **kwargs: spoken.append(text))
    monkeypatch.setattr(
        command,
        "_safe_display",
        lambda name, *args, **kwargs: displayed.append((name, args)),
    )
    monkeypatch.setattr(
        command.conversation_manager,
        "add_turn",
        lambda user, assistant: recorded.append((user, assistant)),
    )

    command._handle_llm_failure(
        LLMRequestError(
            "provider timeout",
            category="timeout",
            retryable=True,
        ),
        query="open report.pdf",
        raw_transcript="open the report file",
        response_language="en",
        is_voice_input=True,
    )

    assert state.state_type == "llm_retry"
    assert state.data["pending_request"] == "open report.pdf"
    assert state.data["raw_transcript"] == "open the report file"
    assert state.data["error_category"] == "timeout"
    assert state.data["previous_interaction_state"]["state_type"] == "selection"
    assert recorded and recorded[0][0] == "open report.pdf"
    assert spoken and "say 'retry'" in spoken[0].lower()
    assert displayed and displayed[0][0] == "assistantResponse"



def test_pending_voice_reply_is_captured_without_another_wake_word(monkeypatch):
    captured = []
    displays = []
    monkeypatch.setattr(
        command,
        "takecommand",
        lambda **kwargs: (captured.append(kwargs) or ("Notepad", "en")),
    )
    monkeypatch.setattr(
        command,
        "_safe_display",
        lambda name, *args, **kwargs: displays.append(name),
    )
    command._continuous_listening_event.clear()

    result = command._capture_pending_voice_reply(True, "en")

    assert result == ("Notepad", "en")
    assert captured[0]["return_language"] is True
    assert captured[0]["listen_timeout"] == 10.0
    assert captured[0]["phrase_time_limit"] == 8.0
    assert "ShowSiriWave" in displays


def test_pending_voice_reply_does_not_open_mic_for_typed_turns(monkeypatch):
    def unexpected_capture(**kwargs):
        raise AssertionError("Typed turns must not open the microphone.")

    monkeypatch.setattr(command, "takecommand", unexpected_capture)
    command._continuous_listening_event.clear()

    assert command._capture_pending_voice_reply(False, "en") is None


def test_pending_voice_reply_reuses_continuous_listener_instead_of_opening_second_mic(monkeypatch):
    def unexpected_capture(**kwargs):
        raise AssertionError("Continuous Listening already owns the microphone.")

    monkeypatch.setattr(command, "takecommand", unexpected_capture)
    command._continuous_listening_event.set()
    try:
        assert command._capture_pending_voice_reply(True, "en") is None
    finally:
        command._continuous_listening_event.clear()


def test_followup_capture_timeout_preserves_pending_question_state(monkeypatch):
    state = get_interaction_state()
    state.set(
        "clarification",
        prompt="Which item would you like me to open?",
        action_type="conversation_followup",
        pending_request="open that one",
    )
    monkeypatch.setattr(command, "takecommand", lambda **kwargs: ("", ""))
    command._continuous_listening_event.clear()

    assert command._capture_pending_voice_reply(True, "en") is None
    assert state.state_type == "clarification"
    assert state.prompt == "Which item would you like me to open?"
