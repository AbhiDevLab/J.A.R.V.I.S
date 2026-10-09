"""Regression tests for Phase 8.3 structured profile context."""
from engine import memory
from engine.user_context import (
    build_user_profile_context,
    get_profile_items,
    save_profile_item,
)


def test_profile_items_are_structured_and_persisted(tmp_path, monkeypatch):
    store = memory.MemoryStore(tmp_path / "profile.sqlite3")
    monkeypatch.setattr(memory, "memory_store", store)

    saved = save_profile_item(
        "communication",
        "response_style",
        "The user prefers concise technical responses.",
        confidence=0.95,
        importance=4,
    )

    assert saved is not None
    items = get_profile_items(category="communication")
    assert len(items) == 1
    assert items[0]["profile_category"] == "communication"
    assert items[0]["memory_key"] == "profile.communication.response_style"


def test_profile_context_includes_relevant_preferences_only(tmp_path, monkeypatch):
    store = memory.MemoryStore(tmp_path / "profile.sqlite3")
    monkeypatch.setattr(memory, "memory_store", store)
    save_profile_item(
        "communication",
        "response_style",
        "The user prefers concise technical responses.",
        confidence=0.95,
    )
    save_profile_item(
        "preference",
        "voice",
        "The user prefers a British English voice.",
        confidence=0.95,
    )

    context = build_user_profile_context("How should you format technical responses?")

    assert "concise technical responses" in context
    assert "British English voice" not in context


def test_profile_context_does_not_inject_unrelated_project_context(tmp_path, monkeypatch):
    store = memory.MemoryStore(tmp_path / "profile.sqlite3")
    monkeypatch.setattr(memory, "memory_store", store)
    save_profile_item(
        "project",
        "jarvis_stack",
        "The JARVIS project uses Python and Eel.",
        confidence=0.95,
    )

    assert build_user_profile_context("What response style should you use?") == ""


def test_profile_storage_rejects_sensitive_or_low_confidence_items(tmp_path, monkeypatch):
    store = memory.MemoryStore(tmp_path / "profile.sqlite3")
    monkeypatch.setattr(memory, "memory_store", store)

    assert save_profile_item(
        "preference",
        "secret",
        "The user's API key is confidential.",
        confidence=0.99,
    ) is None
    assert save_profile_item(
        "communication",
        "response_style",
        "The user prefers concise responses.",
        confidence=0.2,
    ) is None
    assert get_profile_items() == []


def test_legacy_user_and_project_memory_keys_are_profile_context(tmp_path, monkeypatch):
    store = memory.MemoryStore(tmp_path / "profile.sqlite3")
    monkeypatch.setattr(memory, "memory_store", store)
    store.save_memory(
        "The user prefers a British English voice.",
        key="user.preferred_voice",
        confidence=0.95,
    )
    store.save_memory(
        "The JARVIS project uses Python.",
        key="project.jarvis.stack",
        confidence=0.95,
    )

    assert {item["profile_category"] for item in get_profile_items()} == {
        "preference",
        "project",
    }
