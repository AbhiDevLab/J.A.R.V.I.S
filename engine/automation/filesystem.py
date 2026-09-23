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

SEARCH_EXCLUDED_DIRECTORIES = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "appdata",
    "application data",
    "local settings",
    "node_modules",
    ".git",
    "__pycache__",
    "envjarvis",
    "venv",
    ".venv",
}


def _clean_reference(
    value: str,
) -> str:
    text = str(
        value or ""
    ).strip()

    while (
        len(text) >= 2
        and text[0] == text[-1]
        and text[0] in {'"', "'"}
    ):
        text = text[1:-1].strip()

    return text.rstrip(
        ".,!?;:"
    ).strip()


def _matches_expected_type(
    path: Path,
    expected_type: Optional[str],
) -> bool:
    if expected_type == "file":
        return path.is_file()

    if expected_type == "folder":
        return path.is_dir()

    return path.exists()


def _search_roots() -> List[Path]:
    roots = [
        Path.cwd(),
        SPECIAL_DIRECTORIES["desktop"],
        SPECIAL_DIRECTORIES["downloads"],
        SPECIAL_DIRECTORIES["documents"],
        SPECIAL_DIRECTORIES["pictures"],
        SPECIAL_DIRECTORIES["videos"],
        SPECIAL_DIRECTORIES["music"],
        Path.home(),
    ]

    unique_roots = []
    seen = set()

    for root in roots:
        try:
            resolved = root.resolve(
                strict=False
            )

            if resolved in seen:
                continue

            seen.add(resolved)
            unique_roots.append(resolved)

        except Exception:
            continue

    return unique_roots


def search_paths(
    name: str,
    expected_type: Optional[str] = None,
    max_results: int = 10,
) -> List[Path]:
    """
    Search for an exact file/folder name in common
    user locations.

    Matching is case-insensitive.
    """

    target = _clean_reference(
        name
    )

    if not target:
        return []

    direct = resolve_path(target)

    if _matches_expected_type(
        direct,
        expected_type,
    ):
        return [direct]

    # Explicit paths should not trigger a broad search.
    if (
        "\\" in target
        or "/" in target
        or ":" in target
    ):
        return []

    target_lower = target.casefold()

    matches: List[Path] = []
    seen = set()

    for root in _search_roots():
        if (
            not root.exists()
            or not root.is_dir()
        ):
            continue

        try:
            for (
                current_root,
                dir_names,
                file_names,
            ) in os.walk(
                root,
                topdown=True,
            ):
                dir_names[:] = [
                    directory
                    for directory in dir_names
                    if directory.casefold()
                    not in SEARCH_EXCLUDED_DIRECTORIES
                ]

                current_path = Path(
                    current_root
                )

                if expected_type != "file":
                    for directory in dir_names:
                        if (
                            directory.casefold()
                            != target_lower
                        ):
                            continue

                        match = (
                            current_path / directory
                        ).resolve(
                            strict=False
                        )

                        if match in seen:
                            continue

                        seen.add(match)
                        matches.append(match)

                        if len(matches) >= max_results:
                            return matches

                if expected_type != "folder":
                    for filename in file_names:
                        if (
                            filename.casefold()
                            != target_lower
                        ):
                            continue

                        match = (
                            current_path / filename
                        ).resolve(
                            strict=False
                        )

                        if match in seen:
                            continue

                        seen.add(match)
                        matches.append(match)

                        if len(matches) >= max_results:
                            return matches

        except Exception as exc:
            print(
                f"Filesystem search warning: {exc}"
            )

    return matches


def resolve_existing_path(
    reference: str,
    expected_type: str,
) -> tuple[Optional[Path], str]:
    """
    Resolve a user-provided file/folder reference.

    Resolution order:
        1. Explicit/direct path
        2. Ancestor folder with the requested name
        3. Common filesystem search
    """

    target = _clean_reference(
        reference
    )

    if not target:
        return (
            None,
            "No path was provided.",
        )

    direct = resolve_path(target)

    if _matches_expected_type(
        direct,
        expected_type,
    ):
        return direct, ""

    # A very useful case for commands such as:
    # "create folder X in Dev"
    # when JARVIS itself is running inside C:\Dev\...
    if (
        expected_type == "folder"
        and "\\" not in target
        and "/" not in target
        and ":" not in target
    ):
        current = Path.cwd().resolve(
            strict=False
        )

        for parent in [
            current,
            *current.parents,
        ]:
            if (
                parent.name.casefold()
                == target.casefold()
            ):
                return parent, ""

    matches = search_paths(
        target,
        expected_type=expected_type,
        max_results=10,
    )

    if len(matches) == 1:
        return matches[0], ""

    if len(matches) > 1:
        locations = "; ".join(
            str(match)
            for match in matches
        )

        return (
            None,
            f"I found multiple matches for "
            f"{target}: {locations}.",
        )

    return (
        None,
        f"I could not find {target}.",
    )

def search_paths(
    name: str,
    expected_type: Optional[str] = None,
    max_results: int = 10,
) -> List[Path]:
    """
    Search common user locations for an exact filename/folder name.

    Search order:
        1. Current working directory
        2. Desktop
        3. Downloads
        4. Documents
        5. Pictures
        6. Videos
        7. Music
        8. User home directory

    Matching is case-insensitive.
    """

    target = str(name or "").strip()

    while (
        len(target) >= 2
        and target[0] == target[-1]
        and target[0] in {'"', "'"}
    ):
        target = target[1:-1].strip()

    target = target.rstrip(".,!?;:")

    if not target:
        return []

    direct = resolve_path(target)

    if direct.exists():
        if (
            expected_type == "file"
            and not direct.is_file()
        ):
            return []

        if (
            expected_type == "folder"
            and not direct.is_dir()
        ):
            return []

        return [direct]

    # Do not recursively search for an explicit path.
    if (
        "\\" in target
        or "/" in target
        or ":" in target
    ):
        return []

    excluded_directories = {
        "$recycle.bin",
        "system volume information",
        "appdata",
        "application data",
        "local settings",
        "node_modules",
        ".git",
        "__pycache__",
        "envjarvis",
        "venv",
        ".venv",
    }

    roots = [
        Path.cwd(),
        SPECIAL_DIRECTORIES["desktop"],
        SPECIAL_DIRECTORIES["downloads"],
        SPECIAL_DIRECTORIES["documents"],
        SPECIAL_DIRECTORIES["pictures"],
        SPECIAL_DIRECTORIES["videos"],
        SPECIAL_DIRECTORIES["music"],
        Path.home(),
    ]

    unique_roots = []

    seen_roots = set()

    for root in roots:
        try:
            resolved_root = root.resolve(
                strict=False
            )

            if resolved_root in seen_roots:
                continue

            seen_roots.add(resolved_root)
            unique_roots.append(resolved_root)

        except Exception:
            continue

    target_lower = target.casefold()
    matches: List[Path] = []
    seen_matches = set()

    for root in unique_roots:
        if not root.exists() or not root.is_dir():
            continue

        try:
            for (
                current_root,
                dir_names,
                file_names,
            ) in os.walk(
                root,
                topdown=True,
            ):
                dir_names[:] = [
                    directory
                    for directory in dir_names
                    if directory.casefold()
                    not in excluded_directories
                ]

                current_path = Path(
                    current_root
                )

                if expected_type != "file":
                    for directory in dir_names:
                        if (
                            directory.casefold()
                            != target_lower
                        ):
                            continue

                        match = current_path / directory
                        resolved_match = match.resolve(
                            strict=False
                        )

                        if (
                            resolved_match
                            not in seen_matches
                        ):
                            matches.append(match)
                            seen_matches.add(
                                resolved_match
                            )

                        if len(matches) >= max_results:
                            return matches

                if expected_type != "folder":
                    for filename in file_names:
                        if (
                            filename.casefold()
                            != target_lower
                        ):
                            continue

                        match = current_path / filename
                        resolved_match = match.resolve(
                            strict=False
                        )

                        if (
                            resolved_match
                            not in seen_matches
                        ):
                            matches.append(match)
                            seen_matches.add(
                                resolved_match
                            )

                        if len(matches) >= max_results:
                            return matches

        except Exception as exc:
            print(
                f"Filesystem search warning: {exc}"
            )

    return matches

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
    source, resolution_error = resolve_existing_path(
        source_text,
        expected_type,
    )

    if source is None:
        return (
            False,
            resolution_error
            or f"I could not find {source_text}.",
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
    source, resolution_error = resolve_existing_path(
        source_text,
        "file",
    )

    if source is None:
        return (
            False,
            resolution_error
            or f"I could not find {source_text}.",
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
    source, resolution_error = resolve_existing_path(
        source_text,
        "file",
    )

    if source is None:
        return (
            False,
            resolution_error
            or f"I could not find {source_text}.",
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
    path, resolution_error = resolve_existing_path(
        path_text,
        "file",
    )

    if path is None:
        return (
            False,
            resolution_error
            or f"I could not find {path_text}.",
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
    path, resolution_error = resolve_existing_path(
        path_text,
        "folder"
    )
    if path is None:
        return (False, resolution_error or f"I could not find {path_text}.",)

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