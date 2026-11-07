"""Shared per-turn context assembly for the Phase 8 intelligence pipeline.

This module keeps the context supplied to interpretation and response generation
consistent while preserving the privacy boundary between transient desktop text
and persistent conversation/memory context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.automation.application_state import build_application_activity_context
from engine.interaction_state import get_interaction_state
from engine.memory import build_memory_context
from engine.reference_resolver import build_reference_context
from engine.user_context import build_user_profile_context


@dataclass(frozen=True)
class TurnIntelligenceContext:
    """Context snapshot assembled once for one user turn."""

    memory_context: str = ""
    profile_context: str = ""
    conversation_context: str = ""
    reference_context: str = ""
    application_context: str = ""
    interaction_context: str = ""

    @property
    def interpreter_conversation_context(self) -> str:
        """Conversation plus bounded references and verified app activity."""
        return "\n\n".join(
            part
            for part in (
                self.conversation_context,
                self.reference_context,
                self.application_context,
            )
            if part
        )

    @property
    def response_context(self) -> str:
        """Build the existing LLM context without injecting live app-state text."""
        parts = []
        if self.conversation_context:
            parts.append(
                f"""
{self.conversation_context}

Use the previous conversation only when it is relevant to the current query.
Resolve references such as "it", "that", "this", "the previous one", and follow-up
questions using that context.
""".strip()
            )
        if self.memory_context:
            parts.append(self.memory_context)
        if self.profile_context:
            parts.append(self.profile_context)
        if self.reference_context:
            parts.append(self.reference_context)
        return "\n\n".join(parts)


def build_turn_intelligence_context(
    query: str,
    conversation_manager: Any,
    *,
    interaction_state: Any = None,
) -> TurnIntelligenceContext:
    """Capture the relevant context sources once for the current user turn.

    The application activity snapshot is supplied to contextual interpretation,
    where it can help resolve references to open/closed applications. It is
    deliberately excluded from the general response prompt. Extracted document
    contents are never added here; they remain transient in the read-application
    action result.
    """
    active_state = interaction_state or get_interaction_state()
    return TurnIntelligenceContext(
        memory_context=build_memory_context(query),
        profile_context=build_user_profile_context(query),
        conversation_context=conversation_manager.build_context(),
        reference_context=build_reference_context(
            conversation_manager.get_messages(),
            summary=conversation_manager.get_summary(),
        ),
        application_context=build_application_activity_context(),
        interaction_context=active_state.as_context(),
    )
