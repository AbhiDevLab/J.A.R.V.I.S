from __future__ import annotations
import re
from typing import Optional

from .actions import (
    AutomationAction,
    RiskLevel,
)
from .applications import (
    normalize_application_name,
    resolve_application,
)
from .filesystem import search_paths


OPEN_PREFIXES = (
    "open ",
    "launch ",
    "start ",
    "run ",
)


def _extract(
    text: str,
    prefixes: tuple[str, ...],
) -> Optional[str]:
    lowered = text.lower()

    for prefix in prefixes:
        if lowered == prefix.strip():
            return ""

        if lowered.startswith(prefix):
            return text[
                len(prefix):
            ].strip()

    return None


def _split_right(
    value: str,
    marker: str,
) -> tuple[str, str]:
    lowered = value.lower()
    index = lowered.rfind(marker)

    if index == -1:
        return (
            value.strip(),
            "",
        )

    return (
        value[:index].strip(),
        value[
            index + len(marker):
        ].strip(),
    )


def _clean_name(
    value: str,
) -> str:
    result = str(
        value or ""
    ).strip()

    for prefix in (
        "filename ",
        "file named ",
        "the file named ",
        "named ",
        "called ",
    ):
        if result.lower().startswith(
            prefix
        ):
            result = result[
                len(prefix):
            ].strip()
            break

    return result.rstrip(
        ".,!?;:"
    ).strip()


def _route_create(
    text: str,
    action_type: str,
) -> Optional[AutomationAction]:
    if action_type == "create_file":
        target = _extract(
            text,
            (
                "create a file",
                "create file",
            ),
        )

        if target is None:
            return None

        content = ""

        content_marker = (
            " with content "
        )

        index = target.lower().find(
            content_marker
        )

        if index != -1:
            content = target[
                index
                + len(content_marker):
            ].strip()

            target = target[:index].strip()

    else:
        target = _extract(
            text,
            (
                "create a folder",
                "create folder",
                "make a folder",
                "make folder",
            ),
        )

        if target is None:
            return None

        content = ""

    if target.lower().startswith(
        "in "
    ):
        name = ""
        directory = target[
            3:
        ].strip()
    else:
        name, directory = _split_right(
            target,
            " in ",
        )

    parameters = {
        "name": _clean_name(name),
        "directory": directory,
    }

    if action_type == "create_file":
        parameters["content"] = content

    return AutomationAction(
        action_type=action_type,
        parameters=parameters,
        risk=RiskLevel.LOW,
    )


def _route_rename(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract(
        text,
        (
            "rename the file",
            "rename file",
            "rename the folder",
            "rename folder",
        ),
    )

    if target is None:
        return None

    source, new_name = _split_right(
        target,
        " to ",
    )

    source, source_directory = (
        _split_right(
            source,
            " in ",
        )
    )

    is_folder = (
        "rename folder"
        in text.lower()
    )

    return AutomationAction(
        action_type=(
            "rename_folder"
            if is_folder
            else "rename_file"
        ),
        parameters={
            "source": _clean_name(
                source
            ),
            "source_directory": (
                source_directory
            ),
            "target": _clean_name(
                new_name
            ),
        },
        risk=RiskLevel.LOW,
    )


def _route_transfer(
    text: str,
    action_type: str,
) -> Optional[AutomationAction]:
    if action_type == "move_file":
        target = _extract(
            text,
            (
                "move the file",
                "move file",
            ),
        )
    else:
        target = _extract(
            text,
            (
                "copy the file",
                "copy file",
            ),
        )

    if target is None:
        return None

    source, destination = _split_right(
        target,
        " to ",
    )

    source, source_directory = (
        _split_right(
            source,
            " in ",
        )
    )

    return AutomationAction(
        action_type=action_type,
        parameters={
            "source": _clean_name(
                source
            ),
            "source_directory": (
                source_directory
            ),
            "destination": destination,
        },
        risk=RiskLevel.LOW,
    )


def _route_delete_all(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract(
        text,
        (
            "delete all occurrences of",
            "delete all occurrence of",
            "delete all instances of",
            "delete every occurrence of",
            "delete every instance of",
            "delete every copy of",
            "delete all copies of",
        ),
    )

    if target is None:
        return None

    target = target.strip()

    for suffix in (
        " from my system",
        " from system",
        " on my system",
        " on the system",
    ):
        if target.lower().endswith(
            suffix
        ):
            target = target[
                :-len(suffix)
            ].strip()
            break

    name = _clean_name(
        target
    )

    if not name:
        return AutomationAction(
            action_type="delete_all_matches",
            parameters={
                "name": "",
            },
            risk=RiskLevel.HIGH,
        )

    return AutomationAction(
        action_type="delete_all_matches",
        parameters={
            "name": name,
        },
        risk=RiskLevel.HIGH,
    )


def _route_delete(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract(
        text,
        (
            "delete the file",
            "delete file",
            "remove the file",
            "remove file",
        ),
    )

    if target is not None:
        path, directory = _split_right(
            target,
            " in ",
        )

        return AutomationAction(
            action_type="delete_file",
            parameters={
                "path": _clean_name(path),
                "source_directory": directory,
            },
            risk=RiskLevel.HIGH,
        )

    target = _extract(
        text,
        (
            "delete the folder",
            "delete folder",
            "remove the folder",
            "remove folder",
        ),
    )

    if target is not None:
        path, directory = _split_right(
            target,
            " in ",
        )

        return AutomationAction(
            action_type="delete_folder",
            parameters={
                "path": _clean_name(path),
                "source_directory": directory,
            },
            risk=RiskLevel.HIGH,
        )

    return None


def _route_find(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract(
        text,
        (
            "search for a file named",
            "search for a file called",
            "search for the file named",
            "search for the file called",
            "search for file",
            "find a file named",
            "find a file called",
            "find a file name called",
            "find the file named",
            "find the file called",
            "find file",
            "find the file",
            "locate file",
            "locate the file",
        ),
    )

    if target is None:
        return None

    name, directory = _split_right(
        target,
        " in ",
    )

    return AutomationAction(
        action_type="find_file",
        parameters={
            "name": _clean_name(name),
            "directory": directory,
        },
        risk=RiskLevel.LOW,
    )


def _route_listing(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract(
        text,
        (
            "list the files in",
            "list files in",
            "list directory",
            "show the files in",
            "show files in",
            "show directory",
            "show the contents of",
            "show contents of",
            "what is in",
            "what's in",
            "whats in",
            "list the files",
            "list files",
        ),
    )

    if target is None:
        return None

    return AutomationAction(
        action_type="list_directory",
        parameters={
            "path": target,
        },
        risk=RiskLevel.LOW,
    )


def _route_open(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract(
        text,
        OPEN_PREFIXES,
    )

    if not target:
        return None

    normalized = normalize_application_name(
        target
    )

    executable = resolve_application(
        normalized
    )

    if executable:
        return AutomationAction(
            action_type="open_application",
            parameters={
                "application": normalized,
                "executable": executable,
            },
            risk=RiskLevel.LOW,
        )

    folder_matches = search_paths(
        target,
        expected_type="folder",
        max_results=1,
    )

    if folder_matches:
        return AutomationAction(
            action_type="open_folder",
            parameters={
                "path": target,
            },
            risk=RiskLevel.LOW,
        )

    return AutomationAction(
        action_type="open_application",
        parameters={
            "application": normalized,
            "executable": "",
        },
        risk=RiskLevel.LOW,
    )


def _route_shell(
    text: str,
) -> Optional[AutomationAction]:
    target = _extract(
        text,
        (
            "run shell command",
            "execute shell command",
            "run command",
            "execute command",
        ),
    )

    if target is None or not target:
        return None

    return AutomationAction(
        action_type="shell_command",
        parameters={
            "command": target,
        },
        risk=RiskLevel.HIGH,
    )

def _route_find_and_operate(
    text: str,
) -> Optional[AutomationAction]:
    """
    Convert commands such as:

        Find Godmother and open it
        Find Godmother and delete it
        Find Godmother and move it to Desktop
        Find Godmother and copy it to Downloads
        Find Godmother and rename it to Final Godmother

    into a normal filesystem action whose source is resolved
    later by dialogue.py.
    """

    pattern = re.compile(
        r"""
        ^\s*
        (?P<find>
            find\s+(?:a\s+)?(?:file\s+)?(?:named\s+|called\s+|name\s+called\s+)?
            |
            search\s+for\s+(?:a\s+)?(?:file\s+)?(?:named\s+|called\s+|name\s+called\s+)?
            |
            locate\s+(?:a\s+)?(?:file\s+)?(?:named\s+|called\s+|name\s+called\s+)?
        )
        (?P<source>.+?)
        \s+
        (?:and\s+then|then|and)
        \s+
        (?P<operation>
            open
            |
            delete
            |
            remove
            |
            move
            |
            copy
            |
            rename
        )
        (?:
            \s+it
        |
            \s+the\s+file
        )?
        (?:
            \s+to\s+(?P<target>.+)
        )?
        \s*$
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    match = pattern.match(
        text
    )

    if not match:
        return None

    source = _clean_name(
        match.group("source")
    )

    operation = (
        match.group("operation")
        .lower()
    )

    target = match.group(
        "target"
    )

    if not source:
        return None

    if operation == "open":
        return AutomationAction(
            action_type="open_file",
            parameters={
                "source": source,
            },
            risk=RiskLevel.LOW,
        )

    if operation in {
        "delete",
        "remove",
    }:
        return AutomationAction(
            action_type="delete_file",
            parameters={
                "path": source,
            },
            risk=RiskLevel.HIGH,
        )

    if operation == "move":
        return AutomationAction(
            action_type="move_file",
            parameters={
                "source": source,
                "source_directory": "",
                "destination": (
                    target or ""
                ),
            },
            risk=RiskLevel.LOW,
        )

    if operation == "copy":
        return AutomationAction(
            action_type="copy_file",
            parameters={
                "source": source,
                "source_directory": "",
                "destination": (
                    target or ""
                ),
            },
            risk=RiskLevel.LOW,
        )

    if operation == "rename":
        return AutomationAction(
            action_type="rename_file",
            parameters={
                "source": source,
                "source_directory": "",
                "target": (
                    target or ""
                ),
            },
            risk=RiskLevel.LOW,
        )

    return None

def route_command(
    query: str,
) -> Optional[AutomationAction]:
    text = str(
        query or ""
    ).strip()

    if not text:
        return None
    
    action = _route_find_and_operate(
        text
    )

    if action is not None:
        return action

    # Most specific filesystem intents first.
    action = _route_delete_all(text)

    if action:
        return action

    action = _route_delete(text)

    if action:
        return action

    action = _route_find(text)

    if action:
        return action

    action = _route_create(
        text,
        "create_file",
    )

    if action:
        return action

    action = _route_create(
        text,
        "create_folder",
    )

    if action:
        return action

    action = _route_rename(text)

    if action:
        return action

    action = _route_transfer(
        text,
        "move_file",
    )

    if action:
        return action

    action = _route_transfer(
        text,
        "copy_file",
    )

    if action:
        return action

    action = _route_listing(text)

    if action:
        return action

    action = _route_shell(text)

    if action:
        return action

    return _route_open(text)