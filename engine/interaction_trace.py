"""Local, privacy-conscious interaction traces for J.A.R.V.I.S.

Only bounded decision metadata is stored. This module deliberately has no
fields or APIs for prompts, transcripts, document text, tool output, paths,
shell arguments, credentials, or raw audio.
"""
from __future__ import annotations

import math
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_EVENT_TYPES = {
    "turn_started",
    "interpretation_completed",
    "clarification_requested",
    "intent_classified",
    "automation_completed",
    "response_generated",
    "llm_failure",
    "turn_interrupted",
    "turn_completed",
}
_INPUT_CHANNELS = {"voice", "typed", "unknown"}
_INTENTS = {
    "automation",
    "conversation",
    "clarification",
    "confirmation",
    "cancellation",
    "unknown",
    "llm_error",
}
_ROUTES = {
    "automation",
    "conversation",
    "interpretation",
    "clarification",
    "recovery",
    "unknown",
}
_OUTCOMES = {
    "success",
    "failed",
    "clarification",
    "interrupted",
    "cancelled",
    "timeout",
    "configuration",
    "rate_limit",
    "provider_error",
    "unknown",
}
_PROVIDERS = {"omniroute", "openai", "gemini", "openrouter", "custom"}
_TOKEN_RE = re.compile(r"^[a-zA-Z0-9_.:/-]{1,120}$")


def _enabled() -> bool:
    value = os.getenv("JARVIS_INTERACTION_TRACES_ENABLED", "1")
    return str(value).strip().casefold() not in {"0", "false", "no", "off"}


def get_interaction_trace_db_path() -> Path:
    configured = os.getenv("JARVIS_INTERACTION_TRACE_DB", "").strip()
    if configured:
        return Path(configured).expanduser()
    repository_root = Path(__file__).resolve().parents[1]
    return repository_root / "data" / "interaction_traces.sqlite3"


def new_interaction_trace_id() -> str:
    """Create an opaque ID that does not encode user or conversation data."""
    return uuid.uuid4().hex


def _bounded_days() -> int:
    try:
        value = int(os.getenv("JARVIS_INTERACTION_TRACE_RETENTION_DAYS", "30"))
    except (TypeError, ValueError):
        value = 30
    return max(1, min(value, 365))


def _safe_token(value: Any, allowed: set[str], *, default: str = "") -> str:
    normalized = str(value or "").strip().casefold()
    return normalized if normalized in allowed else default


def _safe_identifier(value: Any) -> str:
    normalized = str(value or "").strip()
    if not _TOKEN_RE.fullmatch(normalized):
        return ""
    return normalized[:120]


def _safe_confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(max(0.0, min(number, 1.0)), 4)


def _safe_latency(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return round(min(number, 3_600_000.0), 2)


def record_interaction_trace(
    trace_id: str,
    event_type: str,
    **metadata: Any,
) -> bool:
    """Append one allowlisted event; failures never affect the user interaction.

    Arbitrary keyword fields are discarded. Only these metadata keys can be
    persisted: input_channel, interpretation_used, interpretation_confidence,
    intent, intent_source, route, action_type, outcome, error_category,
    provider, model, and latency_ms.
    """
    if not _enabled():
        return False

    identifier = str(trace_id or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        return False

    event = _safe_token(event_type, _EVENT_TYPES)
    if not event:
        return False

    channel = _safe_token(metadata.get("input_channel"), _INPUT_CHANNELS)
    intent = _safe_token(metadata.get("intent"), _INTENTS)
    route = _safe_token(metadata.get("route"), _ROUTES)
    outcome = _safe_token(metadata.get("outcome"), _OUTCOMES)
    provider = _safe_token(metadata.get("provider"), _PROVIDERS)
    action_type = _safe_identifier(metadata.get("action_type"))
    intent_source = _safe_identifier(metadata.get("intent_source"))
    error_category = _safe_identifier(metadata.get("error_category"))
    model = _safe_identifier(metadata.get("model"))
    confidence = _safe_confidence(metadata.get("interpretation_confidence"))
    latency = _safe_latency(metadata.get("latency_ms"))

    interpretation_used = metadata.get("interpretation_used")
    if interpretation_used is not None:
        interpretation_used = int(bool(interpretation_used))

    path = get_interaction_trace_db_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat(timespec="milliseconds")
        cutoff = (now - timedelta(days=_bounded_days())).isoformat(
            timespec="milliseconds"
        )
        with sqlite3.connect(str(path), timeout=5.0) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    input_channel TEXT NOT NULL DEFAULT '',
                    interpretation_used INTEGER,
                    interpretation_confidence REAL,
                    intent TEXT NOT NULL DEFAULT '',
                    intent_source TEXT NOT NULL DEFAULT '',
                    route TEXT NOT NULL DEFAULT '',
                    action_type TEXT NOT NULL DEFAULT '',
                    outcome TEXT NOT NULL DEFAULT '',
                    error_category TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    latency_ms REAL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_interaction_trace_events_trace
                    ON interaction_trace_events(trace_id, id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_interaction_trace_events_time
                    ON interaction_trace_events(timestamp_utc)
                """
            )
            connection.execute(
                "DELETE FROM interaction_trace_events WHERE timestamp_utc < ?",
                (cutoff,),
            )
            # Retention is time-based, with a hard row cap as a second bound.
            connection.execute(
                """
                DELETE FROM interaction_trace_events
                 WHERE id NOT IN (
                     SELECT id FROM interaction_trace_events
                     ORDER BY id DESC LIMIT 50000
                 )
                """
            )
            connection.execute(
                """
                INSERT INTO interaction_trace_events (
                    trace_id, timestamp_utc, event_type, input_channel,
                    interpretation_used, interpretation_confidence, intent,
                    intent_source, route, action_type, outcome, error_category,
                    provider, model, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier, timestamp, event, channel, interpretation_used,
                    confidence, intent, intent_source, route, action_type,
                    outcome, error_category, provider, model, latency,
                ),
            )
            connection.commit()
        return True
    except (OSError, sqlite3.Error):
        # Observability is best-effort and must never break J.A.R.V.I.S.
        return False


def list_recent_interaction_trace_events(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent metadata-only events for diagnostics; never exposes content."""
    if not _enabled():
        return []
    try:
        safe_limit = max(1, min(int(limit), 1000))
    except (TypeError, ValueError):
        safe_limit = 100

    path = get_interaction_trace_db_path()
    if not path.is_file():
        return []
    try:
        with sqlite3.connect(str(path), timeout=5.0) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, trace_id, timestamp_utc, event_type, input_channel,
                       interpretation_used, interpretation_confidence, intent,
                       intent_source, route, action_type, outcome, error_category,
                       provider, model, latency_ms
                FROM interaction_trace_events
                ORDER BY id DESC LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    except (OSError, sqlite3.Error):
        return []
