from __future__ import annotations

import re
import subprocess
from typing import Any, Dict

from .actions import (
    AutomationAction,
    requires_confirmation,
)
from .applications import resolve_application
from .application_state import (
    record_application_opened,
    record_application_closed,
)
from .windows_apps import (
    close_application_window,
    read_application_window_text,
)
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
from engine.llm_client import ask_llm


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
        if application in {"command prompt", "cmd"}:
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

        record_application_opened(application)
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



def _execute_close_application(action: AutomationAction) -> Dict[str, Any]:
    application = str(action.parameters.get("application", "")).strip()
    if not application:
        return _result(False, "No application was specified.")
    result = close_application_window(application)
    if result.get("success") and not result.get("still_open"):
        record_application_closed(application)
    return result


def _answer_application_question(question: str, content: str, application: str) -> str:
    """Answer from the live window text only; never consult conversation memory."""
    question_text = str(question or "").strip()
    source_text = str(content or "").strip()
    if not question_text or not source_text:
        return "I could not find enough readable text to answer that question."

    # High-value named-field questions get deterministic extraction first.
    # Windows UI Automation may flatten a multi-line document into one line,
    # so stop at the next recognized field label as well as at a line ending.
    if re.search(r"\bproject\s+(?:name|title)\b", question_text, re.IGNORECASE):
        following_field_labels = (
            r"last[ \t]+updated|due[ \t]+date|start[ \t]+date|end[ \t]+date|"
            r"project[ \t]+manager|meeting[ \t]+time|"
            r"status|date|owner|author|developer|description|meeting|"
            r"experiment|version|priority|created|updated|"
            r"language|framework|technology|team|department|email|"
            r"contact|phone|deadline|repository|repo|branch|"
            r"website|url|location|notes|summary|objective|goal"
        )
        project_field_pattern = (
            r"(?im)^[ \t]*project[ \t]+(?:name|title)[ \t]*[:=—-][ \t]*"
            r"(?P<value>.*?)"
            rf"(?=(?:[ \t]+|[|;,][ \t]*)(?:{following_field_labels})"
            r"[ \t]*[:=—-]|[ \t]*$)"
        )
        match = re.search(project_field_pattern, source_text)
        if match:
            value = re.sub(r"\s+", " ", match.group("value")).strip().strip("\"' ")
            if value:
                return f"The project name shown in {application.title()} is {value}."
        return (
            f"The visible {application.title()} text does not explicitly state a project name."
        )

    prompt = f"""
You are answering a question about text JARVIS has just extracted from a live Windows application.
Answer using ONLY the source text below. Do not use previous conversation, stored memory, outside knowledge,
or assumptions. If the answer is not explicitly supported by the source, say that it is not specified.
Be concise and include a short exact supporting excerpt when one exists.

Application: {application}
User question: {question_text}

SOURCE TEXT (the only evidence):
<document>
{source_text}
</document>
"""
    try:
        answer = str(ask_llm(prompt) or "").strip()
    except Exception as exc:
        print(f"Application document question unavailable: {type(exc).__name__}")
        return (
            f"I read the {application.title()} text, but could not answer the question right now. "
            "The extracted text is available; please try the question again."
        )
    if not answer:
        return f"The visible text in {application.title()} does not provide an answer to that question."
    return answer

def _execute_read_application(action: AutomationAction) -> Dict[str, Any]:
    application = str(action.parameters.get("application", "")).strip()
    question = str(action.parameters.get("question", "")).strip()
    if not application:
        return _result(False, "No application was specified.")
    result = read_application_window_text(application)
    if not result.get("success"):
        return _result(False, str(result.get("message") or "I could not read that application."))

    if question:
        answer = _answer_application_question(
            question,
            str(result.get("content") or ""),
            application,
        )
        return {
            "success": True,
            "content": result.get("content", ""),
            "answer": answer,
            "message": f"Based only on the visible text in {application.title()}:\n\n{answer}",
            "spoken_message": answer,
            "summary": f"Answered a question using the visible text in {application.title()}.",
        }
    return result


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
        "close_application": _execute_close_application,
        "read_application": _execute_read_application,
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