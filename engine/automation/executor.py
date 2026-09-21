from __future__ import annotations

import subprocess
from typing import Any, Dict

from .actions import (
    AutomationAction,
    requires_confirmation,
)
from .applications import resolve_application
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

def _execute_open_application(
    action: AutomationAction,
) -> Dict[str, Any]:
    application = str(
        action.parameters.get("application", "")
    ).strip()
    executable = str(
        action.parameters.get("executable", "")
    ).strip()

    if not application:
        return _result(
            False,
            "No application was specified.",
        )

    resolved = resolve_application(application)

    if resolved:
        executable = resolved

    if not executable:
        return _result(
            False,
            f"I could not find {application}.",
        )

    print(f"🖥️ Opening application: {application}")
    print(f"Executable: {executable}")

    try:
        if application == {"command prompt", "cmd"}:
            subprocess.Popen(
                [executable, "/K"],
                shell=False,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            subprocess.Popen(
                [executable],
                shell=False,
            )

        return _result(
            True,
            f"Opening {application}.",
        )

    except Exception as exc:
        print(
            f"Application launch error: {exc}"
        )
        return _result(
            False,
            f"I could not open {application}.",
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
        "open_application": _execute_open_application,
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