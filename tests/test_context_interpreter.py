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


def test_fresh_session_target_action_is_interpreted():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query("open my resumy") is True


def test_known_application_launch_uses_fast_path_without_context():
    with patch.dict("os.environ", {"JARVIS_INTERPRETATION_MODE": "auto"}):
        assert should_interpret_query("open Chrome") is False
        assert should_interpret_query("launch VS Code.") is False


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

