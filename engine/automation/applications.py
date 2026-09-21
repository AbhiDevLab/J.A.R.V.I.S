from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Optional


# ------------------------------------------------------------------
# Known desktop applications.
#
# Values are executable names and/or common Windows installation
# locations. Only applications defined here can be launched by the
# low-risk open_application action.
# ------------------------------------------------------------------

APPLICATIONS: Dict[str, tuple[str, ...]] = {
    "chrome": (
        "chrome.exe",
        os.path.expandvars(
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"
        ),
        os.path.expandvars(
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"
        ),
        os.path.expandvars(
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
        ),
    ),

    "edge": (
        "msedge.exe",
        os.path.expandvars(
            r"%PROGRAMFILES(x86)%\Microsoft\Edge\Application\msedge.exe"
        ),
        os.path.expandvars(
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"
        ),
    ),

    "vscode": (
        "code.exe",
        os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
        ),
        os.path.expandvars(
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe"
        ),
    ),

    "spotify": (
        "spotify.exe",
        os.path.expandvars(
            r"%APPDATA%\Spotify\Spotify.exe"
        ),
    ),

    "notepad": (
        "notepad.exe",
    ),

    "calculator": (
        "calc.exe",
    ),

    "paint": (
        "mspaint.exe",
    ),

    "explorer": (
        "explorer.exe",
    ),

    "task manager": (
        "taskmgr.exe",
    ),

    "command prompt": (
        "cmd.exe",
    ),

    "terminal": (
        "wt.exe",
    ),
}


# Multiple natural-language names can refer to the same application.
ALIASES: Dict[str, str] = {
    "google chrome": "chrome",
    "chrome browser": "chrome",

    "microsoft edge": "edge",
    "edge browser": "edge",

    "visual studio code": "vscode",
    "vs code": "vscode",
    "visual studio": "vscode",

    "spotify desktop": "spotify",

    "file explorer": "explorer",
    "windows explorer": "explorer",

    "task manager": "task manager",

    "cmd": "command prompt",
    "command line": "command prompt",

    "windows terminal": "terminal",
}


def normalize_application_name(
    name: str,
) -> str:
    """
    Normalize an application name received from speech.

    Examples:
        "Open Chrome." -> "chrome"
        "Google Chrome!" -> "google chrome"
        "VS Code" -> "vs code"
    """

    text = str(name or "").strip().lower()

    # Remove punctuation while preserving spaces.
    cleaned = "".join(
        char
        if char.isalnum() or char.isspace()
        else " "
        for char in text
    )

    return " ".join(
        cleaned.split()
    )


def resolve_application(
    name: str,
) -> Optional[str]:
    """
    Resolve a normalized application name into an executable path.

    Returns:
        Executable path/name if found, otherwise None.
    """

    normalized = normalize_application_name(
        name
    )

    canonical = ALIASES.get(
        normalized,
        normalized,
    )

    candidates = APPLICATIONS.get(
        canonical,
    )

    if not candidates:
        return None

    for candidate in candidates:
        if not candidate:
            continue

        # First try PATH resolution.
        path_match = shutil.which(
            candidate
        )

        if path_match:
            return path_match

        # Then try direct filesystem path.
        path = Path(candidate)

        if path.is_file():
            return str(path)

    return None