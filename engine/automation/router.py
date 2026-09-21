from __future__ import annotations

from typing import Optional

from .actions import (
    AutomationAction,
    RiskLevel,
)
from .applications import (
    normalize_application_name,
    resolve_application,
)


OPEN_PREFIXES = (
    "open ",
    "launch ",
    "start ",
    "run ",
)


def _extract_application_name(
    query: str,
) -> Optional[str]:
    text = str(
        query or ""
    ).strip()

    lowered = text.lower()

    for prefix in OPEN_PREFIXES:
        if lowered.startswith(prefix):
            return text[
                len(prefix):
            ].strip()

    return None


def route_command(
    query: str,
) -> Optional[AutomationAction]:
    """
    Convert natural-language commands into structured
    automation actions.

    Phase 7.2 currently supports:
        - known desktop application launching
        - explicit shell-command routing
    """

    text = str(
        query or ""
    ).strip()

    # ---------------------------------------------------------
    # Desktop application control
    # ---------------------------------------------------------

    application_name = _extract_application_name(text)
    if application_name:
        normalized_name = normalize_application_name(
            application_name
        )
        executable = resolve_application(
            normalized_name
        )

        return AutomationAction(
            action_type="open_application",
            parameters={
                "application": normalized_name,
                "executable": executable or "",
            },
            risk=RiskLevel.LOW,
        )

    # ---------------------------------------------------------
    # Existing secure shell-command pathway
    # ---------------------------------------------------------

    prefixes = (
        "run command ",
        "execute command ",
        "run shell command ",
        "execute shell command ",
    )

    lowered = text.lower()

    for prefix in prefixes:
        if lowered.startswith(prefix):
            command = text[
                len(prefix):
            ].strip()

            if not command:
                return None

            return AutomationAction(
                action_type="shell_command",
                parameters={
                    "command": command,
                },
                risk=RiskLevel.HIGH,
            )

    return None