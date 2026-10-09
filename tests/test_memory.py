"""Regression tests for J.A.R.V.I.S Phase 8.2 persistent memory."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from engine import memory


def test_semantic_memory_persists_and_is_retrievable(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    first = memory.MemoryStore(db_path)
    saved = first.save_memory(
        "The user prefers a concise British voice for JARVIS.",
        memory_type="semantic",
        key="user.preferred_voice",
        confidence=0.96,
        importance=4,
    )

    assert saved is not None
    second = memory.MemoryStore(db_path)
    results = second.retrieve("Which voice does the user prefer?", limit=5)

    assert len(results) == 1
    assert results[0]["id"] == saved["id"]
    assert results[0]["memory_type"] == "semantic"
    assert results[0]["relevance_score"] > 0


def test_new_semantic_value_supersedes_old_value_for_same_key(tmp_path):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")
    old = store.save_memory(
        "The user prefers the American voice.",
        key="user.preferred_voice",
        confidence=0.9,
    )
    new = store.save_memory(
        "The user prefers the British voice.",
        key="user.preferred_voice",
        confidence=0.95,
    )

    assert old is not None and new is not None
    active = store.list_memories(memory_type="semantic")
    history = store.list_memories(memory_type="semantic", include_inactive=True)

    assert len(active) == 1
    assert active[0]["id"] == new["id"]
    old_record = next(item for item in history if item["id"] == old["id"])
    assert old_record["is_active"] is False
    assert old_record["superseded_by"] == new["id"]


def test_low_confidence_and_sensitive_memory_are_rejected(tmp_path):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")

    low_confidence = store.save_memory(
        "The user prefers concise responses.",
        key="user.response_style",
        confidence=0.2,
    )
    sensitive = store.save_memory(
        "The user's API key is secret.",
        key="user.secret",
        confidence=0.99,
    )

    assert low_confidence is None
    assert sensitive is None
    assert store.list_memories() == []


def test_expired_memory_is_deactivated_and_not_retrieved(tmp_path):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")
    saved = store.save_memory(
        "The user is working on a campus automation project.",
        key="project.campus_automation",
        confidence=0.95,
        expires_in_days=1,
    )
    assert saved is not None

    expired_at = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).isoformat(timespec="seconds")
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            "UPDATE memories SET expires_at = ? WHERE id = ?",
            (expired_at, saved["id"]),
        )

    assert store.retrieve("campus automation project") == []
    all_records = store.list_memories(include_inactive=True)
    assert all_records[0]["is_active"] is False


def test_episode_is_persisted_with_expiry_and_metadata(tmp_path):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")
    saved = store.save_memory(
        "Action: open_application. User request: open Notepad. Outcome: success.",
        memory_type="episodic",
        key="episode_open_notepad",
        source="automation",
        conversation_id="conversation-1",
        confidence=0.95,
        importance=2,
        expires_in_days=30,
        metadata={"action_type": "open_application"},
    )

    assert saved is not None
    assert saved["memory_type"] == "episodic"
    assert saved["source"] == "automation"
    assert saved["metadata"]["action_type"] == "open_application"
    assert saved["expires_at"] is not None


def test_forget_and_clear_operations_deactivate_memories(tmp_path):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")
    one = store.save_memory("The user prefers concise responses.", key="user.style")
    two = store.save_memory(
        "The user is building a desktop assistant.",
        key="project.desktop_assistant",
    )
    assert one is not None and two is not None

    assert store.forget_memory(key="user.style") == 1
    assert len(store.list_memories()) == 1
    assert store.clear_memories() == 1
    assert store.list_memories() == []


def test_memory_can_be_disabled_without_creating_database(tmp_path):
    db_path = tmp_path / "disabled.sqlite3"
    store = memory.MemoryStore(db_path, enabled=False)

    assert store.save_memory("The user prefers concise responses.") is None
    assert store.retrieve("response style") == []
    assert store.list_memories() == []
    assert not db_path.exists()


def test_retrieval_does_not_inject_unrelated_memories(tmp_path):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")
    store.save_memory(
        "The user is building a Python desktop assistant named JARVIS.",
        key="project.jarvis",
    )
    store.save_memory(
        "The user prefers a British English voice.",
        key="user.preferred_voice",
    )

    results = store.retrieve("Tell me about the Python desktop assistant project.")
    assert results
    assert all("assistant" in item["content"].lower() or "python" in item["content"].lower()
               or "jarvis" in item["content"].lower() for item in results)
    assert not any("British English voice" in item["content"] for item in results)


def test_extraction_only_runs_for_durable_user_statements(tmp_path, monkeypatch):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")
    monkeypatch.setattr(memory, "memory_store", store)
    monkeypatch.setenv("JARVIS_MEMORY_AUTO_EXTRACT", "1")
    monkeypatch.setattr(
        "engine.llm_client.ask_llm",
        lambda prompt: json.dumps({
            "memories": [{
                "key": "user.response_style",
                "content": "The user prefers concise technical explanations.",
                "memory_type": "semantic",
                "confidence": 0.94,
                "importance": 4,
            }]
        }),
    )

    saved = memory.extract_memories_from_turn(
        "I prefer concise technical explanations.",
        "Understood. I will be concise.",
        conversation_id="conversation-2",
    )

    assert len(saved) == 1
    assert saved[0]["memory_key"] == "user.response_style"
    assert store.list_memories()[0]["content"] == (
        "The user prefers concise technical explanations."
    )


def test_extraction_skips_ordinary_question_without_calling_llm(tmp_path, monkeypatch):
    store = memory.MemoryStore(tmp_path / "memory.sqlite3")
    monkeypatch.setattr(memory, "memory_store", store)
    def fail_if_called(_prompt):
        raise AssertionError("LLM should not be called for an ordinary question")
    monkeypatch.setattr("engine.llm_client.ask_llm", fail_if_called)

    assert memory.extract_memories_from_turn(
        "What is the weather today?",
        "I can help with that.",
    ) == []
