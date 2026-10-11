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



def test_cross_turn_reference_index_surfaces_files_apps_people_tasks_and_answers():
    from engine.reference_resolver import build_reference_context

    messages = [
        {"role": "user", "content": "Open the report.pdf in Downloads."},
        {"role": "assistant", "content": "Opened C:\\Users\\Abhi\\Downloads\\report.pdf."},
        {"role": "user", "content": "Use VS Code for this project."},
        {"role": "assistant", "content": "VS Code is the editor we will use for this project."},
        {"role": "user", "content": "Send a message to Alice."},
        {"role": "assistant", "content": "What message should I send to Alice?"},
    ]

    context = build_reference_context(messages, summary="The user is working on a project README.")

    assert "report.pdf" in context
    assert "C:\\Users\\Abhi\\Downloads\\report.pdf" in context
    assert "VS Code" in context
    assert "vscode" in context.lower()
    assert "Alice" in context
    assert "Recent user tasks" in context
    assert "Recent JARVIS answers" in context


def test_pending_confirmation_yes_is_resolved_against_pending_task_context():
    from engine.context_interpreter import interpret_query
    from engine.reference_resolver import (
        assistant_requests_confirmation,
        is_clear_affirmative_confirmation,
        is_clear_negative_confirmation,
    )

    state = get_interaction_state()
    pending_question = "Would you like me to open report.pdf?"
    state.set(
        "confirmation",
        prompt=pending_question,
        action_type="confirm_previous_task",
        pending_request="open report.pdf",
    )

    assert assistant_requests_confirmation(pending_question) is True
    assert is_clear_affirmative_confirmation("Yes, do it") is True
    assert is_clear_negative_confirmation("No, cancel that") is True

    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"open report.pdf","intent":"automation","confidence":0.94,"needs_clarification":false,"clarification_question":""}',
    ) as ask_llm:
        result = interpret_query(
            "yes, do it",
            conversation_context="Previous conversation context: User asked to open report.pdf.",
            interaction_state=state.as_context(),
        )

    assert result.query == "open report.pdf"
    assert "pending_request: open report.pdf" in ask_llm.call_args.args[0]


def test_unresolvable_pending_confirmation_does_not_require_guessing():
    from engine.reference_resolver import (
        is_clear_affirmative_confirmation,
        is_clear_negative_confirmation,
    )

    assert is_clear_affirmative_confirmation("go ahead") is True
    assert is_clear_negative_confirmation("never mind") is True
    assert is_clear_affirmative_confirmation("open Chrome") is False
    assert is_clear_negative_confirmation("open Chrome") is False
