"""Deterministic Phase 8 LLM retry-state tests."""

from engine.interaction_state import InteractionState
from engine.llm_recovery import resolve_pending_retry


def make_pending_state():
    state = InteractionState()
    state.set(
        "llm_retry",
        prompt="say retry or send a new request",
        action_type="retry_llm_request",
        pending_request="open my resume",
        raw_transcript="open my resumy",
        language="en",
        is_voice_input=True,
        error_category="timeout",
        previous_interaction_state={
            "state_type": "selection",
            "prompt": "Choose one of the matching files.",
            "action_type": "select_file",
            "candidates": ["C:/Reports/a.pdf", "C:/Downloads/b.pdf"],
            "data": {"description": "report"},
        },
    )
    return state


def test_explicit_retry_replays_saved_request_and_restores_dialogue_state():
    state = make_pending_state()

    result = resolve_pending_retry("Please retry", state)

    assert result.action == "retry"
    assert result.pending_request == "open my resume"
    assert result.raw_transcript == "open my resumy"
    assert result.language == "en"
    assert result.is_voice_input is True
    assert state.state_type == "selection"
    assert state.prompt == "Choose one of the matching files."
    assert state.candidates == ["C:/Reports/a.pdf", "C:/Downloads/b.pdf"]
    assert state.data["description"] == "report"


def test_cancel_clears_pending_retry_without_replaying_request():
    state = make_pending_state()

    result = resolve_pending_retry("no", state)

    assert result.action == "cancel"
    assert state.has_state() is False


def test_new_request_clears_old_retry_without_treating_it_as_approval():
    state = make_pending_state()

    result = resolve_pending_retry("What is the weather?", state)

    assert result.action == "new_request"
    assert state.has_state() is False


def test_helper_does_not_consume_non_retry_interaction_state():
    state = InteractionState()
    state.set("confirmation", prompt="Should I continue?")

    result = resolve_pending_retry("yes", state)

    assert result is None
    assert state.state_type == "confirmation"
