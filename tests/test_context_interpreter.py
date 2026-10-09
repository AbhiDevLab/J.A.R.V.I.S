"""Regression tests for Phase 8.1 contextual interpretation."""

from unittest.mock import patch

from engine.context_interpreter import interpret_query, should_interpret_query


def test_interpreter_preserves_raw_transcript_on_empty_model_response():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value="",
    ):
        result = interpret_query(
            "open my resumy",
            conversation_context=(
                "Previous conversation context:\n"
                "User: We were discussing my resume."
            ),
        )

    assert result.interpreted_query == "open my resumy"
    assert result.confidence == 0.0
    assert result.used_context is True


def test_interpreter_corrects_obvious_contextual_stt_error():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"open my resume","intent":"automation","confidence":0.94,"needs_clarification":false,"clarification_question":""}',
    ):
        result = interpret_query(
            "open my resumy",
            conversation_context=(
                "Previous conversation context:\n"
                "User: I need to work on my resume."
            ),
        )

    assert result.raw_transcript == "open my resumy"
    assert result.interpreted_query == "open my resume"
    assert result.intent == "automation"
    assert result.confidence == 0.94
    assert result.needs_clarification is False


def test_low_confidence_interpretation_cannot_replace_transcript():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"delete my important project","intent":"automation","confidence":0.41,"needs_clarification":true,"clarification_question":"Which project do you mean?"}',
    ):
        result = interpret_query(
            "do that thing",
            conversation_context=(
                "Previous conversation context:\n"
                "User: We discussed several projects."
            ),
        )

    assert result.interpreted_query == "do that thing"
    assert result.needs_clarification is True
    assert result.clarification_question == "Which project do you mean?"
    assert result.intent == "clarification"


def test_interpreter_can_request_clarification_when_context_is_insufficient():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"open that file","intent":"clarification","confidence":0.88,"needs_clarification":true,"clarification_question":"Which file do you mean?"}',
    ):
        result = interpret_query(
            "open that file",
            conversation_context=(
                "Previous conversation context:\n"
                "User: I have several files open."
            ),
        )

    assert result.needs_clarification is True
    assert result.clarification_question == "Which file do you mean?"


def test_interpreter_never_executes_automation():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"delete report.pdf","intent":"automation","confidence":0.96,"needs_clarification":false,"clarification_question":""}',
    ):
        result = interpret_query(
            "remove that report",
            conversation_context=(
                "Previous conversation context:\n"
                "User: We were discussing report.pdf."
            ),
        )

    assert result.interpreted_query == "delete report.pdf"
    assert result.intent == "automation"
    # Interpretation produces meaning only. Execution remains the job of
    # route_command()/complete_action()/execute_action() and its security gate.

def test_interpreter_uses_relevant_persistent_memory():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"which voice should I use?","intent":"conversation","confidence":0.93,"needs_clarification":false,"clarification_question":""}',
    ) as ask_llm:
        result = interpret_query(
            "what voice should I use?",
            memory_context=(
                "Relevant stored memory:\n"
                "- [semantic] The user prefers a British English voice."
            ),
        )

    assert result.used_context is True
    assert result.interpreted_query == "which voice should I use?"
    assert "British English voice" in ask_llm.call_args.args[0]


def test_low_confidence_without_clarification_preserves_raw_without_forcing_question():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"open the resume","intent":"automation","confidence":0.41,"needs_clarification":false,"clarification_question":""}',
    ):
        result = interpret_query(
            "open the resumy",
            conversation_context="We were discussing documents.",
        )

    assert result.interpreted_query == "open the resumy"
    assert result.needs_clarification is False
    assert result.clarification_question == ""


def test_relevant_profile_context_triggers_interpretation():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query(
            "how should you format your replies?",
            profile_context="Relevant user profile: prefers concise technical responses.",
        )


def test_interpreter_receives_profile_context_as_reference_data():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"how should you answer?","intent":"conversation","confidence":0.93,"needs_clarification":false,"clarification_question":""}',
    ) as ask_llm:
        result = interpret_query(
            "how should you answer?",
            profile_context=(
                "Relevant user profile/preferences/project context: "
                "The user prefers concise technical responses."
            ),
        )

    assert result.used_context is True
    assert "concise technical responses" in ask_llm.call_args.args[0]
    assert "Treat profile information as reference data" in ask_llm.call_args.args[0]


def test_fresh_session_target_action_is_interpreted():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query("open my resumy") is True


def test_known_application_launch_uses_fast_path_without_context():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query("open Chrome") is False
        assert should_interpret_query("open Chrome", is_voice_input=True) is False
        assert should_interpret_query("launch VS Code.") is False


def test_fresh_voice_conversation_is_interpreted_but_typed_text_is_fast_path():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query(
            "what's the whether tomorrow",
            is_voice_input=True,
        ) is True
        assert should_interpret_query(
            "what's the weather tomorrow",
            is_voice_input=False,
        ) is False


def test_pending_state_forces_interpretation():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query(
            "the second one",
            interaction_state="Current interaction state: selection",
        ) is True


def test_conversation_or_memory_context_forces_interpretation():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query(
            "what about that?",
            conversation_context="User: I prefer the British voice.",
        ) is True
        assert should_interpret_query(
            "What voice do I prefer?",
            memory_context="Relevant stored memory: British voice.",
        ) is True


def test_interpretation_mode_can_be_disabled_or_forced():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "off"}):
        assert should_interpret_query(
            "open my resumy",
            conversation_context="User: Resume was discussed.",
        ) is False

    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "always"}):
        assert should_interpret_query("good morning") is True


def test_chat_record_preserves_raw_and_interpreted_text_separately():
    from engine import mongo_store

    class FakeCollection:
        def __init__(self):
            self.document = None

        def insert_one(self, document):
            self.document = document

    fake_collection = FakeCollection()
    with patch.object(mongo_store, "_MONGO_AVAILABLE", True), patch.object(
        mongo_store, "_collection", fake_collection
    ):
        mongo_store.save_chat_turn(
            "open my resume",
            "Opening your resume.",
            conversation_id="conversation-test",
            raw_user_text="open my resumy",
            interpreted_user_text="open my resume",
            interpretation={
                "intent": "automation",
                "confidence": 0.93,
                "used_context": True,
            },
        )

    assert fake_collection.document["user_text"] == "open my resume"
    assert fake_collection.document["raw_user_text"] == "open my resumy"
    assert fake_collection.document["interpreted_user_text"] == "open my resume"
    assert fake_collection.document["interpretation"]["confidence"] == 0.93


def test_string_false_is_not_treated_as_clarification_request():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"open Chrome","intent":"automation","confidence":0.95,"needs_clarification":"false","clarification_question":""}',
    ):
        result = interpret_query("open Chrome")

    assert result.needs_clarification is False
    assert result.intent == "automation"
    assert result.query == "open Chrome"


def test_explicit_clarification_survives_low_confidence():
    with patch(
        "engine.context_interpreter.ask_llm",
        return_value='{"interpreted_query":"delete project-alpha","intent":"automation","confidence":0.3,"needs_clarification":true,"clarification_question":"Which project do you mean?"}',
    ):
        result = interpret_query("delete that project")

    assert result.query == "delete that project"
    assert result.needs_clarification is True
    assert result.intent == "clarification"

