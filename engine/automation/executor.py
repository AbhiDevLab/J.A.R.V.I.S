from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Dict

from .actions import AutomationAction
from .policy import (
    ApprovalMode,
    ActionTier,
    action_fingerprint,
    get_action_policy,
)
from .audit import record_action_event
from .elevation import execute_privileged_action
from .applications import resolve_application, canonical_application_name
from .application_state import (
    record_application_opened,
    record_application_closed,
)
from .windows_apps import (
    close_application_window,
    read_application_window_text,
    type_text_into_application,
    create_new_notepad_document,
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
from engine.system_resources import discover_system_resources


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
            (
                f"I could not locate {application}. I checked its configured executable "
                "locations, Windows App Paths, Start Menu shortcuts and packaged-app "
                "registrations. If this is a portable installation, add a Start Menu "
                "shortcut or configure its executable path."
            ),
            error_code="application_not_found",
        )

    print(f"🖥️ Opening application: {application}")
    print(f"Executable: {executable}")

    try:
        if str(executable).casefold().startswith("apps-folder:"):
            if os.name != "nt":
                return _result(False, "Microsoft Store applications can only be activated through the Windows AppsFolder.")
            app_id = str(executable).split(":", 1)[1].strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+", app_id):
                return _result(False, "Windows returned an invalid application identifier. I did not launch it.")
            system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
            explorer = os.path.join(system_root, "explorer.exe")
            subprocess.Popen(
                [explorer, f"shell:AppsFolder\\{app_id}"],
                shell=False,
            )
        elif str(executable).casefold().endswith(".lnk"):
            if os.name != "nt" or not hasattr(os, "startfile"):
                return _result(False, "Windows Start Menu shortcuts can only be launched on Windows.")
            os.startfile(executable)
        elif application in {"command prompt", "cmd"}:
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

def _execute_type_text(action: AutomationAction) -> Dict[str, Any]:
    application = str(action.parameters.get("application", "")).strip()
    text = str(action.parameters.get("text", ""))
    if not application:
        return _result(False, "No target application was specified.")
    if not text:
        return _result(False, "There is no text to type.")
    return type_text_into_application(application, text)


def _execute_open_application_and_type(action: AutomationAction) -> Dict[str, Any]:
    application = str(action.parameters.get("application", "")).strip()
    executable = str(action.parameters.get("executable", "")).strip()
    text = str(action.parameters.get("text", ""))
    if not application or not text:
        return _result(False, "The application and text are both required.")

    opened = _execute_open_application(
        AutomationAction(
            action_type="open_application",
            parameters={"application": application, "executable": executable},
            risk=action.risk,
        )
    )
    if not opened.get("success"):
        return opened

    open_message = str(opened.get("message") or f"Opened {application}.")
    document_message = ""
    new_document_created = False

    if canonical_application_name(application) == "notepad":
        prepared = create_new_notepad_document(application)
        if not prepared.get("success"):
            return _result(
                False,
                (
                    f"{open_message} "
                    f"{prepared.get('message', 'I could not prepare a blank document.')} "
                    "I did not type anything, so the existing Notepad content remains untouched."
                ),
                application_opened=True,
                typing_completed=False,
                new_document_created=False,
            )
        document_message = str(prepared.get("message") or "")
        new_document_created = bool(prepared.get("new_document_created"))

    typed = _execute_type_text(
        AutomationAction(
            action_type="type_text",
            parameters={"application": application, "text": text},
            risk=action.risk,
        )
    )
    if not typed.get("success"):
        return _result(
            False,
            (
                f"{open_message} "
                "However, I could not complete the typing step: "
                f"{typed.get('message', 'the target was not verified')} "
                "The application remains open; no typing retry was attempted."
            ),
            application_opened=True,
            typing_completed=False,
        )
    return _result(
        True,
        " ".join(
            part for part in (open_message, document_message, str(typed.get("message") or ""))
            if part
        ),
        application_opened=True,
        typing_completed=True,
        new_document_created=new_document_created,
        characters_typed=typed.get("characters_typed"),
    )


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

def _format_resource_size(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError):
        return "unknown"
    if amount < 0:
        return "unknown"
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return "unknown"


def _resource_markdown_cell(value: Any, fallback: str = "—") -> str:
    """Normalize untrusted inventory values for a Markdown table cell."""
    text = str(value if value not in (None, "") else fallback)
    return (
        text.replace("|", "¦")
        .replace(chr(13), " ")
        .replace(chr(10), " ")
        .replace("`", "'")
    )


def _execute_system_resource_discovery(action: AutomationAction) -> Dict[str, Any]:
    parameters = action.parameters or {}
    scopes = parameters.get("scopes")
    query = str(parameters.get("query") or "").strip() or None

    if not isinstance(scopes, (list, tuple, set)) or not scopes:
        return _result(False, "No system resource category was specified.")

    try:
        inventory = discover_system_resources(
            scopes,
            query=query,
        )
    except (TypeError, ValueError) as exc:
        return _result(
            False,
            f"I could not perform that resource search ({type(exc).__name__}).",
            error_code="invalid_resource_request",
        )

    sections: list[str] = []
    spoken_parts: list[str] = []
    generated_at = _resource_markdown_cell(
        inventory.get("generated_at_utc"),
        "timestamp unavailable",
    )
    scope_labels = ", ".join(
        _resource_markdown_cell(scope)
        for scope in inventory.get("scopes", [])
    )

    system = inventory.get("system")
    if isinstance(system, dict):
        operating_system = " ".join(
            value for value in (
                str(system.get("operating_system") or "").strip(),
                str(system.get("os_edition") or "").strip(),
                str(system.get("os_release") or "").strip(),
            ) if value and value.casefold() != "unknown"
        ) or "Unknown operating system"
        architecture = str(system.get("architecture") or "unknown")
        processor = str(system.get("processor") or "unknown")
        physical_cores = system.get("physical_core_count")
        logical_cpus = system.get("logical_cpu_count")
        clock_mhz = system.get("processor_clock_mhz")
        cpu_details = (
            f"{physical_cores} physical cores, {logical_cpus} logical processors"
            if physical_cores is not None and logical_cpus is not None
            else f"{logical_cpus} logical processors"
            if logical_cpus is not None
            else "unknown"
        )
        if clock_mhz is not None:
            cpu_details += f", registry clock {clock_mhz} MHz"

        memory_installed = _format_resource_size(system.get("memory_installed_bytes"))
        memory_usable = _format_resource_size(system.get("memory_total_bytes"))
        memory_used = _format_resource_size(system.get("memory_used_bytes"))
        memory_available = _format_resource_size(system.get("memory_available_bytes"))
        memory_load = (
            f"{system.get('memory_load_percent')}%"
            if system.get("memory_load_percent") is not None
            else "unknown"
        )
        os_version = str(system.get("os_version") or "unknown")
        os_build = str(system.get("os_build") or "unknown")
        os_ubr = str(system.get("os_update_revision") or "unknown")
        sections.append(
            "## System overview\n"
            "| Property | Runtime value |\n"
            "|---|---|\n"
            f"| Operating system | {_resource_markdown_cell(operating_system)} |\n"
            f"| OS version | {_resource_markdown_cell(os_version)} |\n"
            f"| OS build | {_resource_markdown_cell(os_build)} (UBR { _resource_markdown_cell(os_ubr) }) |\n"
            f"| Architecture | {_resource_markdown_cell(architecture)} |\n"
            f"| Processor | {_resource_markdown_cell(processor)} |\n"
            f"| CPU cores / processors | {_resource_markdown_cell(cpu_details)} |\n"
            f"| Installed physical RAM | {memory_installed} |\n"
            f"| Usable physical RAM | {memory_usable} |\n"
            f"| Physical RAM in use | {memory_used} |\n"
            f"| Available physical RAM | {memory_available} |\n"
            f"| Calculated physical memory use | {memory_load} |"
        )
        spoken_parts.append(
            f"system information for {operating_system} with {architecture} architecture"
        )

    applications = inventory.get("installed_applications")
    if isinstance(applications, list):
        rows = [item for item in applications if isinstance(item, dict)]
        category_labels = {
            "installed_application": "Installed desktop applications",
            "packaged_application": "Packaged applications",
            "windows_component": "Registered components and updates",
            "registered_executable": "Registered executables (installation not verified)",
            "shortcut_only": "Start Menu shortcuts (installation not verified)",
        }
        category_order = (
            "installed_application",
            "packaged_application",
            "windows_component",
            "registered_executable",
            "shortcut_only",
        )
        category_counts = {
            category: sum(1 for item in rows if item.get("category") == category)
            for category in category_order
        }
        app_summary = [
            "| Evidence category | Count |",
            "|---|---:|",
        ]
        for category in category_order:
            count = category_counts[category]
            if count:
                app_summary.append(
                    f"| {category_labels[category]} | {count} |"
                )
        if not rows:
            app_summary.append("| No application evidence returned | 0 |")
        sections.append(
            "## Application discovery\n"
            + "\n".join(app_summary)
            + "\n\nA shortcut or App Paths entry alone is not treated as proof "
              "that a conventional application is installed."
        )

        for category in category_order:
            category_rows = [item for item in rows if item.get("category") == category]
            if not category_rows:
                continue
            table_rows = [
                "| Name | Publisher | Version | Evidence |",
                "|---|---|---|---|",
            ]
            for item in category_rows[:25]:
                source_labels = ", ".join(item.get("sources") or []) or "unknown"
                table_rows.append(
                    f"| {_resource_markdown_cell(item.get('display_name') or item.get('name'))} "
                    f"| {_resource_markdown_cell(item.get('publisher'))} "
                    f"| {_resource_markdown_cell(item.get('version'))} "
                    f"| {_resource_markdown_cell(source_labels)} |"
                )
            suffix = (
                f"\n\nShowing **25 of {len(category_rows)}** entries."
                if len(category_rows) > 25
                else f"\n\n**{len(category_rows)}** entries."
            )
            sections.append(
                f"### {category_labels[category]}\n"
                + "\n".join(table_rows)
                + suffix
            )
        verified_count = category_counts["installed_application"] + category_counts["packaged_application"]
        spoken_parts.append(
            f"{verified_count} verified installed or packaged applications"
        )

    processes = inventory.get("running_processes")
    if isinstance(processes, list):
        rows = [
            item for item in processes
            if isinstance(item, dict)
        ]
        table_rows = [
            "| Process | PID | Memory |",
            "|---|---:|---:|",
        ]
        for item in rows[:20]:
            memory_value = item.get("memory_kb")
            memory_label = (
                _format_resource_size(float(memory_value) * 1024)
                if memory_value is not None
                else "unknown"
            )
            table_rows.append(
                f"| {_resource_markdown_cell(item.get('name'))} "
                f"| {item.get('pid', '—')} | {memory_label} |"
            )
        if not rows:
            table_rows.append("| No process data available | — | — |")
        suffix = (
            f"\n\nShowing **20 of {len(rows)}** returned processes."
            if len(rows) > 20
            else f"\n\n**{len(rows)}** processes returned."
        )
        sections.append(
            "## Running processes\n"
            + "\n".join(table_rows)
            + suffix
        )
        spoken_parts.append(f"{len(rows)} running processes returned")

    windows = inventory.get("visible_windows")
    if isinstance(windows, list):
        rows = [
            item for item in windows
            if isinstance(item, dict)
        ]
        foreground = inventory.get("foreground_window")
        foreground_handle = (
            foreground.get("handle")
            if isinstance(foreground, dict)
            else None
        )
        table_rows = [
            "| Window | Application | PID | State |",
            "|---|---|---:|---|",
        ]
        for item in rows[:20]:
            state = (
                "**Foreground**"
                if foreground_handle is not None
                and item.get("handle") == foreground_handle
                else "Visible"
            )
            table_rows.append(
                f"| {_resource_markdown_cell(item.get('title'), '(untitled)')} "
                f"| {_resource_markdown_cell(item.get('process_name'), 'unknown')} "
                f"| {item.get('process_id', '—')} | {state} |"
            )
        if not rows:
            table_rows.append("| No visible titled windows found | — | — | — |")
        suffix = (
            f"\n\nShowing **20 of {len(rows)}** visible windows."
            if len(rows) > 20
            else f"\n\n**{len(rows)}** visible windows returned."
        )
        sections.append(
            "## Open applications and windows\n"
            + "\n".join(table_rows)
            + suffix
        )
        if isinstance(foreground, dict):
            spoken_parts.append(
                f"{len(rows)} visible windows; foreground window is "
                f"{foreground.get('title') or 'untitled'}"
            )
        else:
            spoken_parts.append(f"{len(rows)} visible windows")

    relationships = inventory.get("application_process_relationships")
    if isinstance(relationships, dict):
        rows = [
            item for item in relationships.get("items", [])
            if isinstance(item, dict)
        ]
        table_rows = [
            "| Application | Process | PID | Match evidence | Windows | Foreground |",
            "|---|---|---:|---|---:|---|",
        ]
        for item in rows[:40]:
            basis_labels = {
                "exact_executable_path": "Exact executable path",
                "inside_registered_install_location": "Inside registered install folder",
                "unique_executable_name": "Unique executable name",
                "executable_name_claimed_by_multiple_apps": "Ambiguous executable name",
                "duplicate_executable_path_evidence": "Duplicate path evidence",
                "overlapping_install_locations": "Overlapping install folders",
                "unmatched": "No verified application match",
            }
            basis = basis_labels.get(
                str(item.get("match_basis") or ""),
                str(item.get("match_basis") or "unknown"),
            )
            table_rows.append(
                f"| {_resource_markdown_cell(item.get('application'))} "
                f"| {_resource_markdown_cell(item.get('process'))} "
                f"| {item.get('pid', '—')} "
                f"| {_resource_markdown_cell(basis)} "
                f"| {item.get('window_count', 0)} "
                f"| {'Yes' if item.get('has_foreground_window') else 'No'} |"
            )
            titles = [
                _resource_markdown_cell(title)
                for title in item.get("window_titles", [])
                if title
            ]
            if titles:
                table_rows.append(
                    f"| ↳ Window titles | {_resource_markdown_cell('; '.join(titles))} "
                    "| — | Joined by exact PID | — | — |"
                )
        if not rows:
            table_rows.append("| No process relationships returned | — | — | — | — | — |")

        query_label = relationships.get("query")
        summary = (
            f"**{relationships.get('matched_count', 0)}** mapped, "
            f"**{relationships.get('ambiguous_count', 0)}** ambiguous, "
            f"**{relationships.get('unmapped_count', 0)}** unmapped "
            f"out of **{relationships.get('process_count', len(rows))}** processes."
        )
        if query_label:
            summary = (
                f"Filtered for **{_resource_markdown_cell(query_label)}**. "
                + summary
            )
        sample_limit = relationships.get("process_sample_limit")
        sample_note = (
            f"\n\nSnapshot is bounded to up to {int(sample_limit)} processes; "
            "additional running processes may not be included."
            if isinstance(sample_limit, int) and sample_limit > 0
            else ""
        )
        sections.append(
            "## Application–process relationships\n"
            + summary
            + "\n\n"
            + "\n".join(table_rows[:81])
            + "\n\nRelationships use executable path, registered install location, "
              "or a unique executable name. Windows are joined to processes by exact PID. "
              "Ambiguous or inaccessible matches are not guessed."
            + sample_note
        )
        spoken_parts.append(
            f"{relationships.get('matched_count', 0)} application-process relationships mapped; "
            f"{relationships.get('ambiguous_count', 0)} ambiguous and "
            f"{relationships.get('unmapped_count', 0)} unmapped"
        )

    drives = inventory.get("drives")
    if isinstance(drives, list):
        rows = [
            item for item in drives
            if isinstance(item, dict)
        ]
        table_rows = [
            "| Drive | Volume label | Type | File system | Capacity | Used | Free |",
            "|---|---|---|---|---:|---:|---:|",
        ]
        for item in rows:
            table_rows.append(
                f"| {_resource_markdown_cell(item.get('root'))} "
                f"| {_resource_markdown_cell(item.get('volume_label'))} "
                f"| {_resource_markdown_cell(item.get('type'))} "
                f"| {_resource_markdown_cell(item.get('filesystem'))} "
                f"| {_format_resource_size(item.get('total_bytes'))} "
                f"| {_format_resource_size(item.get('used_bytes'))} "
                f"| {_format_resource_size(item.get('free_bytes'))} |"
            )
        if not rows:
            table_rows.append("| No logical drives found | — | — | — | — | — | — |")
        sections.append(
            "## Logical drives\n"
            + "\n".join(table_rows)
        )
        spoken_parts.append(f"{len(rows)} logical drives")

    file_search = inventory.get("files_and_folders")
    if isinstance(file_search, dict):
        results = [
            item for item in file_search.get("results", [])
            if isinstance(item, dict)
        ]
        result_rows = [
            f"- **{_resource_markdown_cell(item.get('kind'))}:** "
            f"`{_resource_markdown_cell(item.get('path'))}`"
            for item in results[:25]
        ]
        if not result_rows:
            result_rows.append("- No matching file or folder names were found.")
        status = (
            f"Search stopped at the **{_resource_markdown_cell(file_search.get('stop_reason'))}** limit."
            if file_search.get("truncated")
            else "Search completed within its configured limits."
        )
        sections.append(
            f"## File and folder matches for `{_resource_markdown_cell(file_search.get('query'))}`\n"
            f"**{file_search.get('result_count', len(results))}** matches returned.\n\n"
            + "\n".join(result_rows)
            + f"\n\n{status}"
        )
        spoken_parts.append(
            f"{file_search.get('result_count', len(results))} file or folder names matching {file_search.get('query')}"
        )

    message = (
        "# J.A.R.V.I.S — System resource report\n\n"
        f"> Snapshot: {generated_at}  \n"
        f"> Categories: {scope_labels or 'selected resources'}\n\n"
        + "\n\n".join(sections)
    )
    spoken_message = (
        "Resource discovery completed. " + "; ".join(spoken_parts) + "."
        if spoken_parts
        else "Resource discovery completed."
    )
    return _result(
        True,
        message,
        spoken_message=spoken_message,
        summary=spoken_message,
        inventory=inventory,
    )



def execute_action(
    action: AutomationAction,
) -> Dict[str, Any]:
    """Execute a supported action through the central permission policy.

    Ordinary operations run automatically. Sensitive operations require a
    one-time voice confirmation. Critical operations require voice + face.
    Actions explicitly marked requires_admin are sent only to the privileged
    broker after approval; the normal JARVIS process never self-elevates.
    """
    handlers = {
        "open_application": _execute_open_application,
        "open_application_and_type": _execute_open_application_and_type,
        "type_text": _execute_type_text,
        "close_application": _execute_close_application,
        "read_application": _execute_read_application,
        "discover_system_resources": _execute_system_resource_discovery,
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

    handler = handlers.get(action.action_type)
    if handler is None:
        return _result(
            False,
            f"Unsupported automation action: {action.action_type}",
            error_code="unsupported_action",
        )

    permission = get_action_policy(action)
    tier = permission.tier
    approval_required = permission.approval_mode is not ApprovalMode.AUTOMATIC
    fingerprint = action_fingerprint(action)

    # Record the request without persisting raw paths, command text, document
    # contents, or other action arguments. Sensitive/critical actions fail
    # closed when the audit store cannot be written.
    try:
        audit_ok = record_action_event(
            action, tier, "requested", "policy_evaluation_started"
        )
    except Exception as exc:
        audit_ok = False
        print(f"JARVIS audit write failed: {type(exc).__name__}")

    if not audit_ok and tier is not ActionTier.ORDINARY:
        return _result(
            False,
            "The security audit log is unavailable. This operation was blocked.",
            error_code="audit_unavailable",
        )

    if approval_required:
        try:
            authorized = request_authorization(
                action,
                require_face=permission.requires_face,
            )
        except Exception as exc:
            authorized = False
            print(f"JARVIS authorization failed: {type(exc).__name__}")

        if not authorized:
            try:
                record_action_event(action, tier, "denied", "approval_not_granted")
            except Exception:
                pass
            return _result(
                False,
                "Action cancelled by the permission policy. No operation was executed.",
                cancelled=True,
                permission_tier=tier.value,
            )

        # The approval is operation-specific and one-shot. Any parameter
        # mutation between approval and execution invalidates it.
        if action_fingerprint(action) != fingerprint:
            try:
                record_action_event(action, tier, "denied", "approved_action_changed")
            except Exception:
                pass
            return _result(
                False,
                "The approved operation changed before execution. It was cancelled.",
                cancelled=True,
                error_code="approval_fingerprint_mismatch",
            )

        try:
            approved_logged = record_action_event(
                action, tier, "approved", "one_time_approval_received"
            )
        except Exception as exc:
            approved_logged = False
            print(f"JARVIS approval audit failed: {type(exc).__name__}")

        if not approved_logged:
            return _result(
                False,
                "The approval could not be recorded securely. This operation was blocked.",
                error_code="audit_unavailable",
            )

    if action.requires_admin:
        if permission.administrator_access != "ondemand":
            result = _result(
                False,
                "Administrator access is disabled by the current JARVIS policy.",
                error_code="admin_access_disabled",
            )
        else:
            # A dedicated one-shot UAC broker is introduced in Phase 7.4.4.
            # Until it is installed, privileged actions are rejected instead
            # of running through the normal, potentially under/over-privileged
            # process or attempting blanket elevation.
            result = execute_privileged_action(action)
        try:
            record_action_event(
                action,
                tier,
                "execution_succeeded" if result.get("success") else "execution_blocked",
                str(result.get("error_code") or "privileged_broker_result"),
            )
        except Exception as exc:
            print(f"JARVIS audit write failed: {type(exc).__name__}")
        return result

    try:
        result = handler(action)
    except Exception as exc:
        print(f"Automation handler error ({action.action_type}): {type(exc).__name__}")
        result = _result(
            False,
            f"The requested operation failed ({type(exc).__name__}).",
            error_code="handler_exception",
        )

    try:
        record_action_event(
            action,
            tier,
            "execution_succeeded" if result.get("success") else "execution_failed",
            "handler_succeeded" if result.get("success") else str(result.get("error_code") or "handler_failed"),
        )
    except Exception as exc:
        # Execution has already happened; report the operational result while
        # surfacing the audit-write failure in logs for maintenance.
        print(f"JARVIS audit write failed after execution: {type(exc).__name__}")

    return result
