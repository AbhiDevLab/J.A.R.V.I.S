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
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
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





def _focus_application_editor(window):
    """Focus a usable text surface without trusting flaky UIA state flags.

    The read helper intentionally discovers Edit/Document/TextBox descendants
    without consulting is_visible()/is_enabled(). Some Notepad UIA providers
    report those flags inconsistently even though the document can be read and
    focused. Here, focus itself is the usability test: try the known text
    control types and accept only a control that successfully takes focus.
    """
    controls = []
    for control in window.descendants():
        try:
            control_type = str(control.element_info.control_type or "")
        except Exception:
            continue
        if control_type not in {"Edit", "Document", "TextBox"}:
            continue
        controls.append(control)

    priority = {"Edit": 0, "Document": 1, "TextBox": 2}
    controls.sort(
        key=lambda control: priority.get(
            str(getattr(control.element_info, "control_type", "") or ""),
            3,
        )
    )

    for control in controls:
        try:
            control.set_focus()
            has_keyboard_focus = getattr(control, "has_keyboard_focus", None)
            if callable(has_keyboard_focus) and not has_keyboard_focus():
                continue
            return control
        except Exception:
            # A stale/disabled descendant must not prevent trying the next
            # editable text surface in the same verified application window.
            continue
    return None


def _focus_notepad_document(window):
    """Return the active Notepad document control, never a generic Edit/TextBox.

    Modern tabbed Notepad can expose other editable controls (for example,
    search or tab UI). Only a UIA Document control is eligible for document
    shortcuts and text entry. If several document controls exist, one must
    already own keyboard focus; otherwise selection is ambiguous and we fail
    closed rather than guessing which tab to target.
    """
    documents = []
    for control in window.descendants():
        try:
            if str(control.element_info.control_type or "") == "Document":
                documents.append(control)
        except Exception:
            continue

    if not documents:
        return None

    focused = []
    for control in documents:
        checker = getattr(control, "has_keyboard_focus", None)
        if callable(checker):
            try:
                if checker():
                    focused.append(control)
            except Exception:
                continue

    if len(focused) == 1:
        return focused[0]
    if len(documents) > 1:
        return None

    # A single Document control is unambiguous. Focus it and verify that the
    # UIA provider reports keyboard focus before sending any shortcut/keys.
    target = documents[0]
    try:
        checker = getattr(target, "has_keyboard_focus", None)
        if not callable(checker):
            return None
        target.set_focus()
        if not checker():
            return None
        return target
    except Exception:
        return None


def _read_editor_control_text(control) -> tuple[bool, str]:
    """Read the focused editor control, distinguishing blank from unreadable."""
    candidates = []
    readable = False

    for getter_name in ("get_value", "window_text"):
        getter = getattr(control, getter_name, None)
        if not callable(getter):
            continue
        try:
            value = getter()
            if value is not None:
                readable = True
                candidates.append(str(value).replace("\x00", ""))
        except Exception:
            continue

    try:
        text_pattern = control.iface_text
        value = text_pattern.DocumentRange.GetText(-1)
        if value is not None:
            readable = True
            candidates.append(str(value).replace("\x00", ""))
    except Exception:
        pass

    return readable, max(candidates, key=len, default="").strip()


def create_new_notepad_document(
    application: str,
    *,
    wait_timeout: float = 5.0,
) -> Dict[str, Any]:
    """Ensure a blank Notepad document is active before a compound type command.

    Existing content is never cleared or overwritten. If the active document
    is non-empty, send Notepad's New-tab shortcut and verify that a readable,
    blank editor becomes active before allowing the caller to type.
    """
    canonical = canonical_application_name(application)
    if canonical != "notepad":
        return {
            "success": False,
            "message": "Fresh-document creation is currently supported for Notepad only.",
        }

    try:
        deadline = time.monotonic() + max(0.0, float(wait_timeout))
        windows = []
        while True:
            windows = get_application_windows(canonical)
            if windows or time.monotonic() >= deadline:
                break
            time.sleep(0.15)

        if not windows:
            return {
                "success": False,
                "message": "I could not find a visible Notepad window to prepare a new document.",
            }

        user32, _kernel32 = _load_winapi()
        foreground = int(user32.GetForegroundWindow() or 0)
        selected = next((item for item in windows if item.handle == foreground), None)
        if selected is None and len(windows) == 1:
            selected = windows[0]
        if selected is None:
            titles = "; ".join(item.title for item in windows if item.title)
            return {
                "success": False,
                "ambiguous": True,
                "message": (
                    "I found multiple Notepad windows"
                    + (f" ({titles})" if titles else "")
                    + ". Bring the intended window to the foreground and retry."
                ),
            }

        if foreground != selected.handle:
            user32.ShowWindow(wintypes.HWND(selected.handle), 9)  # SW_RESTORE
            user32.SetForegroundWindow(wintypes.HWND(selected.handle))
            time.sleep(0.15)

        if int(user32.GetForegroundWindow() or 0) != selected.handle:
            return {
                "success": False,
                "message": "Windows did not let me focus the selected Notepad window.",
            }

        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
        window = desktop.window(handle=selected.handle).wrapper_object()
        editor = _focus_notepad_document(window)
        if editor is None:
            return {
                "success": False,
                "message": "I could not identify a focusable Notepad document. No content was changed.",
            }

        readable, current_text = _read_editor_control_text(editor)
        if not readable:
            return {
                "success": False,
                "message": "I could not verify the active Notepad document contents. I left it untouched.",
            }

        if not current_text.strip():
            return {
                "success": True,
                "message": "A blank Notepad document is already active.",
                "new_document_created": False,
                "document_is_blank": True,
            }

        # Existing content is non-empty. Create a new tab; never clear,
        # select-all, replace, or otherwise modify the active document.
        if int(user32.GetForegroundWindow() or 0) != selected.handle:
            return {
                "success": False,
                "message": "Notepad lost foreground focus. I did not create or type into a document.",
            }
        try:
            editor.type_keys("^n", pause=0.05)
        except Exception as exc:
            return {
                "success": False,
                "message": (
                    f"Notepad did not accept the new-document shortcut ({type(exc).__name__}). "
                    "Existing content was left untouched."
                ),
            }

        verify_deadline = time.monotonic() + max(2.0, float(wait_timeout))
        last_error = ""
        while time.monotonic() < verify_deadline:
            try:
                current_windows = get_application_windows(canonical)
                current_foreground = int(user32.GetForegroundWindow() or 0)
                active = next(
                    (item for item in current_windows if item.handle == current_foreground),
                    None,
                )
                if active is None and len(current_windows) == 1:
                    active = current_windows[0]

                if active is not None and current_foreground == active.handle:
                    active_window = desktop.window(handle=active.handle).wrapper_object()
                    active_editor = _focus_notepad_document(active_window)
                    if active_editor is not None:
                        blank_is_readable, new_text = _read_editor_control_text(active_editor)
                        if blank_is_readable and not new_text.strip():
                            return {
                                "success": True,
                                "message": "Created and verified a new blank Notepad document.",
                                "new_document_created": True,
                                "document_is_blank": True,
                                "window_title": active.title,
                            }
            except Exception as exc:
                last_error = type(exc).__name__
            time.sleep(0.15)

        detail = f" ({last_error})" if last_error else ""
        return {
            "success": False,
            "message": (
                "I sent Notepad's new-document shortcut, but could not verify a blank "
                f"document became active{detail}. I did not type anything; check Notepad before retrying."
            ),
            "new_document_created": None,
            "document_is_blank": False,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": (
                f"I could not safely prepare a new Notepad document ({type(exc).__name__}). "
                "Existing content was left untouched."
            ),
        }


def _normalise_visible_text(value: str) -> str:
    """Normalise whitespace for conservative post-entry verification."""
    return " ".join(str(value or "").split())


def _text_entry_verified(before: str, after: str, requested: str) -> bool:
    """Return true only when the requested text is newly visible after entry."""
    expected = _normalise_visible_text(requested)
    before_text = _normalise_visible_text(before)
    after_text = _normalise_visible_text(after)
    if not expected or expected not in after_text:
        return False
    return after_text.count(expected) > before_text.count(expected)


def type_text_into_application(
    application: str,
    text: str,
    *,
    wait_timeout: float = 8.0,
) -> Dict[str, Any]:
    """Focus an allowlisted application window and type into an editable UIA control.

    This fails closed: keystrokes are sent only after the named application's
    visible window and a focusable editable control inside it are verified.
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
        target = (
            _focus_notepad_document(window)
            if canonical == "notepad"
            else _focus_application_editor(window)
        )
        if target is None:
            return {
                "success": False,
                "message": (
                    f"I found {canonical.title()}, but could not focus an editable "
                    "document control. No keystrokes were sent."
                ),
                "window_title": selected.title,
            }

        # Verify focus again immediately before injecting any keyboard input.
        if int(user32.GetForegroundWindow() or 0) != selected.handle:
            return {
                "success": False,
                "message": (
                    f"Focus moved away from {canonical.title()}. "
                    "No text was typed; bring the intended window forward and retry."
                ),
            }

        baseline_result = read_application_window_text(canonical)
        baseline_text = (
            str(baseline_result.get("content") or "")
            if baseline_result.get("success")
            else ""
        )

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

        # Verify once by reading the named app window. Never repeat the typing
        # call automatically: uncertain input must not create duplicate text.
        time.sleep(0.15)
        verification = read_application_window_text(canonical)
        visible_text = (
            str(verification.get("content") or "")
            if verification.get("success")
            else ""
        )
        if not _text_entry_verified(baseline_text, visible_text, value):
            return {
                "success": False,
                "message": (
                    f"Text entry was sent to {canonical.title()}, but I could not "
                    "verify that the requested text appeared in the document. "
                    "Please inspect the window before retrying; I did not resend it."
                ),
                "application": canonical,
                "window_title": selected.title,
                "typing_sent": True,
                "typing_verified": False,
                "characters_typed": len(value),
            }

        return {
            "success": True,
            "message": f"Typed and verified the requested text in {canonical.title()}.",
            "application": canonical,
            "window_title": selected.title,
            "typing_verified": True,
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
