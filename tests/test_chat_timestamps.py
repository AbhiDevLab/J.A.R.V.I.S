"""Regression tests for per-message timestamps in saved J.A.R.V.I.S chats."""
from pathlib import Path

from engine import mongo_store


ROOT = Path(__file__).resolve().parents[1]


class CapturingCollection:
    def __init__(self):
        self.document = None

    def insert_one(self, document):
        self.document = document


def test_save_chat_turn_persists_user_and_assistant_timestamps(monkeypatch):
    collection = CapturingCollection()
    user_timestamp = "2026-10-11T05:30:12.123+00:00"
    assistant_timestamp = "2026-10-11T05:30:14.456+00:00"

    monkeypatch.setattr(mongo_store, "_MONGO_AVAILABLE", True)
    monkeypatch.setattr(mongo_store, "_collection", collection)

    mongo_store.save_chat_turn(
        "What time is it?",
        "It is 11:00 AM.",
        conversation_id="timestamp-test",
        user_timestamp=user_timestamp,
        assistant_timestamp=assistant_timestamp,
    )

    assert collection.document is not None
    assert collection.document["timestamp"] == assistant_timestamp
    assert collection.document["user_timestamp"] == user_timestamp
    assert collection.document["assistant_timestamp"] == assistant_timestamp


def test_timestamp_ui_covers_live_and_loaded_messages():
    controller = (ROOT / "www" / "controller.js").read_text(encoding="utf-8")
    command = (ROOT / "engine" / "command.py").read_text(encoding="utf-8")

    assert "function messageTimestampMarkup(timestamp)" in controller
    assert "timeZoneName: \"short\"" in controller
    assert "message.timestamp" in controller
    assert '"timestamp": turn.get("user_timestamp") or turn.get("timestamp")' in command
    assert '"timestamp": turn.get("assistant_timestamp") or turn.get("timestamp")' in command
