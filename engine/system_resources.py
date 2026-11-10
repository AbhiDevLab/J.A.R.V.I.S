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
import time
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
        canonical = _application_discovery.ALIASES.get(normalized, normalized)
        discovered.setdefault(canonical, set()).add(source)

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


def _handle_to_int(handle: Any) -> int:
    """Convert ctypes pointer handles and callback integer handles safely."""
    value = getattr(handle, "value", handle)
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


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
        foreground_handle = _handle_to_int(user32.GetForegroundWindow())
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


def _read_windows_version_registry() -> dict[str, Any]:
    """Read Windows product/build metadata without relying on compatibility APIs."""
    if not _is_windows():
        return {}

    try:
        import winreg

        registry_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            registry_path,
            0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        ) as key:
            values: dict[str, Any] = {}
            for name in (
                "ProductName",
                "DisplayVersion",
                "ReleaseId",
                "CurrentBuildNumber",
                "CurrentMajorVersionNumber",
                "CurrentMinorVersionNumber",
                "UBR",
            ):
                try:
                    values[name] = winreg.QueryValueEx(key, name)[0]
                except OSError:
                    continue
            return values
    except (ImportError, OSError, AttributeError):
        return {}


def _windows_version_label(metadata: dict[str, Any]) -> str:
    """Resolve Windows 10/11 from the build, not platform.release().

    Python can report release '10' for Windows 11 when the process manifest
    does not declare Windows 11 compatibility. Windows 11 client builds start
    at 22000; server products retain their registry product name.
    """
    product_name = str(metadata.get("ProductName") or "").strip()
    try:
        build = int(str(metadata.get("CurrentBuildNumber") or "0"))
    except (TypeError, ValueError, OverflowError):
        build = 0

    if "server" in product_name.casefold():
        return product_name
    if build >= 22000:
        return "Windows 11"
    if build >= 10240:
        return "Windows 10"
    return product_name or f"Windows (build {build})" if build else "Windows"


def _windows_version_fields() -> dict[str, str]:
    """Return user-facing Windows release and exact build details."""
    metadata = _read_windows_version_registry()
    if not metadata:
        # platform.release() may report "10" for Windows 11 when an
        # application compatibility manifest is in effect. Prefer the actual
        # numeric build from platform.version(); do not treat "10" as proof
        # that the operating system is Windows 10.
        raw_version = platform.version()
        build_match = re.search(r"(?:^|\.)(\d{5,})(?:\.|$)", raw_version)
        try:
            build = int(build_match.group(1)) if build_match else 0
        except (TypeError, ValueError, OverflowError):
            build = 0
        if build >= 22000:
            label = "Windows 11"
        elif build >= 10240:
            label = "Windows 10"
        else:
            label = "Windows (version unavailable)"
        return {
            "operating_system": label,
            "os_release": f"Build {build}" if build else "Version metadata unavailable",
            "os_version": raw_version,
            "os_build": str(build) if build else "unknown",
        }

    label = _windows_version_label(metadata)
    display_version = str(
        metadata.get("DisplayVersion")
        or metadata.get("ReleaseId")
        or ""
    ).strip()
    try:
        major = int(metadata.get("CurrentMajorVersionNumber", 10))
        minor = int(metadata.get("CurrentMinorVersionNumber", 0))
        build = int(str(metadata.get("CurrentBuildNumber") or "0"))
    except (TypeError, ValueError, OverflowError):
        major, minor, build = 10, 0, 0
    try:
        update_build = int(metadata.get("UBR", 0))
    except (TypeError, ValueError, OverflowError):
        update_build = 0

    version = f"{major}.{minor}.{build}"
    if update_build:
        version += f".{update_build}"

    return {
        "operating_system": label,
        "os_release": display_version or f"Build {build}",
        "os_version": version,
        "os_build": str(build) if build else "unknown",
    }


def get_system_information() -> dict[str, Any]:
    """Return non-identifying OS, CPU, Python, and memory details."""
    memory_total, memory_available = _memory_bytes()
    os_fields = (
        _windows_version_fields()
        if _is_windows()
        else {
            "operating_system": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "os_build": "unknown",
        }
    )
    return {
        **os_fields,
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


_FILE_SEARCH_EXCLUDED_DIRECTORIES = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "recovery",
    "perflogs",
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


def discover_files_and_folders(
    query: str,
    *,
    max_results: int = 50,
    max_directories: int = 5000,
    max_seconds: float = 5.0,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """Search accessible drive roots by name without reading file contents.

    This is deliberately query-scoped rather than a background/full-drive
    indexer. Directory count, result count, and wall-clock time are bounded.
    Windows/system folders, reparse points, symlinks, and hidden entries are
    excluded by default. Results contain paths only in the returned in-memory
    response; nothing is persisted.
    """
    search_term = str(query or "").strip()
    if len(search_term) < 2 or chr(0) in search_term:
        raise ValueError("Provide at least two non-null characters to search for.")

    result_limit = _bounded_limit(max_results, 50, 200)
    directory_limit = _bounded_limit(max_directories, 5000, 20000)
    try:
        time_limit = max(0.25, min(20.0, float(max_seconds)))
    except (TypeError, ValueError, OverflowError):
        time_limit = 5.0

    roots = [
        Path(drive["root"])
        for drive in discover_drives()
        if isinstance(drive, dict) and drive.get("accessible") and drive.get("root")
    ]
    results: list[dict[str, Any]] = []
    visited_directories = 0
    stop_reason = ""
    started = time.monotonic()
    needle = search_term.casefold()

    for root in roots:
        if stop_reason:
            break
        if not root.is_dir():
            continue
        try:
            for current_root, dir_names, file_names in os.walk(
                root,
                topdown=True,
                followlinks=False,
            ):
                if time.monotonic() - started >= time_limit:
                    stop_reason = "time_limit"
                    break

                visited_directories += 1
                if visited_directories > directory_limit:
                    visited_directories -= 1
                    stop_reason = "directory_limit"
                    break

                current_path = Path(current_root)
                kept_directories = []
                for directory in sorted(dir_names, key=str.casefold):
                    if directory.casefold() in _FILE_SEARCH_EXCLUDED_DIRECTORIES:
                        continue
                    candidate = current_path / directory
                    try:
                        metadata = candidate.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    attributes = int(getattr(metadata, "st_file_attributes", 0) or 0)
                    if candidate.is_symlink() or attributes & 0x400:
                        continue
                    if not include_hidden and (
                        directory.startswith(".") or attributes & (0x2 | 0x4)
                    ):
                        continue
                    kept_directories.append(directory)
                    if needle in directory.casefold():
                        results.append(
                            {
                                "name": directory,
                                "path": str(candidate),
                                "kind": "folder",
                                "drive": root.anchor or str(root),
                            }
                        )
                        if len(results) >= result_limit:
                            stop_reason = "result_limit"
                            break

                dir_names[:] = kept_directories
                if stop_reason:
                    break

                for filename in sorted(file_names, key=str.casefold):
                    if time.monotonic() - started >= time_limit:
                        stop_reason = "time_limit"
                        break
                    candidate = current_path / filename
                    try:
                        metadata = candidate.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    attributes = int(getattr(metadata, "st_file_attributes", 0) or 0)
                    if candidate.is_symlink() or attributes & 0x400:
                        continue
                    if not include_hidden and (
                        filename.startswith(".") or attributes & (0x2 | 0x4)
                    ):
                        continue
                    if needle in filename.casefold():
                        results.append(
                            {
                                "name": filename,
                                "path": str(candidate),
                                "kind": "file",
                                "drive": root.anchor or str(root),
                            }
                        )
                        if len(results) >= result_limit:
                            stop_reason = "result_limit"
                            break
                if stop_reason:
                    break
        except OSError:
            # An inaccessible directory or removable/network volume is skipped.
            continue

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "query": search_term,
        "results": results,
        "result_count": len(results),
        "visited_directories": visited_directories,
        "elapsed_ms": elapsed_ms,
        "truncated": bool(stop_reason),
        "stop_reason": stop_reason or None,
        "drive_count": len(roots),
    }


_RESOURCE_REQUESTS = (
    (
        "all",
        re.compile(
            r"^(?:please )?(?:(?:show|display|get|give me|tell me|list)(?: me)? "
            r"(?:(?:all|full|my|this|the) )?)?(?:system|pc|computer) "
            r"(?:resources|inventory|overview|full inventory)$",
            re.IGNORECASE,
        ),
    ),
    (
        "system",
        re.compile(
            r"^(?:please )?(?:(?:show|display|get|give me|tell me|list)(?: me)? "
            r"(?:(?:my|this|the) )?)?(?:system|pc|computer) "
            r"(?:information|info|details)$",
            re.IGNORECASE,
        ),
    ),
    (
        "applications",
        re.compile(
            r"^(?:please )?(?:(?:list|show|display|find)(?: me)? "
            r"(?:all )?(?:installed )?(?:apps|applications|programs|software)|"
            r"(?:what|which) (?:apps|applications|programs|software) are installed)$",
            re.IGNORECASE,
        ),
    ),
    (
        "processes",
        re.compile(
            r"^(?:please )?(?:(?:show|list|display)(?: me)? "
            r"(?:all )?(?:running )?(?:processes|tasks)|"
            r"what (?:processes|tasks) are running)$",
            re.IGNORECASE,
        ),
    ),
    (
        "windows",
        re.compile(
            r"^(?:please )?(?:(?:show|list|display)(?: me)? "
            r"(?:the )?(?:active|open|visible) (?:windows|apps|applications)|"
            r"what (?:apps|applications|windows) are open)$",
            re.IGNORECASE,
        ),
    ),
    (
        "drives",
        re.compile(
            r"^(?:please )?(?:(?:show|list|display)(?: me)? "
            r"(?:(?:all|logical|available|my) )?drives|"
            r"what drives? (?:are available|do i have)|"
            r"show drives? on this (?:pc|computer))$",
            re.IGNORECASE,
        ),
    ),
)
_FILE_SEARCH_REQUESTS = (
    re.compile(
        r"^(?:please )?(?:find|search for|locate) "
        r"(?:(?:the|a|all) )?(?:files?|folders?|documents?)"
        r"(?: named| called| matching)? (?P<query>.+?) "
        r"(?:across|on|in) (?:all|every|accessible) drives?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please )?(?:search|scan) (?:all|every|accessible) drives? "
        r"for (?P<query>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please )?(?:find|search for|locate) (?P<query>.+?) "
        r"(?:across|on|in) (?:all|every|accessible) drives?$",
        re.IGNORECASE,
    ),
)


def parse_system_resource_request(text: str) -> dict[str, Any] | None:
    """Parse explicit, deterministic system-inventory requests.

    Full-drive filename search is recognized only when the user explicitly
    names all/every/accessible drives. Ordinary file requests keep their
    existing scoped filesystem routing.
    """
    value = " ".join(str(text or "").strip().rstrip(".!?").split())
    if not value:
        return None

    for scope, pattern in _RESOURCE_REQUESTS:
        if pattern.fullmatch(value):
            if scope == "all":
                return {"scopes": sorted(_DEFAULT_SCOPES)}
            return {"scopes": [scope]}

    for pattern in _FILE_SEARCH_REQUESTS:
        match = pattern.fullmatch(value)
        if match:
            search_query = str(match.group("query") or "").strip()
            if (
                len(search_query) >= 2
                and chr(0) not in search_query
                and not search_query.startswith(("\\", "/"))
            ):
                if (
                    len(search_query) >= 2
                    and search_query[0] == search_query[-1]
                    and search_query[0] in (chr(34), chr(39))
                ):
                    search_query = search_query[1:-1].strip()
                search_query = re.sub(
                    r"^(?:(?:a|the) )?(?:file|folder|document)(?: named| called| matching)? ",
                    "",
                    search_query,
                    flags=re.IGNORECASE,
                ).strip()
                if len(search_query) >= 2:
                    return {"scopes": ["files"], "query": search_query}

    return None


_VALID_SCOPES = {"system", "applications", "processes", "windows", "drives", "files"}
_DEFAULT_SCOPES = _VALID_SCOPES - {"files"}


def discover_system_resources(
    scopes: Iterable[str] | None = None,
    *,
    max_processes: int = 250,
    max_windows: int = 200,
    query: str | None = None,
    max_file_results: int = 50,
    max_file_directories: int = 5000,
    max_file_seconds: float = 5.0,
) -> dict[str, Any]:
    """Build an in-memory, bounded inventory for the requested resource scopes.

    The default collects system details, registered applications, running
    processes, visible windows, and logical drives. When the "files" scope is
    explicitly requested, a name-based search is performed across accessible
    drives with strict result, directory, and time limits. File contents are
    never opened or indexed.
    """
    if scopes is None:
        selected = set(_DEFAULT_SCOPES)
    elif isinstance(scopes, str):
        selected = {scopes.strip().lower()}
    else:
        selected = {str(scope).strip().lower() for scope in scopes}

    invalid = selected - _VALID_SCOPES
    if invalid:
        raise ValueError(f"Unsupported resource scope(s): {', '.join(sorted(invalid))}")
    if not selected:
        raise ValueError("At least one resource scope must be requested.")
    if "files" in selected and not str(query or "").strip():
        raise ValueError("The files scope requires a specific filename or folder-name query.")

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
    if "files" in selected:
        inventory["files_and_folders"] = discover_files_and_folders(
            query,
            max_results=max_file_results,
            max_directories=max_file_directories,
            max_seconds=max_file_seconds,
        )
    return inventory
