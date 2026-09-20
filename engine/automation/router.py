from __future__ import annotations

from typing import Optional

from .actions import (
    AutomationAction,
    RiskLevel,
)


def route_command(
    query: str,
) -> Optional[AutomationAction]:
    """
    Convert an explicit user command into a structured
    automation action.

    Phase 10.1 intentionally supports only shell-command
    routing so the security gate can be validated safely.
    """

    text = str(
        query or ""
    ).strip()

    lowered = text.lower()

    prefixes = (
        "run command ",
        "execute command ",
        "run shell command ",
        "execute shell command ",
    )

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