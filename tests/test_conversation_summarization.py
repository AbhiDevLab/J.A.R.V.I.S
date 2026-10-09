"""Regression tests for Phase 8.4 rolling conversation summaries."""
from unittest.mock import patch

from engine.conversation import ConversationManager
from engine.conversation_summary import summarize_conversation


def _turn(index):
    return (
        f"The user asked about task {index} and file README_{index}.md.",
        f"JARVIS explained the result for task {index}.",
    )


def test_conversation_is_summarized_only_after_trigger(monkeypatch):
    monkeypatch.setenv("JARVIS_CONTEXT_TURNS", "2")
    monkeypatch.setenv("JARVIS_SUMMARY_TRIGGER_TURNS", "4")
    monkeypatch.setenv("JARVIS_CONVERSATION_SUMMARY_ENABLED", "1")
    manager = ConversationManager()

    with patch(
        "engine.conversation_summary.summarize_conversation",
        return_value="Earlier task summary.",
    ) as summarizer:
        for index in range(4):
            manager.add_turn(*_turn(index))
        summarizer.assert_not_called()

        manager.add_turn(*_turn(4))
        summarizer.assert_called_once()

    assert manager.get_summary() == "Earlier task summary."
    assert len(manager.get_messages()) == 4
    context = manager.build_context()
    assert "Rolling summary of earlier turns" in context
    assert "Earlier task summary." in context
    assert "task 3" in context
    assert "task 4" in context
    assert "User: The user asked about task 0" not in context


def test_rolling_summary_is_updated_with_previous_summary(monkeypatch):
    monkeypatch.setenv("JARVIS_CONTEXT_TURNS", "2")
    monkeypatch.setenv("JARVIS_SUMMARY_TRIGGER_TURNS", "4")
    monkeypatch.setenv("JARVIS_CONVERSATION_SUMMARY_ENABLED", "1")
    manager = ConversationManager()

    with patch(
        "engine.conversation_summary.summarize_conversation",
        side_effect=["First compact summary.", "Updated compact summary."],
    ) as summarizer:
        for index in range(5):
            manager.add_turn(*_turn(index))
        for index in range(5, 8):
            manager.add_turn(*_turn(index))

    assert summarizer.call_count == 2
    assert summarizer.call_args_list[1].args[0] == "First compact summary."
    assert manager.get_summary() == "Updated compact summary."


def test_new_conversation_clears_summary_and_recent_turns(monkeypatch):
    monkeypatch.setenv("JARVIS_CONTEXT_TURNS", "1")
    monkeypatch.setenv("JARVIS_SUMMARY_TRIGGER_TURNS", "2")
    monkeypatch.setenv("JARVIS_CONVERSATION_SUMMARY_ENABLED", "1")
    manager = ConversationManager()

    with patch(
        "engine.conversation_summary.summarize_conversation",
        return_value="Earlier context.",
    ):
        manager.add_turn("Task one.", "Result one.")
        manager.add_turn("Task two.", "Result two.")
        manager.add_turn("Task three.", "Result three.")

    assert manager.get_summary()
    manager.start_new_conversation()
    assert manager.get_summary() == ""
    assert manager.get_messages() == []
    assert manager.build_context() == ""


def test_summary_can_be_disabled_to_preserve_legacy_recent_window(monkeypatch):
    monkeypatch.setenv("JARVIS_CONTEXT_TURNS", "2")
    monkeypatch.setenv("JARVIS_SUMMARY_TRIGGER_TURNS", "4")
    monkeypatch.setenv("JARVIS_CONVERSATION_SUMMARY_ENABLED", "0")
    manager = ConversationManager()

    with patch("engine.conversation_summary.summarize_conversation") as summarizer:
        for index in range(6):
            manager.add_turn(*_turn(index))

    summarizer.assert_not_called()
    assert len(manager.get_messages()) == 4
    assert manager.get_summary() == ""


def test_llm_summary_uses_prior_summary_and_preserves_task_signals():
    messages = [
        {"role": "user", "content": "I need to finish the README before testing."},
        {"role": "assistant", "content": "The README is the next task."},
    ]
    with patch(
        "engine.conversation_summary.ask_llm",
        return_value="The user needs to finish the README before testing.",
    ) as ask:
        result = summarize_conversation(
            "The user is working on JARVIS.",
            messages,
            max_chars=500,
        )

    assert result == "The user needs to finish the README before testing."
    assert "The user is working on JARVIS." in ask.call_args.args[0]
    assert "unresolved questions" in ask.call_args.args[0]


def test_summary_falls_back_when_llm_fails_and_respects_limit():
    messages = [
        {"role": "user", "content": "Open README.md and inspect the file path."},
        {"role": "assistant", "content": "The path resolves to the project README."},
        {"role": "user", "content": "I still need to run the full test suite."},
    ]
    with patch(
        "engine.conversation_summary.ask_llm",
        side_effect=RuntimeError("temporary provider outage"),
    ):
        result = summarize_conversation(
            "The user is testing JARVIS.",
            messages,
            max_chars=420,
        )

    assert result
    assert len(result) <= 420
    assert "README.md" in result or "full test suite" in result
    assert "The user is testing JARVIS." in result


def test_empty_response_uses_extractive_fallback():
    messages = [
        {"role": "user", "content": "The deployment is blocked by DNS."},
        {"role": "assistant", "content": "Flush the resolver cache and retry."},
    ]
    with patch("engine.conversation_summary.ask_llm", return_value="   "):
        result = summarize_conversation("", messages, max_chars=500)

    assert "deployment is blocked by DNS" in result
    assert "Flush the resolver cache and retry" in result
