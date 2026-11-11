"""Privacy and lifecycle tests for local interaction tracing."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from engine import interaction_trace


def test_trace_persists_only_allowlisted_decision_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "traces.sqlite3"
    monkeypatch.setenv("JARVIS_INTERACTION_TRACES_ENABLED", "1")
    monkeypatch.setenv("JARVIS_INTERACTION_TRACE_DB", str(db_path))

    trace_id = interaction_trace.new_interaction_trace_id()
    assert interaction_trace.record_interaction_trace(
        trace_id,
        "intent_classified",
        input_channel="voice",
        interpretation_used=True,
        interpretation_confidence=0.9472,
        intent="automation",
        intent_source="context_interpreter",
        route="automation",
        action_type="open_application",
        outcome="success",
        latency_ms=123.456,
        # These deliberately sensitive values must be silently discarded.
        raw_transcript="open my private tax report",
        prompt="full private prompt",
        path="C:/Users/example/private.pdf",
        command="del C:/Users/example/private.pdf",
        document_text="private document content",
        api_key="do-not-store",
    )

    rows = interaction_trace.list_recent_interaction_trace_events()
    assert len(rows) == 1
    event = rows[0]
    assert event["trace_id"] == trace_id
    assert event["event_type"] == "intent_classified"
    assert event["input_channel"] == "voice"
    assert event["interpretation_confidence"] == 0.9472
    assert event["intent"] == "automation"
    assert event["intent_source"] == "context_interpreter"
    assert event["route"] == "automation"
    assert event["action_type"] == "open_application"
    assert event["outcome"] == "success"
    assert event["latency_ms"] == 123.46

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(interaction_trace_events)"
            )
        }
    assert not columns.intersection(
        {
            "raw_transcript",
            "transcript",
            "prompt",
            "path",
            "command",
            "arguments",
            "document_text",
            "api_key",
            "response",
            "tool_output",
        }
    )


def test_trace_opt_out_does_not_create_a_database(tmp_path, monkeypatch):
    db_path = tmp_path / "disabled.sqlite3"
    monkeypatch.setenv("JARVIS_INTERACTION_TRACES_ENABLED", "0")
    monkeypatch.setenv("JARVIS_INTERACTION_TRACE_DB", str(db_path))

    assert interaction_trace.record_interaction_trace(
        interaction_trace.new_interaction_trace_id(),
        "turn_started",
        input_channel="typed",
    ) is False
    assert interaction_trace.list_recent_interaction_trace_events() == []
    assert not db_path.exists()


def test_unknown_events_and_invalid_trace_ids_are_rejected(tmp_path, monkeypatch):
    db_path = tmp_path / "invalid.sqlite3"
    monkeypatch.setenv("JARVIS_INTERACTION_TRACES_ENABLED", "1")
    monkeypatch.setenv("JARVIS_INTERACTION_TRACE_DB", str(db_path))

    assert interaction_trace.record_interaction_trace(
        "not-a-uuid",
        "turn_started",
    ) is False
    assert interaction_trace.record_interaction_trace(
        interaction_trace.new_interaction_trace_id(),
        "store_entire_prompt",
        prompt="must not be stored",
    ) is False
    assert not db_path.exists()


def test_retention_removes_events_older_than_configured_window(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "retention.sqlite3"
    monkeypatch.setenv("JARVIS_INTERACTION_TRACES_ENABLED", "1")
    monkeypatch.setenv("JARVIS_INTERACTION_TRACE_DB", str(db_path))
    monkeypatch.setenv("JARVIS_INTERACTION_TRACE_RETENTION_DAYS", "1")

    first_id = interaction_trace.new_interaction_trace_id()
    second_id = interaction_trace.new_interaction_trace_id()
    assert interaction_trace.record_interaction_trace(
        first_id, "turn_started", input_channel="typed"
    )
    old_timestamp = (
        datetime.now(timezone.utc) - timedelta(days=3)
    ).isoformat(timespec="milliseconds")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE interaction_trace_events SET timestamp_utc = ? WHERE trace_id = ?",
            (old_timestamp, first_id),
        )

    assert interaction_trace.record_interaction_trace(
        second_id, "turn_started", input_channel="voice"
    )
    rows = interaction_trace.list_recent_interaction_trace_events()
    assert [row["trace_id"] for row in rows] == [second_id]


def test_trace_store_failure_never_raises_or_breaks_caller(tmp_path, monkeypatch):
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("occupied", encoding="utf-8")
    monkeypatch.setenv("JARVIS_INTERACTION_TRACES_ENABLED", "1")
    monkeypatch.setenv(
        "JARVIS_INTERACTION_TRACE_DB",
        str(parent_file / "traces.sqlite3"),
    )

    assert interaction_trace.record_interaction_trace(
        interaction_trace.new_interaction_trace_id(),
        "turn_started",
        input_channel="voice",
    ) is False
