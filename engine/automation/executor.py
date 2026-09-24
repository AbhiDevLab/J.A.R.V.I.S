from __future__ import annotations

import subprocess
from typing import Any, Dict

from .actions import (
    AutomationAction,
    requires_confirmation,
)
from .applications import resolve_application
from .filesystem import (
    copy_file,
    create_file,
    create_folder,
    delete_file,
    delete_folder,
    find_file,
    list_directory,
    move_file,
    open_file,
    open_folder,
    rename_path,
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

def _execute_filesystem_action(
    action: AutomationAction,
) -> Dict[str, Any]:
    parameters = action.parameters
    action_type = action.action_type

    if action_type == "open_folder":
        success, message = open_folder(
            parameters.get("path", "")
        )

    elif action_type == "list_directory":
        success, message = list_directory(
            parameters.get("path", "")
        )

    elif action_type == "find_file":
        success, message = find_file(
            parameters.get("name", ""),
            parameters.get("directory", ""),
        )
        
    elif action_type == "open_file":
        success, message = open_file(
            parameters.get("path", "")
        )

    elif action_type == "create_file":
        success, message = create_file(
            parameters.get("path", ""),
            parameters.get("content", ""),
        )
        
    elif action_type == "create_folder":
        success, message = create_folder(
            parameters.get("path", "")
        )

    elif action_type == "rename_file":
        success, message = rename_path(
            parameters.get("source", ""),
            parameters.get("target", ""),
            "file",
        )

    elif action_type == "rename_folder":
        success, message = rename_path(
            parameters.get("source", ""),
            parameters.get("target", ""),
            "folder",
        )

    elif action_type == "move_file":
        success, message = move_file(
            parameters.get("source", ""),
            parameters.get("destination", ""),
        )

    elif action_type == "copy_file":
        success, message = copy_file(
            parameters.get("source", ""),
            parameters.get("destination", ""),
        )

    elif action_type == "delete_file":
        success, message = delete_file(
            parameters.get("path", "")
        )

    elif action_type == "delete_folder":
        success, message = delete_folder(
            parameters.get("path", "")
        )

    else:
        return _result(
            False,
            f"Unsupported filesystem action: {action_type}",
        )

    return _result(
        success,
        message,
    )
    
def _execute_delete_all_matches(
    action: AutomationAction,
) -> Dict[str, Any]:
    paths = action.parameters.get(
        "paths",
        [],
    )

    if not isinstance(
        paths,
        list,
    ) or not paths:
        return _result(
            False,
            "No matching files were provided.",
        )

    deleted = 0
    failures = []

    for raw_path in paths:
        path = str(
            raw_path
        ).strip()

        if not path:
            continue

        try:
            from pathlib import Path

            target = Path(path)

            if not target.exists():
                continue

            if not target.is_file():
                failures.append(
                    str(target)
                )
                continue

            target.unlink()
            deleted += 1

        except Exception as exc:
            print(
                f"Delete-all error for {path}: {exc}"
            )
            failures.append(path)

    if failures:
        return _result(
            False,
            (
                f"Deleted {deleted} matching files, "
                f"but {len(failures)} could not be deleted."
            ),
            deleted_count=deleted,
            failed_paths=failures,
        )

    return _result(
        True,
        f"Deleted {deleted} matching files.",
        deleted_count=deleted,
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
        "open_file": _execute_filesystem_action,
        "open_folder": _execute_filesystem_action,
        "list_directory": _execute_filesystem_action,
        "find_file": _execute_filesystem_action,
        "create_file": _execute_filesystem_action,
        "create_folder": _execute_filesystem_action,
        "rename_file": _execute_filesystem_action,
        "rename_folder": _execute_filesystem_action,
        "move_file": _execute_filesystem_action,
        "copy_file": _execute_filesystem_action,
        "delete_file": _execute_filesystem_action,
        "delete_folder": _execute_filesystem_action,
        "delete_all_matches": _execute_delete_all_matches,
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