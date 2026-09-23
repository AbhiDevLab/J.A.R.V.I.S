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
from .filesystem import (
    is_known_directory_reference,
    normalize_filesystem_text,
    resolve_path,
)


OPEN_PREFIXES = (
    "open ",
    "launch ",
    "start ",
    "run ",
)


def _extract_after_prefix(
    query: str,
    prefixes: tuple[str, ...],
) -> Optional[str]:
    text = str(
        query or ""
    ).strip()

    lowered = text.lower()

    for prefix in prefixes:
        if lowered.startswith(prefix):
            value = text[
                len(prefix):
            ].strip()

            if value:
                return value

    return None


def _split_clause(
    value: str,
    marker: str,
) -> Optional[tuple[str, str]]:
    lowered = value.lower()
    index = lowered.rfind(marker)

    if index == -1:
        return None

    left = value[:index].strip()
    right = value[
        index + len(marker):
    ].strip()

    if not left or not right:
        return None

    return left, right


def _looks_like_folder(
    value: str,
) -> bool:
    if is_known_directory_reference(
        value
    ):
        return True

    normalized = normalize_filesystem_text(
        value
    )

    if normalized.endswith(
        (" folder", " directory")
    ):
        return True

    try:
        return resolve_path(value).is_dir()
    except Exception:
        return False


def _route_open_folder(
    text: str,
) -> Optional[AutomationAction]:
    explicit_target = _extract_after_prefix(
        text,
        (
            "open folder ",
            "open directory ",
        ),
    )

    if explicit_target:
        return AutomationAction(
            action_type="open_folder",
            parameters={
                "path": explicit_target,
            },
            risk=RiskLevel.LOW,
        )

    target = _extract_after_prefix(
        text,
        OPEN_PREFIXES,
    )

    if not target:
        return None

    if not _looks_like_folder(target):
        return None

    return AutomationAction(
        action_type="open_folder",
        parameters={
            "path": target,
        },
        risk=RiskLevel.LOW,
    )


def _route_directory_listing(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract_after_prefix(
        text,
        (
            "list files in ",
            "list the files in ",
            "show files in ",
            "show the files in ",
            "list directory ",
            "show directory ",
            "show contents of ",
            "show the contents of ",
            "what is in ",
            "what's in ",
            "whats in ",
        ),
    )

    if not target:
        return None

    return AutomationAction(
        action_type="list_directory",
        parameters={
            "path": target,
        },
        risk=RiskLevel.LOW,
    )


def _route_find_file(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract_after_prefix(
        text,
        (
            "find file ",
            "find the file ",
            "search for file ",
            "search for the file ",
            "find ",
        ),
    )

    if not target:
        return None

    parts = _split_clause(
        target,
        " in ",
    )

    if parts:
        name, directory = parts
    else:
        name = target
        directory = ""

    return AutomationAction(
        action_type="find_file",
        parameters={
            "name": name,
            "directory": directory,
        },
        risk=RiskLevel.LOW,
    )

def _route_create_file(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract_after_prefix(
        text,
        (
            "create file ",
            "create a file ",
        ),
    )

    if not target:
        return None

    content = ""

    parts = _split_clause(
        target,
        " with content ",
    )

    if parts:
        path, content = parts
    else:
        path = target

    path_parts = _split_clause(
        path,
        " in ",
    )

    if path_parts:
        filename, directory = path_parts
        full_path = (
            resolve_path(directory)
            / filename.strip()
        )
    else:
        full_path = path.strip()

    return AutomationAction(
        action_type="create_file",
        parameters={
            "path": str(full_path),
            "content": content.strip(),
        },
        risk=RiskLevel.LOW,
    )

def _route_create_folder(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract_after_prefix(
        text,
        (
            "create folder ",
            "create a folder ",
            "make folder ",
            "make a folder ",
        ),
    )

    if not target:
        return None

    return AutomationAction(
        action_type="create_folder",
        parameters={
            "path": target,
        },
        risk=RiskLevel.LOW,
    )


def _route_rename(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract_after_prefix(
        text,
        (
            "rename file ",
            "rename the file ",
            "rename folder ",
            "rename the folder ",
        ),
    )

    if not target:
        return None

    parts = _split_clause(
        target,
        " to ",
    )

    if not parts:
        return None

    source, destination = parts

    lowered = text.lower()

    expected_type = (
        "folder"
        if "rename folder" in lowered
        else "file"
    )

    action_type = (
        "rename_folder"
        if expected_type == "folder"
        else "rename_file"
    )

    return AutomationAction(
        action_type=action_type,
        parameters={
            "source": source,
            "target": destination,
        },
        risk=RiskLevel.LOW,
    )


def _route_file_transfer(
    text: str,
) -> Optional[AutomationAction]:
    move_target = _extract_after_prefix(
        text,
        (
            "move file ",
            "move the file ",
        ),
    )

    if move_target:
        parts = _split_clause(
            move_target,
            " to ",
        )

        if parts:
            source, destination = parts

            return AutomationAction(
                action_type="move_file",
                parameters={
                    "source": source,
                    "destination": destination,
                },
                risk=RiskLevel.LOW,
            )

    copy_target = _extract_after_prefix(
        text,
        (
            "copy file ",
            "copy the file ",
        ),
    )

    if copy_target:
        parts = _split_clause(
            copy_target,
            " to ",
        )

        if parts:
            source, destination = parts

            return AutomationAction(
                action_type="copy_file",
                parameters={
                    "source": source,
                    "destination": destination,
                },
                risk=RiskLevel.LOW,
            )

    return None


def _route_delete(
    text: str,
) -> Optional[AutomationAction]:
    file_target = _extract_after_prefix(
        text,
        (
            "delete file ",
            "delete the file ",
            "remove file ",
            "remove the file ",
        ),
    )

    if file_target:
        return AutomationAction(
            action_type="delete_file",
            parameters={
                "path": file_target,
            },
            risk=RiskLevel.HIGH,
        )

    folder_target = _extract_after_prefix(
        text,
        (
            "delete folder ",
            "delete the folder ",
            "remove folder ",
            "remove the folder ",
        ),
    )

    if folder_target:
        return AutomationAction(
            action_type="delete_folder",
            parameters={
                "path": folder_target,
            },
            risk=RiskLevel.HIGH,
        )

    return None


def _route_shell_command(
    text: str,
) -> Optional[AutomationAction]:
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


def _route_application(
    text: str,
) -> Optional[AutomationAction]:
    application_name = _extract_after_prefix(
        text,
        OPEN_PREFIXES,
    )

    if not application_name:
        return None

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


def route_command(
    query: str,
) -> Optional[AutomationAction]:
    """
    Convert natural-language commands into
    structured automation actions.
    """

    text = str(
        query or ""
    ).strip()

    if not text:
        return None

    # ---------------------------------------------------------
    # File / folder control
    # ---------------------------------------------------------

    filesystem_action = (
        _route_open_folder(text)
        or _route_directory_listing(text)
        or _route_find_file(text)
        or _route_create_file(text)
        or _route_create_folder(text)
        or _route_rename(text)
        or _route_file_transfer(text)
        or _route_delete(text)
    )

    if filesystem_action is not None:
        return filesystem_action

    # ---------------------------------------------------------
    # Existing secure shell-command pathway
    #
    # IMPORTANT:
    # This comes before generic "run " application
    # detection so "run command ..." remains a shell command.
    # ---------------------------------------------------------

    shell_action = _route_shell_command(
        text
    )

    if shell_action is not None:
        return shell_action

    # ---------------------------------------------------------
    # Desktop application control
    # ---------------------------------------------------------

    return _route_application(text)