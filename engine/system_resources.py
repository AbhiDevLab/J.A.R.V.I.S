"""Bounded, read-only inventory of local Windows system resources.

The collector intentionally avoids process command lines, document contents,
recursive drive scans, registry writes, and persistent storage. File/folder
search remains on-demand through the existing filesystem automation module.
"""
from __future__ import annotations

import csv
import ctypes
import io
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from engine.automation import applications as _application_discovery


def _is_windows() -> bool:
    return os.name == "nt"


def _bounded_limit(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    return max(1, min(maximum, parsed))


def _parse_memory_kb(value: str) -> int | None:
    match = re.search(r"[\d,]+", str(value or ""))
    if not match:
        return None
    try:
        return int(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_tasklist_csv(output: str, *, max_items: int = 250) -> list[dict[str, Any]]:
    """Parse tasklist CSV output without retaining command lines or extra data."""
    limit = _bounded_limit(max_items, 250, 1000)
    processes: list[dict[str, Any]] = []
    try:
        rows = csv.reader(io.StringIO(str(output or "").lstrip("\ufeff")))
        for row in rows:
            if len(row) < 2:
                continue
            image_name = str(row[0] or "").strip()
            try:
                process_id = int(str(row[1]).replace(",", "").strip())
            except (TypeError, ValueError):
                continue
            if not image_name or process_id <= 0:
                continue

            memory_kb = _parse_memory_kb(row[4]) if len(row) > 4 else None
            processes.append(
                {
                    "name": Path(image_name).name,
                    "pid": process_id,
                    "memory_kb": memory_kb,
                }
            )
            if len(processes) >= limit:
                break
    except (csv.Error, TypeError, ValueError):
        return processes
    return processes


def discover_installed_applications(*, max_items: int = 500) -> list[dict[str, Any]]:
    """Discover registered Start Menu/App Paths applications.

    Names are deduplicated and source labels are retained. Shortcut paths and
    packaged-app IDs are deliberately omitted from the returned inventory.
    """
    limit = _bounded_limit(max_items, 500, 2000)
    discovered: dict[str, set[str]] = {}

    def add(name: Any, source: str) -> None:
        normalized = _application_discovery.normalize_application_name(str(name or ""))
        if not normalized:
            return
        discovered.setdefault(normalized, set()).add(source)

    try:
        for display_name, _shortcut_path in _application_discovery.discover_application_shortcuts():
            add(display_name, "start_menu_shortcut")
    except Exception:
        pass

    try:
        for executable_name in _application_discovery.discover_application_registry_names():
            add(executable_name, "app_paths_registry")
    except Exception:
        pass

    try:
        for display_name, _application_id in _application_discovery.discover_start_menu_app_ids():
            add(display_name, "start_menu_app_id")
    except Exception:
        pass

    results = [
        {"name": name, "sources": sorted(sources)}
        for name, sources in sorted(discovered.items())
    ]
    return results[:limit]


def discover_running_processes(*, max_items: int = 250) -> list[dict[str, Any]]:
    """Return a bounded Windows process list using the fixed tasklist command.

    No shell is involved and no process command line, user name, or full
    executable path is collected.
    """
    if not _is_windows():
        return []

    limit = _bounded_limit(max_items, 250, 1000)
    try:
        completed = subprocess.run(
            ["tasklist.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []

    if completed.returncode != 0:
        return []
    return _parse_tasklist_csv(completed.stdout, max_items=limit)


def _load_windows_apis():
    if not _is_windows():
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    from ctypes import wintypes

    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.EnumWindows.argtypes = [
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
        wintypes.LPARAM,
    ]
    user32.EnumWindows.restype = wintypes.BOOL

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return user32, kernel32, wintypes


def _process_image_name(kernel32, wintypes, process_id: int) -> str:
    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(
        process_query_limited_information,
        False,
        int(process_id),
    )
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            return Path(buffer.value).name
        return ""
    finally:
        kernel32.CloseHandle(handle)


def discover_visible_windows(*, max_items: int = 200) -> list[dict[str, Any]]:
    """List visible titled top-level windows with process identity and HWND."""
    if not _is_windows():
        return []

    limit = _bounded_limit(max_items, 200, 1000)
    try:
        apis = _load_windows_apis()
        if apis is None:
            return []
        user32, kernel32, wintypes = apis
        foreground_handle = int(user32.GetForegroundWindow() or 0)
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )
        windows: list[dict[str, Any]] = []

        def visit(hwnd, _parameter):
            if not user32.IsWindowVisible(hwnd):
                return True

            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length <= 0:
                return True
            title_buffer = ctypes.create_unicode_buffer(min(title_length + 1, 8192))
            user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
            title = title_buffer.value.strip()
            if not title:
                return True

            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            handle_value = int(hwnd)
            windows.append(
                {
                    "handle": handle_value,
                    "process_id": int(process_id.value),
                    "process_name": _process_image_name(
                        kernel32, wintypes, process_id.value
                    ),
                    "title": title,
                    "is_foreground": handle_value == foreground_handle,
                }
            )
            return len(windows) < limit

        callback = callback_type(visit)
        user32.EnumWindows(callback, 0)
        return windows
    except Exception:
        # Desktop enumeration is best-effort. A locked process or inaccessible
        # window must not crash JARVIS or trigger an elevation request.
        return []


def get_foreground_window() -> dict[str, Any] | None:
    """Return the current foreground window from the visible-window inventory."""
    return next(
        (
            window
            for window in discover_visible_windows()
            if window.get("is_foreground")
        ),
        None,
    )


def _memory_bytes() -> tuple[int | None, int | None]:
    if not _is_windows():
        return None, None

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatusEx)]
        kernel32.GlobalMemoryStatusEx.restype = ctypes.c_int
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None, None
        return int(status.ullTotalPhys), int(status.ullAvailPhys)
    except Exception:
        return None, None


def get_system_information() -> dict[str, Any]:
    """Return non-identifying OS, CPU, Python, and memory details."""
    memory_total, memory_available = _memory_bytes()
    return {
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "unknown",
        "logical_cpu_count": os.cpu_count(),
        "memory_total_bytes": memory_total,
        "memory_available_bytes": memory_available,
        "python_version": platform.python_version(),
    }


def discover_drives() -> list[dict[str, Any]]:
    """List logical Windows drives and capacity without traversing their files."""
    if not _is_windows():
        return []

    drive_type_labels = {
        0: "unknown",
        1: "no_root_directory",
        2: "removable",
        3: "fixed",
        4: "network",
        5: "optical",
        6: "ramdisk",
    }
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        from ctypes import wintypes

        kernel32.GetLogicalDrives.restype = wintypes.DWORD
        kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetDriveTypeW.restype = wintypes.UINT
        mask = int(kernel32.GetLogicalDrives())
        drives: list[dict[str, Any]] = []
        for index in range(26):
            if not (mask & (1 << index)):
                continue
            root = f"{chr(65 + index)}:\\"
            drive_type = int(kernel32.GetDriveTypeW(root))
            record: dict[str, Any] = {
                "root": root,
                "type": drive_type_labels.get(drive_type, "unknown"),
                "accessible": False,
                "total_bytes": None,
                "used_bytes": None,
                "free_bytes": None,
            }
            try:
                usage = shutil.disk_usage(root)
                record.update(
                    {
                        "accessible": True,
                        "total_bytes": int(usage.total),
                        "used_bytes": int(usage.used),
                        "free_bytes": int(usage.free),
                    }
                )
            except OSError:
                pass
            drives.append(record)
        return drives
    except Exception:
        return []


_VALID_SCOPES = {"system", "applications", "processes", "windows", "drives"}


def discover_system_resources(
    scopes: Iterable[str] | None = None,
    *,
    max_processes: int = 250,
    max_windows: int = 200,
) -> dict[str, Any]:
    """Build an in-memory, bounded inventory for the requested resource scopes.

    The default collects system details, registered applications, running
    processes, visible windows, the foreground window, and logical drives.
    File and folder names are not crawled automatically; targeted discovery
    continues to use the existing filesystem search service.
    """
    if scopes is None:
        selected = set(_VALID_SCOPES)
    elif isinstance(scopes, str):
        selected = {scopes.strip().lower()}
    else:
        selected = {str(scope).strip().lower() for scope in scopes}

    invalid = selected - _VALID_SCOPES
    if invalid:
        raise ValueError(f"Unsupported resource scope(s): {', '.join(sorted(invalid))}")
    if not selected:
        raise ValueError("At least one resource scope must be requested.")

    inventory: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scopes": sorted(selected),
    }
    if "system" in selected:
        inventory["system"] = get_system_information()
    if "applications" in selected:
        inventory["installed_applications"] = discover_installed_applications()
    if "processes" in selected:
        inventory["running_processes"] = discover_running_processes(
            max_items=max_processes
        )
    if "windows" in selected:
        windows = discover_visible_windows(max_items=max_windows)
        inventory["visible_windows"] = windows
        inventory["foreground_window"] = next(
            (window for window in windows if window.get("is_foreground")),
            None,
        )
    if "drives" in selected:
        inventory["drives"] = discover_drives()
    return inventory
