"""Short-lived, verified desktop application activity context for Phase 8."""
from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict

_EVENTS = deque(maxlen=20)


def record_application_opened(application: str) -> None:
    _EVENTS.append({
        "action": "open requested",
        "application": str(application or "").strip(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })


def record_application_closed(application: str) -> None:
    _EVENTS.append({
        "action": "closed",
        "application": str(application or "").strip(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })


def build_application_activity_context() -> str:
    """Describe recent JARVIS app actions separately from current live window state."""
    events = [item for item in _EVENTS if item.get("application")]
    if not events:
        return ""

    lines = [
        "Recent desktop application activity recorded by JARVIS (historical events):"
    ]
    for event in list(events)[-8:]:
        lines.append(
            f"- {event['action']}: {event['application']} ({event['timestamp']})"
        )

    latest_apps = []
    for event in reversed(events):
        app = event["application"]
        if app not in latest_apps:
            latest_apps.append(app)
        if len(latest_apps) >= 5:
            break

    try:
        from .windows_apps import get_application_windows
        for app in latest_apps:
            try:
                windows = get_application_windows(app)
                if windows:
                    lines.append(
                        f"Current live Windows check: {app} has {len(windows)} visible window(s)."
                    )
                else:
                    lines.append(
                        f"Current live Windows check: no visible {app} window was found."
                    )
            except Exception:
                lines.append(
                    f"Current live Windows check: state of {app} could not be verified."
                )
    except Exception:
        lines.append("Current live Windows application state is unavailable.")

    lines.append(
        "Do not confuse a historical open request with a currently open window. "
        "Only claim an application is currently open when the live Windows check confirms a visible window."
    )
    return "\n".join(lines)


def clear_application_activity() -> None:
    """Test helper: clear the in-memory activity journal."""
    _EVENTS.clear()
