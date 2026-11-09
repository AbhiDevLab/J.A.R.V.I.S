from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional


# ------------------------------------------------------------------
# Built-in desktop application catalogue.
#
# Values are executable names and/or common Windows installation locations.
# Additional apps are discovered at runtime from exact Start Menu shortcuts
# and Windows App Paths registry entries; spoken text is never treated as an
# arbitrary shell command or executable path.
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

    "telegram": (
        "Telegram.exe",
        os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Telegram Desktop\Telegram.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe"),
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

    "telegram desktop": "telegram",

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


def discover_application_shortcuts() -> list[tuple[str, str]]:
    """Return Start Menu application shortcuts as (display name, path) pairs.

    This covers ordinary Win32 applications and many packaged apps that
    register a Start Menu shortcut. It deliberately does not scan arbitrary
    folders or infer an executable from a user's spoken text.
    """
    roots = []
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("PROGRAMDATA")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if programdata:
        roots.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

    found: list[tuple[str, str]] = []
    seen_paths = set()
    examined = 0
    for root in roots:
        if not root.is_dir():
            continue
        for current, directories, filenames in os.walk(root):
            directories[:] = [
                name for name in directories
                if not name.startswith(".")
            ]
            for filename in filenames:
                if not filename.lower().endswith(".lnk"):
                    continue
                path = Path(current) / filename
                key = str(path).casefold()
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                found.append((normalize_application_name(path.stem), str(path)))
                examined += 1
                if examined >= 5000:
                    return found
    return found


def _resolve_app_path_registry(name: str) -> Optional[str]:
    """Resolve an exact executable name through Windows App Paths registry keys."""
    if os.name != "nt":
        return None
    normalized = normalize_application_name(name)
    canonical = ALIASES.get(normalized, normalized)
    executable_names = {
        f"{normalized.replace(' ', '')}.exe",
        f"{canonical.replace(' ', '')}.exe",
    }
    try:
        import winreg
    except Exception:
        return None

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        for executable_name in executable_names:
            try:
                with winreg.OpenKey(hive, base + "\\" + executable_name) as key:
                    value, _kind = winreg.QueryValueEx(key, None)
                candidate = str(value or "").strip().strip('"')
                path = Path(candidate)
                if path.is_file():
                    return str(path)
            except (OSError, ValueError):
                continue
    return None


def discover_application_registry_names() -> set[str]:
    """Enumerate exact executable names registered under Windows App Paths."""
    if os.name != "nt":
        return set()
    try:
        import winreg
    except Exception:
        return set()

    names: set[str] = set()
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, base) as key:
                index = 0
                while True:
                    try:
                        entry = winreg.EnumKey(key, index)
                    except OSError:
                        break
                    index += 1
                    if str(entry).casefold().endswith(".exe"):
                        name = normalize_application_name(Path(entry).stem)
                        if name:
                            names.add(name)
        except OSError:
            continue
    return names


def discover_start_menu_app_ids() -> list[tuple[str, str]]:
    """Discover Windows Start-menu apps as exact (display name, AUMID) pairs.

    Get-StartApps is read-only and returns the Application User Model IDs used
    by Windows to identify packaged apps. PowerShell receives a fixed command;
    no spoken or user-supplied string is interpolated into it.
    """
    if os.name != "nt":
        return []

    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        fallback = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if fallback.is_file():
            powershell = str(fallback)
    if not powershell:
        return []

    command = (
        "$ErrorActionPreference='Stop'; "
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        payload = json.loads(result.stdout)
        rows = payload if isinstance(payload, list) else [payload]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return []

    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows[:5000]:
        if not isinstance(row, dict):
            continue
        display_name = normalize_application_name(row.get("Name", ""))
        app_id = str(row.get("AppID", "") or "").strip()
        # AUMIDs are identifiers, not arbitrary shell strings. Reject path
        # separators, control chars and malformed IDs before building a shell URI.
        if (
            not display_name
            or not app_id
            or len(app_id) > 512
            or not re.fullmatch(r"[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+", app_id)
        ):
            continue
        item = (display_name, app_id)
        if item not in seen:
            seen.add(item)
            found.append(item)
    return found


def _resolve_packaged_app_aumid(name: str) -> Optional[str]:
    """Resolve one exact installed Start app name to its validated AUMID."""
    candidates = _application_name_candidates(name)
    matches = {
        app_id
        for display_name, app_id in discover_start_menu_app_ids()
        if display_name in candidates
    }
    if len(matches) == 1:
        return next(iter(matches))
    return None


def resolve_shortcut_target(shortcut_path: str) -> Optional[str]:
    """Read a Windows .lnk target using the COM ShellLink automation object."""
    if os.name != "nt":
        return None
    try:
        from comtypes.client import CreateObject
        shell = CreateObject("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        target = str(shortcut.TargetPath or "").strip()
        return target or None
    except Exception:
        return None


def _application_name_candidates(name: str) -> set[str]:
    normalized = normalize_application_name(name)
    canonical = ALIASES.get(normalized, normalized)
    candidates = {normalized, canonical}
    candidates.update(
        alias for alias, target in ALIASES.items()
        if target == canonical
    )
    return {item for item in candidates if item}


def application_name_variants(name: str) -> set[str]:
    """Names usable for exact matching against live top-level window titles."""
    return _application_name_candidates(name)


def application_executable_names(name: str) -> set[str]:
    """Return exact executable basenames that identify one requested app."""
    normalized = normalize_application_name(name)
    canonical = ALIASES.get(normalized, normalized)
    executable_names: set[str] = set()

    for candidate in APPLICATIONS.get(canonical, ()):
        basename = os.path.basename(os.path.expandvars(candidate)).casefold()
        if basename.endswith(".exe"):
            executable_names.add(basename)

    registered = _resolve_app_path_registry(canonical)
    if registered:
        executable_names.add(Path(registered).name.casefold())

    display_candidates = _application_name_candidates(name)
    for display_name, shortcut_path in discover_application_shortcuts():
        if display_name not in display_candidates:
            continue
        target = resolve_shortcut_target(shortcut_path)
        if target:
            basename = Path(target).name.casefold()
            # These are Windows shell hosts rather than the app's process.
            if basename not in {
                "explorer.exe",
                "applicationframehost.exe",
                "rundll32.exe",
                "shellhost.exe",
            } and basename.endswith(".exe"):
                executable_names.add(basename)

    # Exact-name fallback permits graceful control of a running Win32 app even
    # when it has no Start Menu shortcut. It never performs substring matching.
    executable_names.add((canonical.replace(" ", "") + ".exe").casefold())
    return executable_names


def resolve_application(
    name: str,
) -> Optional[str]:
    """
    Resolve a normalized application name into an executable or .lnk path.

    Resolution order: built-in paths, Windows App Paths, then a unique
    exact-name Start Menu shortcut. Returns None when no safe match exists.
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
        (),
    )

    for candidate in candidates:
        if not candidate:
            continue

        # First try PATH resolution.
        path_match = shutil.which(candidate)
        if path_match:
            return path_match

        # Then try direct filesystem path.
        path = Path(candidate)
        if path.is_file():
            return str(path)

    # Resolve registered applications with an exact App Paths registry key.
    registered = _resolve_app_path_registry(canonical)
    if registered:
        return registered

    # Finally, allow a unique exact-name Start Menu shortcut. The executor
    # launches the .lnk through Windows ShellExecute rather than CreateProcess.
    display_candidates = _application_name_candidates(name)
    shortcuts = [
        path for display_name, path in discover_application_shortcuts()
        if display_name in display_candidates
    ]
    unique = list(dict.fromkeys(shortcuts))
    if len(unique) == 1:
        return unique[0]
    if unique:
        resolved_targets = {
            resolve_shortcut_target(path) or path
            for path in unique
        }
        if len(resolved_targets) == 1:
            return unique[0]

    # Packaged / Microsoft Store apps may have no ordinary .lnk or accessible
    # executable path. Resolve their exact Start-menu AUMID and let Explorer
    # activate the registered Windows application.
    app_id = _resolve_packaged_app_aumid(name)
    if app_id:
        return f"apps-folder:{app_id}"
    return None

def canonical_application_name(name: str) -> Optional[str]:
    """Return the canonical identity for a known or discoverable installed app."""
    normalized = normalize_application_name(name)
    canonical = ALIASES.get(normalized, normalized)
    if canonical in APPLICATIONS:
        return canonical
    if _resolve_app_path_registry(canonical):
        return canonical
    candidates = _application_name_candidates(name)
    if any(display_name in candidates for display_name, _path in discover_application_shortcuts()):
        return canonical
    return None


def find_application_reference(text: str) -> Optional[str]:
    """Find one known or Start-Menu-discovered app name in natural language."""
    value = normalize_application_name(text)
    candidates = set(APPLICATIONS) | set(ALIASES)
    candidates.update(
        display_name for display_name, _path in discover_application_shortcuts()
        if display_name
    )
    candidates.update(discover_application_registry_names())
    matches = []
    for candidate in sorted(candidates, key=len, reverse=True):
        if re.search(
            rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])",
            value,
            re.IGNORECASE,
        ):
            canonical = ALIASES.get(candidate, candidate)
            if canonical not in matches:
                matches.append(canonical)
    return matches[0] if len(matches) == 1 else None


def parse_hindi_application_command(text: str):
    """Normalize a small, explicit set of Hindi/Hinglish app-control phrases."""
    value = normalize_application_name(text)
    patterns = (
        (
            "close",
            r"^(?:is\s+)?(.+?)\s+(?:ko\s+)?(?:band\s+karna\s+hai|band\s+karo|band\s+kijiye|close\s+karna\s+hai)$",
        ),
        (
            "open",
            r"^(?:is\s+)?(.+?)\s+(?:ko\s+)?(?:open\s+karna\s+hai|kholna\s+hai|khol\s+do)$",
        ),
    )
    for action, pattern in patterns:
        match = re.match(pattern, value, re.IGNORECASE)
        if not match:
            continue
        application = find_application_reference(match.group(1))
        if application:
            return action, application
    return None
