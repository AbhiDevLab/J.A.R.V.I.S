"""Privacy-conscious SQLite audit trail for permission-gated automation."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import action_fingerprint


def get_audit_db_path() -> Path:
    configured = os.getenv("JARVIS_AUTOMATION_AUDIT_DB", "").strip()
    if configured:
        return Path(configured).expanduser()
    repository_root = Path(__file__).resolve().parents[2]
    return repository_root / "data" / "automation_audit.sqlite3"


def record_action_event(
    action: Any,
    tier: Any,
    event: str,
    reason: str = "",
) -> bool:
    """Persist an event without storing raw action arguments or document text."""
    path = get_audit_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path), timeout=5.0) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS automation_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                action_type TEXT NOT NULL,
                permission_tier TEXT NOT NULL,
                action_fingerprint TEXT NOT NULL,
                event TEXT NOT NULL,
                reason_code TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO automation_audit (
                timestamp_utc, action_type, permission_tier,
                action_fingerprint, event, reason_code
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                str(getattr(action, "action_type", "unknown"))[:100],
                str(getattr(tier, "value", tier))[:30],
                action_fingerprint(action),
                str(event)[:50],
                str(reason)[:100],
            ),
        )
        connection.commit()
    return True


def list_recent_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent metadata-only audit events for the future security UI."""
    safe_limit = max(1, min(int(limit), 500))
    path = get_audit_db_path()
    if not path.is_file():
        return []

    with sqlite3.connect(str(path), timeout=5.0) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, timestamp_utc, action_type, permission_tier,
                   action_fingerprint, event, reason_code
            FROM automation_audit
            ORDER BY id DESC LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]
