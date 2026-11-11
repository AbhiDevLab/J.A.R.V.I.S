"""Phase 8 end-to-end regressions for cross-turn command continuation.

These tests keep the contextual interpreter, intent classifier, automation
router, action completion, and executor in the real command path. Only external
model, desktop, database, and authorization boundaries are controlled.
"""
from __future__ import annotations

import json

from engine import command
from engine.interaction_state import get_interaction_state


def setup_function():
    get_interaction_state().clear()
    command.conversation_manager.start_new_conversation()


def teardown_function():
    get_interaction_state().clear()
    command.conversation_manager.start_new_conversation()


def _patch_command_boundaries(monkeypatch):
    """Disable UI/audio and external context sources, not pipeline logic."""
    monkeypatch.setattr(command, "detect_text_language", lambda _text: "en")
    monkeypatch.setattr(command, "_safe_display", lambda *args, **kwargs: None)
    monkeypatch.setattr(command, "speak", lambda *args, **kwargs: False)
    monkeypatch.setattr(command, "record_episode", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "engine.intelligence_context.build_memory_context",
        lambda _query: "",
    )
    monkeypatch.setattr(
        "engine.intelligence_context.build_user_profile_context",
        lambda _query: "",
    )
    monkeypatch.setattr(
        "engine.intelligence_context.build_application_activity_context",
        lambda: "",
    )


def test_cross_turn_file_reference_reaches_real_router_and_executor(
    monkeypatch,
    tmp_path,
):
    _patch_command_boundaries(monkeypatch)
    report = tmp_path / "orion-project-report.pdf"
    report.write_text("test report", encoding="utf-8")

    command.conversation_manager.add_turn(
        f"The project report is located at {report}.",
        f"I will refer to {report} as the project report.",
    )

    prompts = []

    def interpret_with_reference(prompt):
        prompts.append(prompt)
        assert str(report) in prompt
        return json.dumps(
            {
                "interpreted_query": f"open the file {report}",
                "intent": "automation",
                "confidence": 0.96,
                "needs_clarification": False,
                "clarification_question": "",
            }
        )

    opened_paths = []

    monkeypatch.setattr(
        "engine.context_interpreter.ask_llm",
        interpret_with_reference,
    )
    monkeypatch.setattr(
        "engine.automation.executor.open_file",
        lambda path: (opened_paths.append(path) is None, "Opened the report."),
    )

    command.allCommands("open that report")

    assert prompts
    assert "Files and paths" in prompts[0]
    assert str(report) in prompts[0]
    assert opened_paths == [str(report.resolve())]


def test_pending_yes_resolves_delete_but_cannot_bypass_authorization(
    monkeypatch,
    tmp_path,
):
    _patch_command_boundaries(monkeypatch)
    target = tmp_path / "sensitive-draft.pdf"
    target.write_text("keep this file", encoding="utf-8")

    command.conversation_manager.add_turn(
        f"Please remove {target}.",
        f"Would you like me to delete {target}?",
    )
    get_interaction_state().set(
        "confirmation",
        prompt=f"Would you like me to delete {target}?",
        action_type="confirm_previous_task",
        pending_request=f"delete the file {target}",
    )

    def interpret_approval(prompt):
        assert "Current interaction state: confirmation" in prompt
        assert str(target) in prompt
        return json.dumps(
            {
                "interpreted_query": f"delete the file {target}",
                "intent": "automation",
                "confidence": 0.97,
                "needs_clarification": False,
                "clarification_question": "",
            }
        )

    authorization_requests = []

    def deny_authorization(action, *, require_face=True):
        authorization_requests.append((action, require_face))
        return False

    monkeypatch.setattr(
        "engine.context_interpreter.ask_llm",
        interpret_approval,
    )
    monkeypatch.setattr(
        "engine.automation.dialogue.search_paths",
        lambda _name, **_kwargs: [target],
    )
    monkeypatch.setattr(
        "engine.automation.executor.request_authorization",
        deny_authorization,
    )

    command.allCommands("yes")

    assert len(authorization_requests) == 1
    assert authorization_requests[0][0].action_type == "delete_file"
    assert authorization_requests[0][0].parameters["path"] == str(target)
    assert authorization_requests[0][1] is True
    assert target.exists()
    assert get_interaction_state().has_state() is False



def test_high_confidence_voice_stt_correction_reaches_real_router_and_executor(
    monkeypatch,
    tmp_path,
):
    """A plausible Whisper error is corrected before deterministic routing."""
    _patch_command_boundaries(monkeypatch)
    monkeypatch.setenv("JARVIS_INTERACTION_TRACES_ENABLED", "1")
    monkeypatch.setenv(
        "JARVIS_INTERACTION_TRACE_DB",
        str(tmp_path / "command-traces.sqlite3"),
    )
    raw_transcript = "open load pad"
    interpreter_prompts = []

    def interpret_with_correction(prompt):
        interpreter_prompts.append(prompt)
        assert raw_transcript in prompt
        return json.dumps(
            {
                "interpreted_query": "open Notepad",
                "intent": "automation",
                "confidence": 0.96,
                "needs_clarification": False,
                "clarification_question": "",
            }
        )

    executed_actions = []

    def capture_execution(action):
        executed_actions.append(action)
        return {"success": True, "message": "Opening Notepad."}

    monkeypatch.setattr(
        "engine.context_interpreter.ask_llm",
        interpret_with_correction,
    )
    monkeypatch.setattr(command, "execute_action", capture_execution)

    command.allCommands(
        raw_transcript,
        voice_input=True,
        detected_language="en",
    )

    assert interpreter_prompts
    assert len(executed_actions) == 1
    action = executed_actions[0]
    assert action.action_type == "open_application"
    assert action.parameters["application"] == "notepad"
    assert get_interaction_state().has_state() is False

    from engine.interaction_trace import list_recent_interaction_trace_events

    events = list_recent_interaction_trace_events()
    event_types = {event["event_type"] for event in events}
    assert {
        "turn_started",
        "interpretation_completed",
        "intent_classified",
        "automation_completed",
        "turn_completed",
    }.issubset(event_types)
    assert not any(
        "raw_transcript" in event or "prompt" in event or "path" in event
        for event in events
    )


def test_low_confidence_voice_correction_clarifies_without_executing(
    monkeypatch,
):
    """An uncertain inferred target must stop before the automation executor."""
    _patch_command_boundaries(monkeypatch)
    raw_transcript = "open load pad"
    interpreter_prompts = []

    def uncertain_interpretation(prompt):
        interpreter_prompts.append(prompt)
        assert raw_transcript in prompt
        return json.dumps(
            {
                "interpreted_query": "open Notepad",
                "intent": "automation",
                "confidence": 0.61,
                "needs_clarification": False,
                "clarification_question": "",
            }
        )

    executed_actions = []
    monkeypatch.setattr(
        "engine.context_interpreter.ask_llm",
        uncertain_interpretation,
    )
    monkeypatch.setattr(
        command,
        "execute_action",
        lambda action: executed_actions.append(action),
    )

    command.allCommands(
        raw_transcript,
        voice_input=True,
        detected_language="en",
    )

    state = get_interaction_state()
    assert interpreter_prompts
    assert executed_actions == []
    assert state.state_type == "clarification"
    assert "clarify" in state.prompt.casefold() or "repeat" in state.prompt.casefold()



def test_relevant_memory_and_profile_reach_interpreter_and_answer_model(
    monkeypatch,
    tmp_path,
):
    """Real SQLite memory retrieval must reach interpretation and response."""
    _patch_command_boundaries(monkeypatch)
    monkeypatch.setenv("JARVIS_INTERPRETATION_MODE", "auto")
    from engine import memory as memory_module
    from engine.memory import build_memory_context
    from engine.user_context import (
        build_user_profile_context,
        save_profile_item,
    )

    store = memory_module.MemoryStore(tmp_path / "intelligence-memory.sqlite3", enabled=True)
    monkeypatch.setattr(memory_module, "memory_store", store)
    saved_memory = store.save_memory(
        "The user is building a Python desktop assistant project.",
        key="project.desktop_assistant",
        confidence=0.98,
        importance=4,
    )
    saved_profile = save_profile_item(
        "communication",
        "response_style",
        "The user prefers concise technical explanations.",
        confidence=0.98,
        importance=4,
    )
    assert saved_memory is not None
    assert saved_profile is not None

    interpreter_prompts = []
    answer_prompts = []

    def interpret_with_context(prompt):
        interpreter_prompts.append(prompt)
        assert "Python desktop assistant project" in prompt
        assert "concise technical explanations" in prompt
        return json.dumps(
            {
                "interpreted_query": (
                    "How should you give concise technical explanations "
                    "about my desktop assistant project?"
                ),
                "intent": "conversation",
                "confidence": 0.96,
                "needs_clarification": False,
                "clarification_question": "",
            }
        )

    def answer_with_context(prompt):
        answer_prompts.append(prompt)
        return (
            "I will use concise technical explanations for your "
            "desktop assistant project."
        )

    monkeypatch.setattr(
        "engine.intelligence_context.build_memory_context",
        build_memory_context,
    )
    monkeypatch.setattr(
        "engine.intelligence_context.build_user_profile_context",
        build_user_profile_context,
    )
    monkeypatch.setattr(
        "engine.context_interpreter.ask_llm",
        interpret_with_context,
    )
    monkeypatch.setattr(command, "ask_llm", answer_with_context)
    monkeypatch.setattr(command, "load_settings", lambda: {"response_language": "en"})
    monkeypatch.setattr(command, "extract_memories_from_turn", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "engine.mongo_store.save_chat_turn",
        lambda *args, **kwargs: None,
    )

    command.allCommands(
        "How should you give concise technical explanations about my desktop assistant project?",
        voice_input=True,
        detected_language="en",
    )

    assert len(interpreter_prompts) == 1
    assert len(answer_prompts) == 1
    assert "Python desktop assistant project" in answer_prompts[0]
    assert "concise technical explanations" in answer_prompts[0]

def test_genuinely_ambiguous_voice_request_keeps_clarification_and_never_executes(
    monkeypatch,
):
    """An unresolved target must remain a clarification, not become an action."""
    _patch_command_boundaries(monkeypatch)
    raw_transcript = "open that one"
    interpreter_prompts = []
    executed_actions = []

    def request_clarification(prompt):
        interpreter_prompts.append(prompt)
        assert raw_transcript in prompt
        return json.dumps(
            {
                "interpreted_query": raw_transcript,
                "intent": "clarification",
                "confidence": 0.42,
                "needs_clarification": True,
                "clarification_question": "Which application or file do you mean?",
            }
        )

    monkeypatch.setattr(
        "engine.context_interpreter.ask_llm",
        request_clarification,
    )
    monkeypatch.setattr(
        command,
        "execute_action",
        lambda action: executed_actions.append(action),
    )

    command.allCommands(
        raw_transcript,
        voice_input=True,
        detected_language="en",
    )

    state = get_interaction_state()
    assert interpreter_prompts
    assert executed_actions == []
    assert state.state_type == "clarification"
    assert state.prompt == "Which application or file do you mean?"


def test_interpreter_provider_failure_preserves_pending_context_for_retry(
    monkeypatch,
):
    """A provider error must preserve the request and previous dialogue state."""
    _patch_command_boundaries(monkeypatch)
    report_choices = ["C:/Reports/alpha.pdf", "C:/Downloads/beta.pdf"]
    get_interaction_state().set(
        "selection",
        prompt="Which report should I open?",
        action_type="select_file",
        candidates=report_choices,
        description="project report",
    )

    def fail_interpretation(_prompt):
        from engine.llm_client import LLMRequestError

        raise LLMRequestError(
            "provider timeout",
            category="timeout",
            retryable=True,
        )

    monkeypatch.setattr(
        "engine.context_interpreter.ask_llm",
        fail_interpretation,
    )

    command.allCommands(
        "the one in Downloads",
        voice_input=True,
        detected_language="en",
    )

    state = get_interaction_state()
    assert state.state_type == "llm_retry"
    assert state.data["pending_request"] == "the one in Downloads"
    assert state.data["raw_transcript"] == "the one in Downloads"
    assert state.data["previous_interaction_state"]["state_type"] == "selection"
    assert state.data["previous_interaction_state"]["candidates"] == report_choices
