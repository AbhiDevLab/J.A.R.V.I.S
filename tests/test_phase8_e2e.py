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

    def deny_authorization(action):
        authorization_requests.append(action)
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
    assert authorization_requests[0].action_type == "delete_file"
    assert authorization_requests[0].parameters["path"] == str(target)
    assert target.exists()
    assert get_interaction_state().has_state() is False
