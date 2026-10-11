"""Phase 8.6 structured semantic intent regression tests."""

from types import SimpleNamespace

from engine.intent_classifier import SemanticIntent, classify_intent
from engine.interaction_state import InteractionState


def test_direct_open_command_is_classified_for_deterministic_routing():
    result = classify_intent("Open README.md")
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.should_route_automation is True
    assert result.normalized_query == "Open README.md"


def test_question_containing_open_is_information_not_automation():
    result = classify_intent("Which file did you just open?")
    assert result.intent is SemanticIntent.INFORMATION_REQUEST
    assert result.should_route_automation is False


def test_question_cannot_become_command_due_to_contextual_rewrite():
    interpretation = SimpleNamespace(
        query="open which.exe",
        intent="automation",
        confidence=0.99,
        needs_clarification=False,
    )
    result = classify_intent(
        "open which.exe",
        raw_text="Which file did you just open?",
        interpretation=interpretation,
    )
    assert result.intent is SemanticIntent.INFORMATION_REQUEST
    assert result.should_route_automation is False


def test_context_corrected_misheard_command_remains_automation():
    interpretation = SimpleNamespace(
        query="open my resume",
        intent="automation",
        confidence=0.94,
        needs_clarification=False,
    )
    result = classify_intent(
        "open my resume",
        raw_text="open my resumy",
        interpretation=interpretation,
    )
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.should_route_automation is True


def test_information_question_is_not_changed_into_command_by_contextual_intent():
    interpretation = SimpleNamespace(
        query="open report.pdf",
        intent="automation",
        confidence=0.96,
        needs_clarification=False,
    )
    result = classify_intent(
        "open report.pdf",
        raw_text="What file did you open?",
        interpretation=interpretation,
    )
    assert result.intent is SemanticIntent.INFORMATION_REQUEST
    assert result.should_route_automation is False


def test_pending_confirmation_requires_resolvable_high_confidence_action():
    state = InteractionState()
    state.set("confirmation", prompt="Would you like me to open report.pdf?")
    low_confidence = SimpleNamespace(
        query="yes, do it",
        intent="confirmation",
        confidence=0.42,
        needs_clarification=False,
    )
    result = classify_intent(
        "yes, do it",
        interpretation=low_confidence,
        interaction_state=state,
    )
    assert result.intent is SemanticIntent.CONFIRMATION
    assert result.needs_clarification is True
    assert result.should_route_automation is False


def test_pending_confirmation_uses_concrete_contextual_action():
    state = InteractionState()
    state.set("confirmation", prompt="Would you like me to open report.pdf?")
    interpretation = SimpleNamespace(
        query="open report.pdf",
        intent="automation",
        confidence=0.94,
        needs_clarification=False,
    )
    result = classify_intent(
        "yes, do it",
        interpretation=interpretation,
        interaction_state=state,
    )
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.normalized_query == "open report.pdf"
    assert result.should_route_automation is True


def test_pending_no_is_a_cancellation_not_a_command():
    state = InteractionState()
    state.set("confirmation", prompt="Would you like me to continue?")
    result = classify_intent("No, cancel that", interaction_state=state)
    assert result.intent is SemanticIntent.CANCELLATION
    assert result.should_route_automation is False


def test_polite_command_is_normalized_for_existing_router():
    result = classify_intent("Can you please open README.md?")
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.normalized_query == "open README.md"
    assert result.should_route_automation is True


def test_ambiguous_statement_defaults_to_conversation_not_automation():
    result = classify_intent("Maybe the README needs more work.")
    assert result.intent is SemanticIntent.CONVERSATION
    assert result.should_route_automation is False


def test_directory_listing_question_preserves_existing_directory_route():
    result = classify_intent("What's in Downloads?")
    assert result.intent is SemanticIntent.AUTOMATION
    assert result.should_route_automation is True


def test_explicit_cancellation_of_pending_clarification_is_safe():
    state = InteractionState()
    state.set("clarification", prompt="Which file do you mean?")
    result = classify_intent("cancel", interaction_state=state)
    assert result.intent is SemanticIntent.CANCELLATION
    assert result.should_route_automation is False
