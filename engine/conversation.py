"""
J.A.R.V.I.S. conversation context manager.

Responsibilities:
- Create and maintain a conversation ID for the current JARVIS session.
- Maintain recent messages in memory.
- Retrieve previous turns from MongoDB when available.
- Build a compact LLM-ready conversation context.
- Start a new conversation when requested.

This module intentionally keeps conversation state separate from
engine.command.py so the conversational layer can evolve independently.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List


class ConversationManager:
    """Manage the active JARVIS conversation and its recent context."""

    def __init__(self) -> None:
        self.conversation_id = self._new_conversation_id()
        self._messages: List[Dict[str, str]] = []

        try:
            context_turns = int(
                os.getenv("JARVIS_CONTEXT_TURNS", "8")
            )
        except (TypeError, ValueError):
            context_turns = 8

        self.context_turns = max(1, context_turns)

    @staticmethod
    def _new_conversation_id() -> str:
        return str(uuid.uuid4())

    def start_new_conversation(self) -> str:
        """Start a fresh conversation and clear in-memory context."""
        self.conversation_id = self._new_conversation_id()
        self._messages.clear()
        return self.conversation_id
    
        def load_conversation(
        self,
        conversation_id: str,
    ) -> bool:
            """
            Load an existing persisted conversation and make it
            the active conversation.

            The full conversation is fetched from MongoDB, while
            only the configured number of recent turns are retained
            in memory for LLM context.
            """
        if not conversation_id:
            return False

        try:
            from engine.mongo_store import get_conversation

            turns = get_conversation(
                conversation_id
            )

            if not turns:
                return False

            self.conversation_id = conversation_id
            self._messages.clear()

            for turn in turns:
                user_text = turn.get(
                    "user_text",
                    "",
                )

                assistant_text = turn.get(
                    "assistant_text",
                    "",
                )

                if user_text:
                    self._messages.append(
                        {
                            "role": "user",
                            "content": str(user_text),
                        }
                    )

                if assistant_text:
                    self._messages.append(
                        {
                            "role": "assistant",
                            "content": str(assistant_text),
                        }
                    )

            self._trim_messages()

            return True

        except Exception as exc:
            print(
                f"Conversation loading error: {exc}"
            )
            return False

    def add_turn(
        self,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Add one completed user/assistant turn to session memory."""
        if user_text:
            self._messages.append(
                {
                    "role": "user",
                    "content": str(user_text),
                }
            )

        if assistant_text:
            self._messages.append(
                {
                    "role": "assistant",
                    "content": str(assistant_text),
                }
            )

        self._trim_messages()

    def _trim_messages(self) -> None:
        """Keep only the configured number of conversational turns."""
        max_messages = self.context_turns * 2

        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

    def load_persistent_context(self) -> None:
        """
        Load recent turns for this conversation from MongoDB.

        This is intentionally optional. If MongoDB is unavailable, the
        active session continues using in-memory context only.
        """
        try:
            from engine.mongo_store import get_chat_turns

            turns = get_chat_turns(
                conversation_id=self.conversation_id,
                limit=self.context_turns,
            )

            self._messages.clear()

            for turn in turns:
                user_text = turn.get("user_text", "")
                assistant_text = turn.get("assistant_text", "")

                if user_text:
                    self._messages.append(
                        {
                            "role": "user",
                            "content": str(user_text),
                        }
                    )

                if assistant_text:
                    self._messages.append(
                        {
                            "role": "assistant",
                            "content": str(assistant_text),
                        }
                    )

            self._trim_messages()

        except Exception as exc:
            print(
                f"Conversation persistence unavailable: {exc}"
            )

    def get_messages(self) -> List[Dict[str, str]]:
        """Return a copy of the recent conversation messages."""
        return list(self._messages)

    def build_context(self) -> str:
        """
        Convert recent conversation messages into an LLM-friendly block.

        Returns an empty string when no previous context exists.
        """
        if not self._messages:
            return ""

        lines = [
            "Previous conversation context:",
            "",
        ]

        for message in self._messages:
            role = message["role"]

            if role == "user":
                speaker = "User"
            else:
                speaker = "JARVIS"

            lines.append(
                f"{speaker}: {message['content']}"
            )

        return "\n".join(lines)

    def has_context(self) -> bool:
        """Return True when previous conversational context exists."""
        return bool(self._messages)


# One active conversation manager per JARVIS process.
conversation_manager = ConversationManager()


def get_conversation_manager() -> ConversationManager:
    """Return the active conversation manager."""
    return conversation_manager

def load_conversation(
    conversation_id: str,
) -> bool:
    """Load a saved conversation into the active session."""
    return conversation_manager.load_conversation(
        conversation_id
    )

def list_saved_conversations(
    limit: int = 20,
):
    """Return recent persisted conversations."""
    try:
        from engine.mongo_store import (
            get_recent_conversations,
        )

        return get_recent_conversations(limit)

    except Exception as exc:
        print(
            f"Conversation history unavailable: {exc}"
        )
        return []


def load_saved_conversation(
    conversation_id: str,
):
    """Load one persisted conversation from MongoDB."""
    try:
        from engine.mongo_store import (
            get_conversation,
        )

        return get_conversation(
            conversation_id
        )

    except Exception as exc:
        print(
            f"Conversation loading error: {exc}"
        )
        return []