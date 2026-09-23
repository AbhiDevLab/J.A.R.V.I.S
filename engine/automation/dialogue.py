from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import List, Optional

from .actions import AutomationAction
from .filesystem import (
    resolve_existing_path,
    resolve_path,
    search_paths,
)


CANCELLATION_PHRASES = {
    "cancel",
    "stop",
    "abort",
    "no",
    "never mind",
    "nevermind",
}


def _normalize(
    text: str,
) -> str:
    return " ".join(
        str(text or "")
        .strip()
        .lower()
        .split()
    )


def _clean(
    text: str,
) -> str:
    value = str(
        text or ""
    ).strip()

    while (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {'"', "'"}
    ):
        value = value[1:-1].strip()

    return value.rstrip(
        ".,!?;:"
    ).strip()


def _cancelled(
    text: str,
) -> bool:
    return (
        _normalize(text)
        in CANCELLATION_PHRASES
    )


def _ask(
    prompt: str,
) -> Optional[str]:
    from engine.command import (
        speak,
        takecommand,
    )

    speak(prompt)

    response = takecommand()

    if _cancelled(response):
        speak("Action cancelled.")
        return None

    response = _clean(response)

    if not response:
        speak(
            "I didn't catch that."
        )
        return None

    return response


def _choose_match(
    matches: List[Path],
    description: str,
) -> Optional[Path]:
    from engine.command import (
        _safe_display,
        speak,
        takecommand,
    )

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    preview = matches[:10]

    location_lines = [
        f"{index}. {match}"
        for index, match in enumerate(
            preview,
            start=1,
        )
    ]

    # Show the complete paths in the UI.
    _safe_display(
        "receiverText",
        (
            f"I found these multiple locations "
            f"for {description}:\n\n"
            + "\n".join(location_lines)
            + "\n\n"
            "Say the number to select a specific "
            "file."
        ),
    )

    # Keep the spoken response short.
    speak(
        f"I found {len(matches)} matching "
        f"locations for {description}. "
        "Say the number of the one you mean.",
        display=False
    )

    response = str(
        takecommand()
    ).strip().lower()

    response = response.rstrip(
        ".,!?;:"
    ).strip()

    if response in {
        "cancel",
        "stop",
        "abort",
        "no",
    }:
        speak("Action cancelled.")
        return None

    if response.isdigit():
        index = int(response)

        if (
            1 <= index <= len(preview)
        ):
            return preview[index - 1]

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    if response in number_words:
        index = number_words[
            response
        ]

        if index <= len(preview):
            return preview[index - 1]

    speak(
        "I could not determine which "
        "location you meant."
    )

    return None

def _choose_delete_target(
    matches: List[Path],
    description: str,
) -> tuple[str, Optional[Path]]:
    from engine.command import (
        _safe_display,
        speak,
        takecommand,
    )

    if not matches:
        return "none", None

    if len(matches) == 1:
        return "single", matches[0]

    preview = matches[:]

    location_lines = [
        f"{index}. {match}"
        for index, match in enumerate(
            preview,
            start=1,
        )
    ]

    all_option = (
        f"{len(preview) + 1}. All"
    )

    display_text = (
        f"I found these multiple locations "
        f"for {description}:\n\n"
        + "\n".join(location_lines)
        + f"\n{all_option}"
    )

    _safe_display(
        "receiverText",
        display_text,
    )

    speak(
        f"I found {len(preview)} matching files. "
        "Say the number to delete a specific file, "
        "or say all to delete every occurrence.",
        display=False
    )

    response = str(
        takecommand()
    ).strip().lower()

    response = response.rstrip(
        ".,!?;:"
    ).strip()

    if response in {
        "cancel",
        "stop",
        "abort",
        "no",
    }:
        speak("Action cancelled.")
        return "cancelled", None

    if response == "all":
        return "all", None

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    if response in number_words:
        index = number_words[
            response
        ]
    elif response.isdigit():
        index = int(response)
    else:
        speak(
            "I could not determine which "
            "file you meant."
        )
        return "invalid", None

    if 1 <= index <= len(preview):
        return (
            "single",
            preview[index - 1],
        )

    if index == len(preview) + 1:
        return "all", None

    speak(
        "That selection is not valid."
    )

    return "invalid", None

def _resolve_directory(
    reference: str,
) -> Optional[Path]:
    path, error = (
        resolve_existing_path(
            reference,
            "folder",
        )
    )

    if path is not None:
        return path

    from engine.command import speak

    speak(
        error
        or f"I could not find {reference}."
    )

    return None


def _complete_create(
    action: AutomationAction,
    item_type: str,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    name = _clean(
        parameters.get(
            "name",
            "",
        )
    )

    directory = _clean(
        parameters.get(
            "directory",
            "",
        )
    )

    if not name:
        name = _ask(
            f"What should the {item_type} "
            f"be named?"
        )

        if name is None:
            return None

    if not directory:
        directory = _ask(
            f"Where should I create "
            f"{name}?"
        )

        if directory is None:
            return None

    directory_path = _resolve_directory(
        directory
    )

    if directory_path is None:
        return None

    path = (
        directory_path
        / Path(name).name
    ).resolve(
        strict=False
    )

    parameters["path"] = str(
        path
    )

    return replace(
        action,
        parameters=parameters,
    )


def _complete_open_folder(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    reference = _clean(
        parameters.get(
            "path",
            "",
        )
    )

    if not reference:
        reference = _ask(
            "Which folder should I open?"
        )

        if reference is None:
            return None

    directory = _resolve_directory(
        reference
    )

    if directory is None:
        return None

    parameters["path"] = str(
        directory
    )

    return replace(
        action,
        parameters=parameters,
    )


def _complete_listing(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    reference = _clean(
        parameters.get(
            "path",
            "",
        )
    )

    if not reference:
        reference = _ask(
            "Which folder should I list?"
        )

        if reference is None:
            return None

    directory = _resolve_directory(
        reference
    )

    if directory is None:
        return None

    parameters["path"] = str(
        directory
    )

    return replace(
        action,
        parameters=parameters,
    )


def _complete_find(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    name = _clean(
        parameters.get(
            "name",
            "",
        )
    )

    directory = _clean(
        parameters.get(
            "directory",
            "",
        )
    )

    if not name:
        name = _ask(
            "Which file should I find?"
        )

        if name is None:
            return None

    if directory:
        directory_path = _resolve_directory(
            directory
        )

        if directory_path is None:
            return None

        directory = str(
            directory_path
        )

    parameters["name"] = name
    parameters["directory"] = directory

    return replace(
        action,
        parameters=parameters,
    )


def _complete_rename(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    expected_type = (
        "folder"
        if action.action_type
        == "rename_folder"
        else "file"
    )

    source = _clean(
        parameters.get(
            "source",
            "",
        )
    )

    source_directory = _clean(
        parameters.get(
            "source_directory",
            "",
        )
    )

    target = _clean(
        parameters.get(
            "target",
            "",
        )
    )

    if not source:
        source = _ask(
            f"Which {expected_type} "
            f"should I rename?"
        )

        if source is None:
            return None

    if source_directory:
        directory = _resolve_directory(
            source_directory
        )

        if directory is None:
            return None

        candidate = (
            directory / source
        )

        matches = (
            [candidate]
            if candidate.exists()
            else []
        )
    else:
        matches = search_paths(
            source,
            expected_type=expected_type,
            max_results=50,
        )

    resolved = _choose_match(
        matches,
        source,
    )

    if resolved is None:
        from engine.command import speak

        speak(
            f"I could not uniquely locate "
            f"{source}."
        )
        return None

    if not target:
        target = _ask(
            "What should I rename it to?"
        )

        if target is None:
            return None

    parameters["source"] = str(
        resolved
    )
    parameters["target"] = Path(
        target
    ).name

    return replace(
        action,
        parameters=parameters,
    )


def _complete_transfer(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    source = _clean(
        parameters.get(
            "source",
            "",
        )
    )

    source_directory = _clean(
        parameters.get(
            "source_directory",
            "",
        )
    )

    destination = _clean(
        parameters.get(
            "destination",
            "",
        )
    )

    operation = (
        "move"
        if action.action_type
        == "move_file"
        else "copy"
    )

    if not source:
        source = _ask(
            f"Which file should I {operation}?"
        )

        if source is None:
            return None

    if source_directory:
        directory = _resolve_directory(
            source_directory
        )

        if directory is None:
            return None

        candidate = (
            directory / source
        )

        matches = (
            [candidate]
            if candidate.exists()
            else []
        )
    else:
        matches = search_paths(
            source,
            expected_type="file",
            max_results=50,
        )

    resolved = _choose_match(
        matches,
        source,
    )

    if resolved is None:
        from engine.command import speak

        speak(
            f"I could not uniquely locate "
            f"{source}."
        )
        return None

    if not destination:
        destination = _ask(
            f"Where should I {operation} "
            f"{resolved.name}?"
        )

        if destination is None:
            return None

    directory = _resolve_directory(
        destination
    )

    if directory is None:
        return None

    parameters["source"] = str(
        resolved
    )
    parameters["destination"] = str(
        directory
    )

    return replace(
        action,
        parameters=parameters,
    )


def _complete_delete(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    expected_type = (
        "folder"
        if action.action_type
        == "delete_folder"
        else "file"
    )

    target = _clean(
        parameters.get(
            "path",
            "",
        )
    )

    source_directory = _clean(
        parameters.get(
            "source_directory",
            "",
        )
    )

    if not target:
        target = _ask(
            f"Which {expected_type} "
            f"should I delete?"
        )

        if target is None:
            return None

    if source_directory:
        directory = _resolve_directory(
            source_directory
        )

        if directory is None:
            return None

        candidate = (
            directory / target
        )

        matches = (
            [candidate]
            if candidate.exists()
            and (
                (
                    expected_type == "file"
                    and candidate.is_file()
                )
                or (
                    expected_type == "folder"
                    and candidate.is_dir()
                )
            )
            else []
        )

    else:
        matches = search_paths(
            target,
            expected_type=expected_type,
            max_results=500,
        )

    if not matches:
        from engine.command import speak

        speak(
            f"I could not find "
            f"{target}."
        )

        return None

    if len(matches) == 1:
        parameters["path"] = str(
            matches[0]
        )

        return replace(
            action,
            parameters=parameters,
        )

    # Multiple matches:
    # provide selection only for a normal delete request.
    if expected_type != "file":
        from engine.command import (
            _safe_display,
            speak,
            takecommand,
        )

        location_lines = [
            f"{index}. {match}"
            for index, match in enumerate(
                matches,
                start=1,
            )
        ]

        _safe_display(
            "receiverText",
            (
                f"I found these multiple locations "
                f"for {target}:\n\n"
                + "\n".join(
                    location_lines
                )
            ),
        )

        speak(
            f"I found {len(matches)} matching "
            f"{expected_type}s. "
            "Please say the number of the one "
            "you want to delete.",
            display=False
        )

        response = str(
            takecommand()
        ).strip().lower()

        response = response.rstrip(
            ".,!?;:"
        ).strip()

        if not response.isdigit():
            speak(
                "I could not determine "
                "which one you meant."
            )
            return None

        index = int(response)

        if not (
            1 <= index <= len(matches)
        ):
            speak(
                "That selection is not valid."
            )
            return None

        parameters["path"] = str(
            matches[index - 1]
        )

        return replace(
            action,
            parameters=parameters,
        )

    selection, selected = (
        _choose_delete_target(
            matches,
            target,
        )
    )

    if selection == "cancelled":
        return None

    if selection == "single":
        parameters["path"] = str(
            selected
        )

        return replace(
            action,
            parameters=parameters,
        )

    if selection == "all":
        return replace(
            action,
            action_type="delete_all_matches",
            parameters={
                "name": target,
                "paths": [
                    str(match)
                    for match in matches
                ],
            },
        )

    return None

def _complete_delete_all(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    parameters = dict(
        action.parameters
    )

    name = _clean(
        parameters.get(
            "name",
            "",
        )
    )

    if not name:
        name = _ask(
            "Which filename should I "
            "delete all occurrences of?"
        )

        if name is None:
            return None

    matches = search_paths(
        name,
        expected_type="file",
        max_results=None,
    )

    if not matches:
        from engine.command import speak

        speak(
            f"I could not find any files "
            f"named {name}."
        )
        return None

    from engine.command import (
        _safe_display,
        speak,
    )

    location_lines = [
        f"{index}. {match}"
        for index, match in enumerate(
            matches,
            start=1,
        )
    ]

    _safe_display(
        "receiverText",
        (
            f"I found these locations "
            f"for {name}:\n\n"
            + "\n".join(
                location_lines
            )
            + "\n\n"
            f"All {len(matches)} matching files "
            f"will be deleted."
        ),
    )

    parameters["name"] = name
    parameters["paths"] = [
        str(match)
        for match in matches
    ]

    return replace(
        action,
        parameters=parameters,
    )


def complete_action(
    action: AutomationAction,
) -> Optional[AutomationAction]:
    action_type = action.action_type

    if action_type == "create_file":
        return _complete_create(
            action,
            "file",
        )

    if action_type == "create_folder":
        return _complete_create(
            action,
            "folder",
        )

    if action_type == "open_folder":
        return _complete_open_folder(
            action
        )

    if action_type == "list_directory":
        return _complete_listing(
            action
        )

    if action_type == "find_file":
        return _complete_find(
            action
        )

    if action_type in {
        "rename_file",
        "rename_folder",
    }:
        return _complete_rename(
            action
        )

    if action_type in {
        "move_file",
        "copy_file",
    }:
        return _complete_transfer(
            action
        )

    if action_type in {
        "delete_file",
        "delete_folder",
    }:
        return _complete_delete(
            action
        )

    if action_type == "delete_all_matches":
        return _complete_delete_all(
            action
        )

    return action