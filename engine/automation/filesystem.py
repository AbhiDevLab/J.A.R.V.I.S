from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Optional


SPECIAL_DIRECTORIES = {
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "pictures": Path.home() / "Pictures",
    "videos": Path.home() / "Videos",
    "music": Path.home() / "Music",
}


DIRECTORY_ALIASES = {
    "my desktop": "desktop",
    "desktop folder": "desktop",
    "my downloads": "downloads",
    "download folder": "downloads",
    "downloads folder": "downloads",
    "my documents": "documents",
    "documents folder": "documents",
    "my pictures": "pictures",
    "pictures folder": "pictures",
    "my videos": "videos",
    "videos folder": "videos",
    "my music": "music",
    "music folder": "music",
}


def normalize_filesystem_text(text: str) -> str:
    value = str(text or "").strip()

    while (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {'"', "'"}
    ):
        value = value[1:-1].strip()

    cleaned = "".join(
        char
        if char.isalnum()
        or char.isspace()
        or char in r"\/:._-~$%"
        else " "
        for char in value.lower()
    )

    return " ".join(cleaned.split())


def _canonical_directory_alias(
    text: str,
) -> Optional[str]:
    normalized = normalize_filesystem_text(text)

    for prefix in (
        "my ",
        "the ",
    ):
        if normalized.startswith(prefix):
            normalized = normalized[
                len(prefix):
            ].strip()

    for suffix in (
        " folder",
        " directory",
    ):
        if normalized.endswith(suffix):
            normalized = normalized[
                :-len(suffix)
            ].strip()

    if normalized in SPECIAL_DIRECTORIES:
        return normalized

    return DIRECTORY_ALIASES.get(normalized)


def is_known_directory_reference(
    text: str,
) -> bool:
    return _canonical_directory_alias(text) is not None


def resolve_path(
    path_text: str,
    base_directory: Optional[Path] = None,
) -> Path:
    raw = str(path_text or "").strip()

    while (
        len(raw) >= 2
        and raw[0] == raw[-1]
        and raw[0] in {'"', "'"}
    ):
        raw = raw[1:-1].strip()

    alias = _canonical_directory_alias(raw)

    if alias:
        return SPECIAL_DIRECTORIES[alias]

    expanded = os.path.expandvars(
        os.path.expanduser(raw)
    )

    path = Path(expanded)

    if not path.is_absolute():
        base = base_directory or Path.cwd()
        path = base / path

    return path.resolve(
        strict=False
    )


def open_folder(
    path_text: str,
):
    path = resolve_path(path_text)

    if not path.exists():
        return False, f"I could not find {path_text}."

    if not path.is_dir():
        return False, f"{path_text} is not a folder."

    try:
        os.startfile(str(path))
        return True, f"Opening {path.name or path_text}."
    except Exception as exc:
        print(
            f"Folder open error: {exc}"
        )
        return False, f"I could not open {path_text}."


def list_directory(
    path_text: str,
):
    path = resolve_path(path_text)

    if not path.exists():
        return False, f"I could not find {path_text}."

    if not path.is_dir():
        return False, f"{path_text} is not a folder."

    try:
        entries = sorted(
            path.iterdir(),
            key=lambda item: (
                not item.is_dir(),
                item.name.lower(),
            ),
        )
    except Exception as exc:
        print(
            f"Directory listing error: {exc}"
        )
        return False, f"I could not read {path_text}."

    if not entries:
        return True, f"{path.name or path_text} is empty."

    folders = sum(
        item.is_dir()
        for item in entries
    )
    files = len(entries) - folders

    preview = []

    for item in entries[:10]:
        prefix = (
            "Folder"
            if item.is_dir()
            else "File"
        )
        preview.append(
            f"{prefix} {item.name}"
        )

    remaining = len(entries) - len(
        preview
    )

    message = (
        f"{path.name or path_text} contains "
        f"{folders} folder"
        f"{'s' if folders != 1 else ''} and "
        f"{files} file"
        f"{'s' if files != 1 else ''}. "
        f"Top items: "
        + ", ".join(preview)
    )

    if remaining > 0:
        message += (
            f", and {remaining} more."
        )

    return True, message


def find_file(
    name: str,
    directory: str = "",
):
    target_name = (
        str(name or "")
        .strip()
        .strip('"')
        .strip("'")
    )

    if not target_name:
        return False, "No file name was provided."

    root = (
        resolve_path(directory)
        if str(directory or "").strip()
        else Path.home()
    )

    if not root.exists():
        return False, f"I could not find {directory}."

    if not root.is_dir():
        return False, f"{directory} is not a folder."

    matches: List[Path] = []
    normalized_target = target_name.lower()

    try:
        for (
            current_root,
            dir_names,
            file_names,
        ) in os.walk(
            root,
            topdown=True,
            onerror=lambda error: print(
                f"File search warning: {error}"
            ),
        ):
            dir_names[:] = [
                dirname
                for dirname in dir_names
                if dirname.lower()
                not in {
                    "$recycle.bin",
                    "system volume information",
                }
            ]

            for filename in file_names:
                if (
                    filename.lower()
                    == normalized_target
                ):
                    matches.append(
                        Path(current_root)
                        / filename
                    )

                    if len(matches) >= 10:
                        break

            if len(matches) >= 10:
                break

    except Exception as exc:
        print(
            f"File search error: {exc}"
        )
        return (
            False,
            f"I could not search for {target_name}.",
        )

    if not matches:
        return (
            False,
            f"I could not find {target_name}.",
        )

    locations = "; ".join(
        str(match)
        for match in matches
    )

    if len(matches) == 1:
        return (
            True,
            f"I found {target_name} at {locations}.",
        )

    return (
        True,
        f"I found {len(matches)} matches "
        f"for {target_name}: {locations}.",
    )


def create_folder(
    path_text: str,
):
    path = resolve_path(path_text)

    if path.exists():
        return (
            False,
            f"{path_text} already exists.",
        )

    try:
        path.mkdir(
            parents=True,
            exist_ok=False,
        )
        return (
            True,
            f"Created folder {path.name}.",
        )
    except Exception as exc:
        print(
            f"Folder creation error: {exc}"
        )
        return (
            False,
            f"I could not create folder {path_text}.",
        )
        
def create_file(
    path_text: str,
    content: str = "",
):
    path = resolve_path(path_text)

    if path.exists():
        return (
            False,
            f"{path_text} already exists.",
        )

    try:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

        return (
            True,
            f"Created file {path.name}.",
        )

    except Exception as exc:
        print(
            f"File creation error: {exc}"
        )
        return (
            False,
            f"I could not create file {path_text}.",
        )


def rename_path(
    source_text: str,
    target_text: str,
    expected_type: str,
):
    source = resolve_path(source_text)

    if not source.exists():
        return (
            False,
            f"I could not find {source_text}.",
        )

    if (
        expected_type == "file"
        and not source.is_file()
    ):
        return (
            False,
            f"{source_text} is not a file.",
        )

    if (
        expected_type == "folder"
        and not source.is_dir()
    ):
        return (
            False,
            f"{source_text} is not a folder.",
        )

    target_raw = (
        str(target_text or "")
        .strip()
        .strip('"')
        .strip("'")
    )

    if not target_raw:
        return (
            False,
            "No new name was provided.",
        )

    target = Path(target_raw)

    if target.is_absolute():
        destination = target
    else:
        destination = (
            source.parent / target
        )

    destination = destination.resolve(
        strict=False
    )

    if destination.exists():
        return (
            False,
            f"{target_text} already exists.",
        )

    try:
        source.rename(destination)

        return (
            True,
            f"Renamed {source.name} "
            f"to {destination.name}.",
        )

    except Exception as exc:
        print(
            f"Rename error: {exc}"
        )
        return (
            False,
            f"I could not rename {source_text}.",
        )


def copy_file(
    source_text: str,
    destination_text: str,
):
    source = resolve_path(
        source_text
    )
    destination = resolve_path(
        destination_text
    )

    if not source.exists():
        return (
            False,
            f"I could not find {source_text}.",
        )

    if not source.is_file():
        return (
            False,
            f"{source_text} is not a file.",
        )

    if (
        destination.exists()
        and destination.is_dir()
    ):
        destination = (
            destination / source.name
        )

    if destination.exists():
        return (
            False,
            f"{destination_text} already exists.",
        )

    try:
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

        return (
            True,
            f"Copied {source.name} "
            f"to {destination}.",
        )

    except Exception as exc:
        print(
            f"File copy error: {exc}"
        )
        return (
            False,
            f"I could not copy {source_text}.",
        )


def move_file(
    source_text: str,
    destination_text: str,
):
    source = resolve_path(
        source_text
    )
    destination = resolve_path(
        destination_text
    )

    if not source.exists():
        return (
            False,
            f"I could not find {source_text}.",
        )

    if not source.is_file():
        return (
            False,
            f"{source_text} is not a file.",
        )

    if (
        destination.exists()
        and destination.is_dir()
    ):
        destination = (
            destination / source.name
        )

    if destination.exists():
        return (
            False,
            f"{destination_text} already exists.",
        )

    try:
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.move(
            str(source),
            str(destination),
        )

        return (
            True,
            f"Moved {source.name} "
            f"to {destination}.",
        )

    except Exception as exc:
        print(
            f"File move error: {exc}"
        )
        return (
            False,
            f"I could not move {source_text}.",
        )


def delete_file(
    path_text: str,
):
    path = resolve_path(
        path_text
    )

    if not path.exists():
        return (
            False,
            f"I could not find {path_text}.",
        )

    if not path.is_file():
        return (
            False,
            f"{path_text} is not a file.",
        )

    try:
        path.unlink()

        return (
            True,
            f"Deleted {path.name}.",
        )

    except Exception as exc:
        print(
            f"File deletion error: {exc}"
        )
        return (
            False,
            f"I could not delete {path_text}.",
        )


def delete_folder(
    path_text: str,
):
    path = resolve_path(
        path_text
    )

    if not path.exists():
        return (
            False,
            f"I could not find {path_text}.",
        )

    if not path.is_dir():
        return (
            False,
            f"{path_text} is not a folder.",
        )

    if (
        path.anchor
        and path == Path(path.anchor)
    ):
        return (
            False,
            "I will not delete a filesystem root.",
        )

    try:
        shutil.rmtree(path)

        return (
            True,
            f"Deleted folder {path.name}.",
        )

    except Exception as exc:
        print(
            f"Folder deletion error: {exc}"
        )
        return (
            False,
            f"I could not delete {path_text}.",
        )