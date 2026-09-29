from __future__ import annotations

import os
import re
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


LOCATION_WRAPPER_PREFIXES = (
    "my ",
    "the ",
)

LOCATION_WRAPPER_SUFFIXES = (
    " folder",
    " directory",
    " project",
    " workspace",
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


def normalize_filesystem_text(
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

    cleaned = "".join(
        char
        if char.isalnum()
        or char.isspace()
        or char in r"\/:._-~$%"
        else " "
        for char in value.lower()
    )

    return " ".join(
        cleaned.split()
    )


def _clean_named_location(
    text: str,
) -> str:
    """
    Clean conversational location words without changing
    ordinary filesystem names.

    Examples:
        "my J.A.R.V.I.S project" -> "J.A.R.V.I.S"
        "the Web folder" -> "Web"
        "current workspace" -> "current workspace"
    """

    value = " ".join(
        str(text or "").strip().split()
    )

    lowered = value.casefold()

    for prefix in LOCATION_WRAPPER_PREFIXES:
        if lowered.startswith(prefix):
            value = value[len(prefix):].strip()
            lowered = value.casefold()
            break

    for suffix in LOCATION_WRAPPER_SUFFIXES:
        if lowered.endswith(suffix):
            value = value[:-len(suffix)].strip()
            break

    return value


def _natural_location_parts(
    reference: str,
) -> list[str]:
    """
    Split conversational hierarchy descriptions such as:

        J.A.R.V.I.S folder under Web folder under Dev folder
        J.A.R.V.I.S inside Web inside Dev

    The first item is the deepest target and the last item
    is the broadest ancestor.
    """

    return [
        _clean_named_location(part)
        for part in re.split(
            r"\s+(?:under|inside|within)\s+",
            reference,
            flags=re.IGNORECASE,
        )
        if _clean_named_location(part)
    ]


def _canonical_directory_alias(
    text: str,
) -> Optional[str]:
    normalized = normalize_filesystem_text(
        _clean_named_location(text)
    )

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

    return DIRECTORY_ALIASES.get(
        normalized
    )


def is_known_directory_reference(
    text: str,
) -> bool:
    return (
        _canonical_directory_alias(text)
        is not None
    )


def resolve_path(
    path_text: str,
    base_directory: Optional[Path] = None,
) -> Path:
    raw = str(
        path_text or ""
    ).strip()

    while (
        len(raw) >= 2
        and raw[0] == raw[-1]
        and raw[0] in {'"', "'"}
    ):
        raw = raw[1:-1].strip()

    alias = _canonical_directory_alias(
        raw
    )

    if alias:
        return SPECIAL_DIRECTORIES[
            alias
        ]

    expanded = os.path.expandvars(
        os.path.expanduser(raw)
    )

    path = Path(expanded)

    if not path.is_absolute():
        base = (
            base_directory
            or Path.cwd()
        )
        path = base / path

    return path.resolve(
        strict=False
    )


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
    """
    Return filesystem roots used by J.A.R.V.I.S.

    Fast/common locations are searched first.
    The Windows Dev and Users trees are then searched
    recursively as broader project/user scopes.
    """

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

    # Windows system drive, e.g. C:\
    drive_root = Path(
        Path.home().anchor
    )

    if drive_root:
        roots.extend(
            [
                drive_root / "Dev",
                drive_root / "Users",
            ]
        )

    unique_roots = []
    seen = set()

    for root in roots:
        try:
            resolved = root.resolve(
                strict=False
            )

            if (
                not resolved.exists()
                or not resolved.is_dir()
            ):
                continue

            if resolved in seen:
                continue

            seen.add(resolved)
            unique_roots.append(
                resolved
            )

        except Exception:
            continue

    return unique_roots

def _is_full_search_root(
    root: Path,
) -> bool:
    """
    C:\\Dev and C:\\Users are intentionally scanned
    recursively without the normal application/system
    exclusion list.
    """

    drive_root = Path(
        Path.home().anchor
    )

    if not drive_root:
        return False

    full_roots = {
        (
            drive_root / "Dev"
        ).resolve(
            strict=False
        ),
        (
            drive_root / "Users"
        ).resolve(
            strict=False
        ),
    }

    return root.resolve(
        strict=False
    ) in full_roots

def _file_match_rank(
    filename: str,
    target: str,
) -> Optional[int]:
    """Rank a filename against a user-provided file reference.

    Lower rank means a stronger match:

        0 -> exact filename
        1 -> exact filename stem
        2 -> target contained in filename stem
        None -> no match"""
    filename_lower = filename.casefold()
    target_lower = target.casefold()

    stem_lower = Path(
        filename
    ).stem.casefold()

    if filename_lower == target_lower:
        return 0

    if stem_lower == target_lower:
        return 1

    if target_lower in stem_lower:
        return 2

    return None

def search_paths(
    name: str,
    expected_type: Optional[str] = None,
    max_results: Optional[int] = 10,
    search_roots: Optional[List[Path]] = None,
) -> List[Path]:
    """
    Search for a file or folder by name.

    File matching uses ranked resolution:

        0 -> exact filename
        1 -> exact filename stem
        2 -> target contained in filename stem

    Only the best available rank is returned.

    Folder matching remains exact-match only.

    Search scope:
        - Current working directory
        - Desktop
        - Downloads
        - Documents
        - Pictures
        - Videos
        - Music
        - User home
        - C:\\Dev recursively
        - C:\\Users recursively

    C:\\Dev and C:\\Users are intentionally searched
    without the normal excluded-directory filter.

    max_results=None means exhaustive search.
    """

    target = _clean_reference(
        name
    )

    if not target:
        return []

    direct = resolve_path(
        target
    )

    if _matches_expected_type(
        direct,
        expected_type,
    ):
        return [direct]

    # Explicit paths should not trigger
    # a broad recursive search.
    if (
        "\\" in target
        or "/" in target
        or ":" in target
    ):
        return []

    matches: List[Path] = []
    ranked_file_matches: List[tuple[int, Path]] = []
    seen = set()

    roots = (
        search_roots
        if search_roots is not None
        else _search_roots()
    )

    for root in roots:
        if (
            not root.exists()
            or not root.is_dir()
        ):
            continue

        full_scope = _is_full_search_root(
            root
        )

        try:
            for (
                current_root,
                dir_names,
                file_names,
            ) in os.walk(
                root,
                topdown=True,
            ):
                if not full_scope:
                    dir_names[:] = [
                        directory
                        for directory in dir_names
                        if directory.casefold()
                        not in SEARCH_EXCLUDED_DIRECTORIES
                    ]

                current_path = Path(
                    current_root
                )

                # Folder search remains exact-match only.
                if expected_type != "file":
                    for directory in dir_names:
                        if (
                            directory.casefold()
                            != target.casefold()
                        ):
                            continue

                        match = (
                            current_path
                            / directory
                        ).resolve(
                            strict=False
                        )

                        if match in seen:
                            continue

                        seen.add(match)
                        matches.append(match)

                # File search uses ranked filename matching.
                if expected_type != "folder":
                    for filename in file_names:
                        rank = _file_match_rank(
                            filename,
                            target,
                        )

                        if rank is None:
                            continue

                        match = (
                            current_path
                            / filename
                        ).resolve(
                            strict=False
                        )

                        if match in seen:
                            continue

                        seen.add(match)

                        ranked_file_matches.append(
                            (
                                rank,
                                match,
                            )
                        )

        except Exception as exc:
            print(
                f"Filesystem search warning: {exc}"
            )

    # Keep only the strongest match class.
    #
    # Example:
    #
    #   query: "Godmother"
    #
    #   Godmother.pdf          rank 1
    #   Godmother.jpg          rank 1
    #   MyGodmotherNotes.txt   rank 2
    #
    # Only the rank-1 matches should be considered.
    if ranked_file_matches:
        ranked_file_matches.sort(
            key=lambda item: (
                item[0],
                str(item[1]).casefold(),
            )
        )

        best_rank = ranked_file_matches[0][0]

        best_matches = [
            match
            for rank, match
            in ranked_file_matches
            if rank == best_rank
        ]

        if max_results is not None:
            best_matches = best_matches[
                :max_results
            ]

        matches.extend(
            best_matches
        )

    return matches

def _resolve_folder_name(
    reference: str,
    search_roots: Optional[List[Path]] = None,
) -> tuple[Optional[Path], str]:
    """Resolve one exact folder name without guessing."""

    target = _clean_named_location(
        _clean_reference(reference)
    )

    if not target:
        return None, "No folder name was provided."

    direct = resolve_path(target)

    if direct.is_dir():
        return direct, ""

    current = Path.cwd().resolve(
        strict=False
    )

    for parent in [
        current,
        *current.parents,
    ]:
        if parent.name.casefold() == target.casefold():
            return parent, ""

    matches = search_paths(
        target,
        expected_type="folder",
        max_results=50,
        search_roots=search_roots,
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

    return None, f"I could not find {target}."


def _resolve_natural_folder_hierarchy(
    reference: str,
) -> tuple[Optional[Path], str]:
    """
    Resolve a spoken hierarchy from broadest ancestor to
    deepest child.

    Example:
        "J.A.R.V.I.S folder under Web folder under Dev folder"

    resolves as:
        C:\Dev -> Web -> J.A.R.V.I.S
    """

    parts = _natural_location_parts(
        _clean_reference(reference)
    )

    if len(parts) <= 1:
        return None, ""

    # Work from the broadest location toward the target.
    parts = list(reversed(parts))
    first = parts[0]

    drive_match = re.fullmatch(
        r"([a-zA-Z]):(?:\\s+drive)?",
        first.strip(),
    )

    if drive_match:
        current = Path(
            f"{drive_match.group(1).upper()}:\\"
        )
        if not current.is_dir():
            return None, f"I could not find {first}."
    else:
        current, error = _resolve_folder_name(
            first
        )
        if current is None:
            return None, error

    for child_name in parts[1:]:
        matches = [
            child
            for child in current.iterdir()
            if child.is_dir()
            and child.name.casefold()
            == child_name.casefold()
        ]

        if len(matches) == 1:
            current = matches[0].resolve(
                strict=False
            )
            continue

        if len(matches) > 1:
            locations = "; ".join(
                str(match)
                for match in matches
            )
            return (
                None,
                f"I found multiple matches for "
                f"{child_name}: {locations}.",
            )

        return (
            None,
            f"I could not find {child_name} inside "
            f"{current}.",
        )

    return current, ""


def resolve_existing_path(
    reference: str,
    expected_type: str,
) -> tuple[Optional[Path], str]:
    """
    Resolve a user-provided file/folder reference.

    Resolution order:
        1. Natural hierarchical location
        2. Direct/explicit path
        3. Current/ancestor folder lookup
        4. Common filesystem search

    Multiple matches are reported instead of guessing.
    """

    target = _clean_reference(reference)

    if not target:
        return (
            None,
            "No path was provided.",
        )

    # Friendly workspace/current-location aliases.
    normalized_target = normalize_filesystem_text(
        target
    )

    if expected_type == "folder" and normalized_target in {
        "current folder",
        "current directory",
        "this folder",
        "current workspace",
        "this workspace",
        "my current folder",
        "my current directory",
        "my current workspace",
    }:
        return (
            Path.cwd().resolve(strict=False),
            "",
        )

    # Resolve "X under Y under Z" / "X inside Y inside Z"
    # before broad filesystem search. This prevents a
    # common folder name from being chosen from elsewhere.
    if expected_type == "folder":
        hierarchical, hierarchy_error = (
            _resolve_natural_folder_hierarchy(target)
        )
        if hierarchical is not None:
            return hierarchical, ""
        if hierarchy_error:
            return None, hierarchy_error

    direct = resolve_path(target)

    if _matches_expected_type(
        direct,
        expected_type,
    ):
        return direct, ""

    if expected_type == "folder":
        cleaned_target = _clean_named_location(target)

        # Resolve a folder name relative to the current
        # workspace/working directory.
        if (
            cleaned_target
            and "\\" not in cleaned_target
            and "/" not in cleaned_target
            and ":" not in cleaned_target
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
                    == cleaned_target.casefold()
                ):
                    return parent, ""

    search_target = (
        _clean_named_location(target)
        if expected_type == "folder"
        else target
    )

    matches = search_paths(
        search_target,
        expected_type=expected_type,
        max_results=50,
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
            f"{search_target}: {locations}.",
        )

    return (
        None,
        f"I could not find {search_target}.",
    )

def open_folder(
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

    try:
        os.startfile(
            str(path)
        )

        return (
            True,
            f"Opening {path.name or path_text}.",
        )

    except Exception as exc:
        print(
            f"Folder open error: {exc}"
        )

        return (
            False,
            f"I could not open {path_text}.",
        )

def open_file(
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
        os.startfile(
            str(path)
        )

        return (
            True,
            f"Opening {path.name}.",
        )

    except Exception as exc:
        print(
            f"File open error: {exc}"
        )

        return (
            False,
            f"I could not open {path_text}.",
        )

def list_directory(
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

        return (
            False,
            f"I could not read {path_text}.",
        )

    if not entries:
        return (
            True,
            f"{path.name or path_text} is empty.",
        )

    folders = sum(
        item.is_dir()
        for item in entries
    )

    files = (
        len(entries) - folders
    )

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

    remaining = (
        len(entries)
        - len(preview)
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
        return (
            False,
            "No file name was provided.",
        )

    if directory:
        directory_path, resolution_error = (
            resolve_existing_path(
                directory,
                "folder",
            )
        )

        if directory_path is None:
            return (
                False,
                resolution_error
                or f"I could not find {directory}.",
            )

        matches = search_paths(
            target_name,
            expected_type="file",
            max_results=50,
            search_roots=[
                directory_path,
            ],
        )

    else:
        matches = search_paths(
            target_name,
            expected_type="file",
            max_results=50,
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

    # Show the detailed locations in the HUD,
    # but keep the spoken response short.
    try:
        from engine.command import _safe_display

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
                (
                    f"I found {len(matches)} matches "
                    f"for {target_name}:\n\n"
                    + "\n".join(location_lines)
                    + "\n\n"
                    "Say the number to select a specific file."
                )
            ),
        )

    except Exception as exc:
        print(
            f"Find-file UI display error: {exc}"
        )

    return (
        True,
        f"I found {len(matches)} matches "
        f"for {target_name}.",
    )

def create_folder(
    path_text: str,
):
    path = resolve_path(
        path_text
    )

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
    path = resolve_path(
        path_text
    )

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
    source, resolution_error = (
        resolve_existing_path(
            source_text,
            expected_type,
        )
    )

    if source is None:
        return (
            False,
            resolution_error
            or f"I could not find {source_text}.",
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

    target = Path(
        target_raw
    )

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
        source.rename(
            destination
        )

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
    source, resolution_error = (
        resolve_existing_path(
            source_text,
            "file",
        )
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
    source, resolution_error = (
        resolve_existing_path(
            source_text,
            "file",
        )
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
    path, resolution_error = (
        resolve_existing_path(
            path_text,
            "file",
        )
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
    path, resolution_error = (
        resolve_existing_path(
            path_text,
            "folder",
        )
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
        shutil.rmtree(
            path
        )

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