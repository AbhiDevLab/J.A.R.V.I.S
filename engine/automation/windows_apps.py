"""Windows desktop window control and accessibility text extraction.

Only visible top-level windows belonging to allowlisted applications are
considered. Closing uses WM_CLOSE (never TerminateProcess/taskkill /F), so
unsaved-document prompts remain under the application's control.
"""
from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass
from ctypes import wintypes
from typing import Any, Dict, List

from .applications import APPLICATIONS, canonical_application_name


@dataclass(frozen=True)
class DesktopWindow:
    handle: int
    process_id: int
    executable: str
    title: str


def _load_winapi():
    if os.name != "nt":
        raise OSError("Windows desktop access is available only on Windows.")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.SendMessageTimeoutW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    ]
    user32.SendMessageTimeoutW.restype = ctypes.c_size_t
    return user32, kernel32


def _process_executable(kernel32, process_id: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
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
            return os.path.basename(buffer.value).casefold()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _application_executables(application: str) -> set[str]:
    canonical = canonical_application_name(application)
    if not canonical:
        return set()
    names = set()
    for candidate in APPLICATIONS[canonical]:
        expanded = os.path.expandvars(candidate)
        names.add(os.path.basename(expanded).casefold())
    return {name for name in names if name}


def get_application_windows(application: str) -> List[DesktopWindow]:
    """Return visible top-level windows for one allowlisted app."""
    expected = _application_executables(application)
    if not expected:
        return []
    user32, kernel32 = _load_winapi()
    windows: List[DesktopWindow] = []

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        executable = _process_executable(kernel32, process_id.value)
        if executable not in expected:
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(max(1, length + 1))
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        windows.append(
            DesktopWindow(
                handle=int(hwnd),
                process_id=int(process_id.value),
                executable=executable,
                title=title_buffer.value.strip(),
            )
        )
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    callback = callback_type(visit)
    if not user32.EnumWindows(callback, 0):
        error = ctypes.get_last_error()
        if error:
            raise OSError(error, "EnumWindows failed")
    return windows


def close_application_window(application: str) -> Dict[str, Any]:
    """Request a graceful close of the foreground/unique app window."""
    canonical = canonical_application_name(application)
    if not canonical:
        return {"success": False, "message": "That application is not in the supported application list."}

    try:
        windows = get_application_windows(canonical)
    except Exception as exc:
        return {
            "success": False,
            "message": f"I could not inspect Windows application windows ({type(exc).__name__}).",
        }

    if not windows:
        return {
            "success": False,
            "message": f"{canonical.title()} does not have a visible open window.",
        }

    user32, _kernel32 = _load_winapi()
    foreground = int(user32.GetForegroundWindow() or 0)
    selected = next((item for item in windows if item.handle == foreground), None)

    if selected is None and len(windows) == 1:
        selected = windows[0]

    if selected is None:
        titles = [item.title for item in windows if item.title]
        detail = "; ".join(titles[:3]) or f"{len(windows)} windows"
        return {
            "success": False,
            "message": (
                f"I found multiple {canonical.title()} windows ({detail}). "
                "Bring the one you want closed to the foreground, then repeat the command."
            ),
            "ambiguous": True,
        }

    WM_CLOSE = 0x0010
    SMTO_ABORTIFHUNG = 0x0002
    result_value = ctypes.c_size_t()
    sent = user32.SendMessageTimeoutW(
        wintypes.HWND(selected.handle),
        WM_CLOSE,
        0,
        0,
        SMTO_ABORTIFHUNG,
        2500,
        ctypes.byref(result_value),
    )
    if not sent:
        return {
            "success": False,
            "message": (
                f"Windows did not confirm the close request for {canonical.title()}. "
                "The application may be busy or waiting for input."
            ),
        }

    # Give the UI a brief opportunity to process WM_CLOSE and display any
    # unsaved-changes prompt. Never force-terminate the process.
    time.sleep(0.2)
    if user32.IsWindow(wintypes.HWND(selected.handle)):
        return {
            "success": False,
            "message": (
                f"{canonical.title()} is still open. It may be displaying an "
                "unsaved-changes prompt; resolve that prompt before asking me to close it again."
            ),
            "save_prompt_or_window_still_open": True,
        }

    try:
        remaining = get_application_windows(canonical)
    except Exception:
        remaining = []

    if remaining:
        return {
            "success": True,
            "message": (
                f"I closed the active {canonical.title()} window. "
                f"{len(remaining)} other {canonical.title()} window(s) remain open."
            ),
            "still_open": True,
            "remaining_windows": len(remaining),
        }

    return {
        "success": True,
        "message": f"{canonical.title()} is now closed.",
        "still_open": False,
    }


def read_application_window_text(
    application: str,
    *,
    max_chars: int = 12000,
) -> Dict[str, Any]:
    """Read text exposed by UI Automation controls in an app's visible window."""
    canonical = canonical_application_name(application)
    if not canonical:
        return {"success": False, "message": "That application is not in the supported application list."}
    try:
        windows = get_application_windows(canonical)
    except Exception as exc:
        return {
            "success": False,
            "message": f"I could not inspect Windows application windows ({type(exc).__name__}).",
        }

    if not windows:
        return {
            "success": False,
            "message": (
                f"{canonical.title()} is not currently open in a visible window. "
                "I cannot retrieve the contents of a window that has already been closed."
            ),
        }

    user32, _kernel32 = _load_winapi()
    foreground = int(user32.GetForegroundWindow() or 0)
    selected = next((item for item in windows if item.handle == foreground), None)
    if selected is None and len(windows) == 1:
        selected = windows[0]
    if selected is None:
        titles = "; ".join(item.title for item in windows if item.title) or str(len(windows))
        return {
            "success": False,
            "message": (
                f"I found multiple {canonical.title()} windows ({titles}). "
                "Bring the document you want me to read to the foreground."
            ),
            "ambiguous": True,
        }

    try:
        from pywinauto import Desktop
    except Exception:
        return {
            "success": False,
            "message": (
                "Windows UI Automation support is not installed. Install the "
                "Windows-only pywinauto dependency and restart JARVIS."
            ),
        }

    try:
        window = Desktop(backend="uia").window(handle=selected.handle).wrapper_object()
        pieces = []
        seen = set()
        for control in window.descendants():
            try:
                control_type = str(control.element_info.control_type or "")
            except Exception:
                continue
            if control_type not in {"Edit", "Document", "TextBox"}:
                continue

            candidates = []
            for getter_name in ("get_value", "window_text"):
                getter = getattr(control, getter_name, None)
                if callable(getter):
                    try:
                        candidate = str(getter() or "").strip()
                    except Exception:
                        candidate = ""
                    if candidate:
                        candidates.append(candidate)

            try:
                text_pattern = control.iface_text
                candidate = str(text_pattern.DocumentRange.GetText(-1) or "").strip()
                if candidate:
                    candidates.append(candidate)
            except Exception:
                pass

            for candidate in candidates:
                candidate = candidate.replace("\x00", "").strip()
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    pieces.append(candidate)

        content = "\n\n".join(pieces).strip()
    except Exception as exc:
        return {
            "success": False,
            "message": (
                f"I found the {canonical.title()} window but could not read its "
                f"accessibility text ({type(exc).__name__})."
            ),
            "window_title": selected.title,
        }

    if not content:
        return {
            "success": False,
            "message": (
                f"I found the {canonical.title()} window, but it did not expose "
                "readable text controls through Windows UI Automation."
            ),
            "window_title": selected.title,
        }

    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars].rstrip() + "\n\n[Content truncated by JARVIS.]"

    return {
        "success": True,
        "content": content,
        "window_title": selected.title,
        "truncated": truncated,
        "message": f"Text currently visible in {canonical.title()}:\n\n{content}",
        "spoken_message": f"I read the text currently visible in {canonical.title()} and displayed it.",
        "summary": f"Read the current visible text from {canonical.title()}.",
    }


def type_text_into_application(
    application: str,
    text: str,
    *,
    wait_timeout: float = 8.0,
) -> Dict[str, Any]:
    """Focus an allowlisted application window and type into an editable UIA control.

    This fails closed: keystrokes are sent only after the named application's
    visible window and an enabled editable control inside it are verified.
    """
    canonical = canonical_application_name(application)
    value = str(text or "")
    if not canonical:
        return {
            "success": False,
            "message": "That application is not in the supported application list.",
        }
    if not value:
        return {"success": False, "message": "There is no text to type."}

    try:
        deadline = time.monotonic() + max(0.0, float(wait_timeout))
        windows = []
        while True:
            windows = get_application_windows(canonical)
            if windows or time.monotonic() >= deadline:
                break
            time.sleep(0.2)

        if not windows:
            return {
                "success": False,
                "message": (
                    f"I could not find an open {canonical.title()} window. "
                    "Open it first, then repeat the typing command."
                ),
            }

        user32, _kernel32 = _load_winapi()
        foreground = int(user32.GetForegroundWindow() or 0)
        selected = next(
            (item for item in windows if item.handle == foreground),
            None,
        )
        if selected is None and len(windows) == 1:
            selected = windows[0]
        if selected is None:
            titles = "; ".join(item.title for item in windows if item.title)
            return {
                "success": False,
                "ambiguous": True,
                "message": (
                    f"I found multiple {canonical.title()} windows"
                    + (f" ({titles})" if titles else "")
                    + ". Bring the intended window to the foreground and try again."
                ),
            }

        # Restore and activate only the verified allowlisted target window.
        if foreground != selected.handle:
            user32.ShowWindow(wintypes.HWND(selected.handle), 9)  # SW_RESTORE
            user32.SetForegroundWindow(wintypes.HWND(selected.handle))
            time.sleep(0.15)

        if int(user32.GetForegroundWindow() or 0) != selected.handle:
            return {
                "success": False,
                "message": (
                    f"Windows did not allow me to focus {canonical.title()}. "
                    "Bring that application to the foreground and repeat the command."
                ),
            }

        try:
            from pywinauto import Desktop
        except Exception:
            return {
                "success": False,
                "message": (
                    "Windows UI Automation support is unavailable. "
                    "Install the Windows-only pywinauto dependency and restart JARVIS."
                ),
            }

        window = (
            Desktop(backend="uia")
            .window(handle=selected.handle)
            .wrapper_object()
        )
        editable_controls = []
        for control in window.descendants():
            try:
                control_type = str(control.element_info.control_type or "")
                if control_type not in {"Edit", "Document", "TextBox"}:
                    continue
                if callable(getattr(control, "is_visible", None)) and not control.is_visible():
                    continue
                if callable(getattr(control, "is_enabled", None)) and not control.is_enabled():
                    continue
                editable_controls.append(control)
            except Exception:
                continue

        if not editable_controls:
            return {
                "success": False,
                "message": (
                    f"I found {canonical.title()}, but it does not expose an enabled "
                    "text-entry control. I did not send any keystrokes."
                ),
                "window_title": selected.title,
            }

        # Prefer an Edit control; some applications expose their editor as Document.
        editable_controls.sort(
            key=lambda control: (
                0 if str(control.element_info.control_type or "") == "Edit" else 1
            )
        )
        target = editable_controls[0]
        target.set_focus()

        # Verify focus again immediately before injecting any keyboard input.
        if int(user32.GetForegroundWindow() or 0) != selected.handle:
            return {
                "success": False,
                "message": (
                    f"Focus moved away from {canonical.title()}. "
                    "No text was typed; bring the intended window forward and retry."
                ),
            }

        # Escape pywinauto key-sequence braces to preserve ordinary user text literally.
        key_text = value.replace("{", "{{}").replace("}", "{}}")
        target.type_keys(
            key_text,
            with_spaces=True,
            with_tabs=True,
            with_newlines=True,
            pause=0.001,
            vk_packet=True,
        )
        return {
            "success": True,
            "message": f"Typed the requested text into {canonical.title()}.",
            "application": canonical,
            "window_title": selected.title,
            "characters_typed": len(value),
        }
    except Exception as exc:
        return {
            "success": False,
            "message": (
                f"I could not safely type into {canonical.title()} "
                f"({type(exc).__name__}). No automatic retry was attempted."
            ),
        }
