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

def test_command_pipeline_uses_shared_snapshot_for_interpretation_and_response(monkeypatch):
    from engine import command, mongo_store

    command.get_interaction_state().clear()
    context = SimpleNamespace(
        memory_context="Relevant stored memory: prefers concise answers.",
        profile_context="Relevant profile: English responses.",
        interpreter_conversation_context="Conversation plus references and app state.",
        interaction_context="Pending interaction: none.",
        response_context="Conversation, memory, profile, and reference context.",
    )
    observed = {}
    conversation_manager = command.conversation_manager

    monkeypatch.setattr(command, "detect_text_language", lambda _text: "en")
    monkeypatch.setattr(
        command,
        "build_turn_intelligence_context",
        lambda query, manager: (observed.update(context_query=query, manager=manager) or context),
    )
    monkeypatch.setattr(
        command,
        "should_interpret_query",
        lambda query, **kwargs: observed.update(should_interpret=kwargs) or True,
    )

    def fake_interpret(raw, **kwargs):
        observed["interpret"] = kwargs
        return SimpleNamespace(
            query=raw,
            interpreted_query=raw,
            intent="conversation",
            confidence=0.93,
            needs_clarification=False,
            clarification_question="",
            used_context=True,
        )

    monkeypatch.setattr(command, "interpret_query", fake_interpret)
    monkeypatch.setattr(
        command,
        "classify_intent",
        lambda *args, **kwargs: SimpleNamespace(
            intent=SimpleNamespace(value="conversation"),
            confidence=0.93,
            source="integration-test",
            normalized_query="summarize it",
            should_route_automation=False,
        ),
    )
    monkeypatch.setattr(command, "load_settings", lambda: {"response_language": "auto"})
    monkeypatch.setattr(command, "_language_name", lambda _language: "English")

    def fake_prompt(query, language, context_section):
        observed["response_context"] = context_section
        return "mock prompt"

    monkeypatch.setattr(command, "build_jarvis_prompt", fake_prompt)
    monkeypatch.setattr(command, "ask_llm", lambda _prompt: "The report summary is ready.")
    monkeypatch.setattr(mongo_store, "save_chat_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(conversation_manager, "add_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(command, "extract_memories_from_turn", lambda *args, **kwargs: None)
    monkeypatch.setattr(command, "_safe_display", lambda *args, **kwargs: None)
    monkeypatch.setattr(command, "speak", lambda *args, **kwargs: False)

    command.allCommands("summarize it")

    assert observed["context_query"] == "summarize it"
    assert observed["manager"] is conversation_manager
    assert observed["should_interpret"]["conversation_context"] == context.interpreter_conversation_context
    assert observed["should_interpret"]["memory_context"] == context.memory_context
    assert observed["should_interpret"]["profile_context"] == context.profile_context
    assert observed["should_interpret"]["interaction_state"] == context.interaction_context
    assert observed["interpret"]["conversation_context"] == context.interpreter_conversation_context
    assert observed["interpret"]["memory_context"] == context.memory_context
    assert observed["interpret"]["profile_context"] == context.profile_context
    assert observed["interpret"]["interaction_state"] == context.interaction_context
    assert observed["response_context"] == context.response_context

