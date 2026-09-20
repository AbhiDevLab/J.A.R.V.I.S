from __future__ import annotations

import subprocess
from typing import Any, Dict

from .actions import (
    AutomationAction,
    requires_confirmation,
)
from .security import request_authorization


def _result(
    success: bool,
    message: str,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "success": success,
        "message": message,
        **extra,
    }


def _execute_shell_command(
    action: AutomationAction,
) -> Dict[str, Any]:
    command = str(
        action.parameters.get(
            "command",
            "",
        )
    ).strip()

    if not command:
        return _result(
            False,
            "No shell command was provided.",
        )

    print(
        f"⚙️ Executing authorized shell command: {command}"
    )

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

        stdout = (
            completed.stdout.strip()
            if completed.stdout
            else ""
        )

        stderr = (
            completed.stderr.strip()
            if completed.stderr
            else ""
        )

        return _result(
            completed.returncode == 0,
            (
                stdout
                or stderr
                or (
                    "Command completed successfully."
                    if completed.returncode == 0
                    else "Command failed."
                )
            ),
            return_code=completed.returncode,
        )

    except subprocess.TimeoutExpired:
        return _result(
            False,
            "The command timed out.",
        )

    except Exception as exc:
        print(
            f"Shell command execution error: {exc}"
        )

        return _result(
            False,
            "The shell command could not be executed.",
        )


def execute_action(
    action: AutomationAction,
) -> Dict[str, Any]:
    """
    Execute a structured automation action.

    High-risk actions MUST pass the authorization gate.
    """

    if requires_confirmation(action):
        authorized = request_authorization(
            action
        )

        if not authorized:
            return _result(
                False,
                "Action cancelled by authorization gate.",
                cancelled=True,
            )

    handlers = {
        "shell_command": _execute_shell_command,
    }

    handler = handlers.get(
        action.action_type
    )

    if handler is None:
        return _result(
            False,
            f"Unsupported automation action: "
            f"{action.action_type}",
        )

    return handler(action)