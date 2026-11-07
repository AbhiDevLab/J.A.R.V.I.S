"""Phase 8 desktop application close/read automation regressions."""
from engine.automation.actions import AutomationAction, RiskLevel
from engine.automation import executor
from engine.automation.router import route_command
from engine.automation import application_state
from engine.intent_classifier import SemanticIntent, classify_intent


def test_close_known_application_routes_to_graceful_close_action():
    action = route_command("close notepad")
    assert action is not None
    assert action.action_type == "close_application"
    assert action.parameters["application"] == "notepad"


def test_close_alias_routes_to_canonical_application():
    action = route_command("please close Google Chrome")
    assert action is not None
    assert action.action_type == "close_application"
    assert action.parameters["application"] == "chrome"


def test_close_unknown_application_is_not_guessed():
    assert route_command("close the application I used earlier") is None


def test_hinglish_open_and_close_commands_are_routed_deterministically():
    open_action = route_command("notepad open karna hai")
    close_action = route_command("is notepad ko band karna hai")
    assert open_action is not None
    assert open_action.action_type == "open_application"
    assert open_action.parameters["application"] == "notepad"
    assert close_action is not None
    assert close_action.action_type == "close_application"
    assert close_action.parameters["application"] == "notepad"


def test_read_application_content_request_routes_to_accessibility_reader():
    action = route_command(
        "Can you give me the content inside the notepad you opened earlier?"
    )
    assert action is not None
    assert action.action_type == "read_application"
    assert action.parameters["application"] == "notepad"


def test_written_text_question_routes_to_reader_before_directory_listing():
    action = route_command("What is written in Notepad?")
    assert action is not None
    assert action.action_type == "read_application"


def test_general_question_about_notepad_remains_conversational():
    assert route_command("Tell me about Notepad") is None


def test_classifier_routes_close_command_even_after_interpretation():
    result = classify_intent(
        "Closing Notepad",
        raw_text="close notepad",
    )
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.should_route_automation is True
    assert result.normalized_query == "close notepad"


def test_classifier_routes_application_content_questions():
    result = classify_intent(
        "What is written in Notepad?",
        raw_text="What is written in Notepad?",
    )
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.should_route_automation is True


def test_classifier_does_not_turn_general_notepad_question_into_read_action():
    result = classify_intent(
        "What can you tell me about Notepad?",
        raw_text="What can you tell me about Notepad?",
    )
    assert result.intent is SemanticIntent.INFORMATION_REQUEST
    assert result.should_route_automation is False


def test_executor_close_records_closed_only_when_window_is_gone(monkeypatch):
    application_state.clear_application_activity()
    recorded = []
    monkeypatch.setattr(
        executor,
        "close_application_window",
        lambda app: {"success": True, "message": "Notepad is now closed.", "still_open": False},
    )
    monkeypatch.setattr(
        executor,
        "record_application_closed",
        lambda app: recorded.append(app),
    )
    result = executor.execute_action(
        AutomationAction(
            action_type="close_application",
            parameters={"application": "notepad"},
            risk=RiskLevel.LOW,
        )
    )
    assert result["success"] is True
    assert recorded == ["notepad"]


def test_executor_does_not_record_app_closed_when_other_window_remains(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        executor,
        "close_application_window",
        lambda app: {"success": True, "message": "One window remains.", "still_open": True},
    )
    monkeypatch.setattr(
        executor,
        "record_application_closed",
        lambda app: recorded.append(app),
    )
    result = executor.execute_action(
        AutomationAction(
            action_type="close_application",
            parameters={"application": "notepad"},
            risk=RiskLevel.LOW,
        )
    )
    assert result["success"] is True
    assert recorded == []


def test_executor_returns_accessibility_content_without_reinterpreting_it(monkeypatch):
    expected = {
        "success": True,
        "content": "Meeting starts at 10.",
        "message": "Text currently visible in Notepad:\n\nMeeting starts at 10.",
        "spoken_message": "I read the text currently visible in Notepad and displayed it.",
        "summary": "Read the current visible text from Notepad.",
    }
    monkeypatch.setattr(
        executor,
        "read_application_window_text",
        lambda app: expected,
    )
    result = executor.execute_action(
        AutomationAction(
            action_type="read_application",
            parameters={"application": "notepad"},
            risk=RiskLevel.LOW,
        )
    )
    assert result == expected


def test_what_is_in_notepad_question_routes_to_window_reader():
    action = route_command("What is in Notepad?")
    assert action is not None
    assert action.action_type == "read_application"


def test_classifier_preserves_original_app_content_request_for_router():
    result = classify_intent(
        "Tell me about Notepad",
        raw_text="What is in Notepad?",
    )
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.normalized_query == "What is in Notepad?"
    assert result.should_route_automation is True


def test_project_name_question_routes_to_application_reader():
    action = route_command("What is my project name in Notepad?")
    assert action is not None
    assert action.action_type == "read_application"
    assert action.parameters["application"] == "notepad"
    assert action.parameters["question"] == "What is my project name in Notepad?"


def test_project_name_question_without_document_evidence_does_not_guess_memory(monkeypatch):
    monkeypatch.setattr(
        executor,
        "read_application_window_text",
        lambda app: {
            "success": True,
            "content": (
                "Experiment 1 — Introduction & Classical vs Quantum.\n"
                "Experiment 2 — Core Concept: Superposition and Interference."
            ),
            "message": "read",
        },
    )
    monkeypatch.setattr(
        executor,
        "ask_llm",
        lambda prompt: (_ for _ in ()).throw(AssertionError("Project name must use deterministic evidence check.")),
    )
    result = executor.execute_action(
        AutomationAction(
            action_type="read_application",
            parameters={
                "application": "notepad",
                "question": "What is my project name in Notepad?",
            },
            risk=RiskLevel.LOW,
        )
    )
    assert result["success"] is True
    assert "does not explicitly state a project name" in result["answer"]


def test_project_name_question_extracts_explicit_document_value(monkeypatch):
    monkeypatch.setattr(
        executor,
        "read_application_window_text",
        lambda app: {"success": True, "content": "Project Name: Orion\nStatus: Active"},
    )
    result = executor.execute_action(
        AutomationAction(
            action_type="read_application",
            parameters={
                "application": "notepad",
                "question": "What is my project name in Notepad?",
            },
            risk=RiskLevel.LOW,
        )
    )
    assert result["success"] is True
    assert result["answer"] == "The project name shown in Notepad is Orion."


def test_specific_application_question_classifier_routes_despite_question_shape():
    result = classify_intent(
        "What is my project name in Notepad?",
        raw_text="What is my project name in Notepad?",
    )
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.should_route_automation is True


def test_general_application_description_question_stays_conversational():
    result = classify_intent(
        "What can you tell me about Notepad?",
        raw_text="What can you tell me about Notepad?",
    )
    assert result.intent is SemanticIntent.INFORMATION_REQUEST
    assert result.should_route_automation is False
