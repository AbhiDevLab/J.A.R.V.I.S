"""Regression tests for Phase 8.5 contextual follow-up resolution."""

from types import SimpleNamespace
from unittest.mock import patch

from engine.automation.dialogue import _interpret_dialogue_response
from engine.interaction_state import get_interaction_state


def setup_function():
    get_interaction_state().clear()


def teardown_function():
    get_interaction_state().clear()


def test_explicit_ordinal_selection_is_resolved_without_llm():
    state = get_interaction_state()
    state.set(
        "selection",
        prompt="select one of the matching files",
        candidates=[r"C:\\Reports\\alpha.pdf", r"C:\\Reports\\beta.pdf"],
    )

    with patch("engine.automation.dialogue.interpret_query") as interpret:
        assert _interpret_dialogue_response("the second one") == "2"

    interpret.assert_not_called()


def test_numeric_choice_with_wrapper_is_resolved_without_llm():
    state = get_interaction_state()
    state.set(
        "selection",
        prompt="select one of the matching files",
        candidates=["alpha.pdf", "beta.pdf", "gamma.pdf"],
    )

    with patch("engine.automation.dialogue.interpret_query") as interpret:
        assert _interpret_dialogue_response("option 3") == "3"

    interpret.assert_not_called()


def test_all_choice_and_cancellation_are_preserved():
    state = get_interaction_state()
    state.set(
        "selection_or_all",
        prompt="select a file or choose all",
        candidates=["alpha.pdf", "beta.pdf"],
    )

    with patch("engine.automation.dialogue.interpret_query") as interpret:
        assert _interpret_dialogue_response("all") == "all"
        assert _interpret_dialogue_response("no") == "no"

    interpret.assert_not_called()


def test_descriptive_ambiguous_reply_uses_pending_state_context():
    state = get_interaction_state()
    state.set(
        "selection",
        prompt="select one of the matching files",
        candidates=[r"C:\\Reports\\alpha.pdf", r"C:\\Downloads\\beta.pdf"],
        description="report",
    )
    model_result = SimpleNamespace(query=r"C:\\Downloads\\beta.pdf")

    with patch(
        "engine.automation.dialogue.interpret_query",
        return_value=model_result,
    ) as interpret:
        resolved = _interpret_dialogue_response("the one in Downloads")

    assert resolved == r"C:\\Downloads\\beta.pdf"
    assert "Available choices" in interpret.call_args.kwargs["interaction_state"]
    assert "Downloads" in interpret.call_args.kwargs["interaction_state"]


def test_invalid_ordinal_is_not_silently_mapped_to_a_candidate():
    state = get_interaction_state()
    state.set(
        "selection",
        prompt="select one of the matching files",
        candidates=["alpha.pdf", "beta.pdf"],
    )

    with patch(
        "engine.automation.dialogue.interpret_query",
        return_value=SimpleNamespace(query="the tenth one"),
    ) as interpret:
        assert _interpret_dialogue_response("the tenth one") == "the tenth one"

    interpret.assert_called_once()
