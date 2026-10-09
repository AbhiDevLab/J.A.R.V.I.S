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
        self._summary = ""

        summary_enabled = os.getenv("JARVIS_CONVERSATION_SUMMARY_ENABLED", "1")
        self.summary_enabled = str(summary_enabled).strip().lower() not in {
            "0", "false", "no", "off", "",
        }

        default_trigger = self.context_turns + max(4, self.context_turns // 2)
        try:
            configured_trigger = int(
                os.getenv("JARVIS_SUMMARY_TRIGGER_TURNS", str(default_trigger))
            )
        except (TypeError, ValueError):
            configured_trigger = default_trigger
        self.summary_trigger_turns = max(
            self.context_turns + 1,
            configured_trigger,
        )

        try:
            summary_max_chars = int(
                os.getenv("JARVIS_CONVERSATION_SUMMARY_MAX_CHARS", "1800")
            )
        except (TypeError, ValueError):
            summary_max_chars = 1800
        self.summary_max_chars = max(300, min(summary_max_chars, 5000))

    @staticmethod
    def _new_conversation_id() -> str:
        return str(uuid.uuid4())

    def start_new_conversation(self) -> str:
        """Start a fresh conversation and clear in-memory context."""
        self.conversation_id = self._new_conversation_id()
        self._messages.clear()
        self._summary = ""
        return self.conversation_id


    def load_conversation(
        self,
        conversation_id: str,
    ) -> bool:
        """
        Load an existing persisted conversation and make it
        the active conversation.

        Only the configured number of recent turns are retained
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
            self._summary = ""

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
        """Compress older turns and retain a bounded recent-turn window."""
        max_recent_messages = self.context_turns * 2

        if not self.summary_enabled:
            if len(self._messages) > max_recent_messages:
                self._messages = self._messages[-max_recent_messages:]
            return

        trigger_messages = self.summary_trigger_turns * 2
        if len(self._messages) <= trigger_messages:
            return

        older_messages = self._messages[:-max_recent_messages]
        if not older_messages:
            return

        try:
            from engine.conversation_summary import summarize_conversation

            updated_summary = summarize_conversation(
                self._summary,
                older_messages,
                max_chars=self.summary_max_chars,
            )
        except Exception as exc:
            # Retain raw history if even importing/calling the summarizer fails.
            print(f"Conversation compaction failed; preserving raw history: {exc}")
            return

        if not updated_summary:
            print("Conversation compaction produced no summary; preserving raw history.")
            return

        self._summary = updated_summary
        self._messages = self._messages[-max_recent_messages:]

    def get_summary(self) -> str:
        """Return the current rolling summary, primarily for tests/diagnostics."""
        return self._summary

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
            self._summary = ""

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

        if self._summary:
            lines.extend([
                "Rolling summary of earlier turns (may omit minor details):",
                self._summary,
                "",
            ])

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