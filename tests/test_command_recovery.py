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
