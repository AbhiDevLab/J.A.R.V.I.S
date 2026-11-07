"""Phase 8.9 integration tests for the shared intelligence context snapshot."""

from types import SimpleNamespace
from unittest.mock import patch

from engine.intelligence_context import build_turn_intelligence_context


class FakeConversationManager:
    def build_context(self):
        return "Conversation: user asked to open the project report."

    def get_messages(self):
        return [
            {"role": "user", "content": "Open C:\\Reports\\orion.pdf."},
            {"role": "assistant", "content": "Opened C:\\Reports\\orion.pdf."},
        ]

    def get_summary(self):
        return "The active task is reviewing the Orion report."


def test_turn_context_combines_all_relevant_sources_for_interpretation():
    state = SimpleNamespace(as_context=lambda: "Pending selection: second report.")
    with (
        patch("engine.intelligence_context.build_memory_context", return_value="Memory: prefers concise answers.") as memory,
        patch("engine.intelligence_context.build_user_profile_context", return_value="Profile: English responses.") as profile,
        patch("engine.intelligence_context.build_reference_context", return_value="References: orion.pdf.") as references,
        patch("engine.intelligence_context.build_application_activity_context", return_value="Application state: Notepad is open.") as apps,
    ):
        context = build_turn_intelligence_context(
            "summarize it",
            FakeConversationManager(),
            interaction_state=state,
        )

    assert context.memory_context == "Memory: prefers concise answers."
    assert context.profile_context == "Profile: English responses."
    assert context.conversation_context.startswith("Conversation:")
    assert context.reference_context == "References: orion.pdf."
    assert context.application_context == "Application state: Notepad is open."
    assert context.interaction_context == "Pending selection: second report."

    interpreter_context = context.interpreter_conversation_context
    assert "Conversation:" in interpreter_context
    assert "References:" in interpreter_context
    assert "Application state:" in interpreter_context
    assert "Memory:" not in interpreter_context
    assert "Profile:" not in interpreter_context

    memory.assert_called_once_with("summarize it")
    profile.assert_called_once_with("summarize it")
    references.assert_called_once()
    apps.assert_called_once()


def test_general_response_context_uses_conversation_memory_profile_and_references():
    state = SimpleNamespace(as_context=lambda: "")
    with (
        patch("engine.intelligence_context.build_memory_context", return_value="Memory: durable preference."),
        patch("engine.intelligence_context.build_user_profile_context", return_value="Profile: project context."),
        patch("engine.intelligence_context.build_reference_context", return_value="References: report.pdf."),
        patch("engine.intelligence_context.build_application_activity_context", return_value="Live app state: Notepad."),
    ):
        context = build_turn_intelligence_context(
            "what was the report?",
            FakeConversationManager(),
            interaction_state=state,
        )

    response_context = context.response_context
    assert "Conversation: user asked to open the project report." in response_context
    assert "Resolve references such as" in response_context
    assert "Memory: durable preference." in response_context
    assert "Profile: project context." in response_context
    assert "References: report.pdf." in response_context
    # Keep raw live application state out of the general response LLM prompt.
    assert "Live app state: Notepad." not in response_context


def test_empty_sources_produce_empty_prompt_contexts():
    empty_manager = SimpleNamespace(
        build_context=lambda: "",
        get_messages=lambda: [],
        get_summary=lambda: "",
    )
    state = SimpleNamespace(as_context=lambda: "")
    with (
        patch("engine.intelligence_context.build_memory_context", return_value=""),
        patch("engine.intelligence_context.build_user_profile_context", return_value=""),
        patch("engine.intelligence_context.build_reference_context", return_value=""),
        patch("engine.intelligence_context.build_application_activity_context", return_value=""),
    ):
        context = build_turn_intelligence_context(
            "hello",
            empty_manager,
            interaction_state=state,
        )

    assert context.interpreter_conversation_context == ""
    assert context.response_context == ""
