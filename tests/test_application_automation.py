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

def test_project_name_extraction_stops_at_following_fields_in_flattened_and_multiline_text(monkeypatch):
    documents = (
        "Project Name: Orion\nStatus: Phase 8 validation\nDeveloper: Abhi",
        "Project Name: Orion Status: Phase 8 validation Developer: Abhi",
        "Project Name: Orion Developer: Abhi Status: Phase 8 validation",
    )
    for document in documents:
        monkeypatch.setattr(
            executor,
            "read_application_window_text",
            lambda app, text=document: {"success": True, "content": text},
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




def test_type_text_request_routes_to_dedicated_named_application_action():
    query = "Type Phase 9.2 barge-in test successful inside opened Notepad"
    action = route_command(query)
    assert action is not None
    assert action.action_type == "type_text"
    assert action.parameters == {
        "application": "notepad",
        "text": "Phase 9.2 barge-in test successful",
    }


def test_compound_open_and_type_routes_as_ordered_application_workflow():
    query = "Open Notepad and type: Phase 9.2 barge-in test successful"
    action = route_command(query)
    assert action is not None
    assert action.action_type == "open_application_and_type"
    assert action.parameters["application"] == "notepad"
    assert action.parameters["text"] == "Phase 9.2 barge-in test successful"


def test_application_read_request_still_routes_to_accessibility_reader():
    action = route_command("Read the text inside Notepad")
    assert action is not None
    assert action.action_type == "read_application"
    assert action.parameters["application"] == "notepad"


def test_type_text_executor_uses_explicit_allowlisted_target_and_exact_body(monkeypatch):
    captured = []
    monkeypatch.setattr(
        executor,
        "type_text_into_application",
        lambda application, text: (
            captured.append((application, text))
            or {"success": True, "message": "Typed text.", "characters_typed": len(text)}
        ),
    )
    result = executor.execute_action(
        AutomationAction(
            action_type="type_text",
            parameters={"application": "notepad", "text": "Hello {JARVIS}!"},
            risk=RiskLevel.LOW,
        )
    )
    assert result["success"] is True
    assert captured == [("notepad", "Hello {JARVIS}!")]


def test_compound_open_and_type_creates_fresh_notepad_document_before_typing(monkeypatch):
    events = []
    monkeypatch.setattr(
        executor,
        "_execute_open_application",
        lambda action: (
            events.append(("open", action.parameters["application"]))
            or {"success": True, "message": "Opening Notepad."}
        ),
    )
    monkeypatch.setattr(
        executor,
        "create_new_notepad_document",
        lambda application: (
            events.append(("new_document", application))
            or {
                "success": True,
                "message": "Created and verified a new blank Notepad document.",
                "new_document_created": True,
            }
        ),
    )
    monkeypatch.setattr(
        executor,
        "_execute_type_text",
        lambda action: (
            events.append(("type", action.parameters["text"]))
            or {"success": True, "message": "Typed text.", "characters_typed": 5}
        ),
    )
    result = executor.execute_action(
        AutomationAction(
            action_type="open_application_and_type",
            parameters={
                "application": "notepad",
                "executable": "notepad.exe",
                "text": "Hello",
            },
            risk=RiskLevel.LOW,
        )
    )
    assert result["success"] is True
    assert events == [
        ("open", "notepad"),
        ("new_document", "notepad"),
        ("type", "Hello"),
    ]
    assert result["typing_completed"] is True
    assert result["new_document_created"] is True


def test_compound_open_and_type_reports_partial_success_without_claiming_typing(monkeypatch):
    monkeypatch.setattr(
        executor,
        "_execute_open_application",
        lambda action: {"success": True, "message": "Opening Notepad."},
    )
    monkeypatch.setattr(
        executor,
        "_execute_type_text",
        lambda action: {"success": False, "message": "Notepad is not in the foreground."},
    )
    result = executor._execute_open_application_and_type(
        AutomationAction(
            action_type="open_application_and_type",
            parameters={"application": "notepad", "text": "Hello"},
            risk=RiskLevel.LOW,
        )
    )
    assert result["success"] is False
    assert result["application_opened"] is True
    assert result["typing_completed"] is False



def test_windows_editor_focus_does_not_reject_document_for_flaky_uia_state_flags():
    from engine.automation.windows_apps import _focus_application_editor

    class FakeInfo:
        control_type = "Document"

    class FakeDocument:
        element_info = FakeInfo()

        def __init__(self):
            self.focused = False

        def is_visible(self):
            return False

        def is_enabled(self):
            return False

        def set_focus(self):
            self.focused = True

        def has_keyboard_focus(self):
            return self.focused

    document = FakeDocument()

    class FakeWindow:
        def descendants(self):
            return [document]

    assert _focus_application_editor(FakeWindow()) is document
    assert document.focused is True


def test_windows_editor_focus_tries_next_text_surface_when_first_cannot_focus():
    from engine.automation.windows_apps import _focus_application_editor

    class FakeControl:
        def __init__(self, control_type, can_focus):
            self.element_info = type("Info", (), {"control_type": control_type})()
            self.can_focus = can_focus
            self.focused = False

        def set_focus(self):
            if not self.can_focus:
                raise RuntimeError("control cannot be focused")
            self.focused = True

        def has_focus(self):
            return self.focused

    first = FakeControl("Edit", False)
    second = FakeControl("Document", True)

    class FakeWindow:
        def descendants(self):
            return [second, first]

    assert _focus_application_editor(FakeWindow()) is second
    assert second.focused is True


def test_text_entry_verification_requires_newly_visible_requested_text():
    from engine.automation.windows_apps import _text_entry_verified

    assert _text_entry_verified(
        "Existing note",
        "Existing note Phase 9.2 passed",
        "Phase 9.2 passed",
    )
    assert not _text_entry_verified(
        "Existing note Phase 9.2 passed",
        "Existing note Phase 9.2 passed",
        "Phase 9.2 passed",
    )
    assert not _text_entry_verified(
        "",
        "Existing note",
        "Phase 9.2 passed",
    )


def test_windows_editor_focus_rejects_control_that_does_not_gain_keyboard_focus():
    from engine.automation.windows_apps import _focus_application_editor

    class FakeControl:
        def __init__(self, control_type, gains_focus):
            self.element_info = type("Info", (), {"control_type": control_type})()
            self.gains_focus = gains_focus

        def set_focus(self):
            pass

        def has_keyboard_focus(self):
            return self.gains_focus

    stale_document = FakeControl("Edit", False)
    live_document = FakeControl("Document", True)

    class FakeWindow:
        def descendants(self):
            return [stale_document, live_document]

    assert _focus_application_editor(FakeWindow()) is live_document


def test_compound_notepad_does_not_type_when_fresh_document_cannot_be_verified(monkeypatch):
    typed = []
    monkeypatch.setattr(
        executor,
        "_execute_open_application",
        lambda action: {"success": True, "message": "Opening Notepad."},
    )
    monkeypatch.setattr(
        executor,
        "create_new_notepad_document",
        lambda application: {
            "success": False,
            "message": "Could not verify a blank document.",
        },
    )
    monkeypatch.setattr(
        executor,
        "_execute_type_text",
        lambda action: typed.append(action) or {"success": True, "message": "typed"},
    )

    result = executor._execute_open_application_and_type(
        AutomationAction(
            action_type="open_application_and_type",
            parameters={"application": "notepad", "text": "Hello"},
            risk=RiskLevel.LOW,
        )
    )

    assert result["success"] is False
    assert result["application_opened"] is True
    assert result["typing_completed"] is False
    assert typed == []


def test_editor_control_text_reader_distinguishes_blank_from_unreadable():
    from engine.automation.windows_apps import _read_editor_control_text

    class BlankEditor:
        def get_value(self):
            return ""

    class UnreadableEditor:
        def get_value(self):
            raise RuntimeError("ValuePattern unavailable")

        def window_text(self):
            raise RuntimeError("Text unavailable")

    assert _read_editor_control_text(BlankEditor()) == (True, "")
    assert _read_editor_control_text(UnreadableEditor()) == (False, "")
