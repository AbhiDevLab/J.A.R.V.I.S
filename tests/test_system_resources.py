"""Regression tests for the read-only system resource inventory."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine import system_resources


def test_tasklist_csv_parser_returns_only_bounded_process_metadata():
    output = (
        '"chrome.exe","1234","Console","1","12,345 K"\r\n'
        '"notepad.exe","not-a-pid","Console","1","1,024 K"\r\n'
        '"System","4","Services","0","8,192 K"\r\n'
    )

    rows = system_resources._parse_tasklist_csv(output, max_items=2)

    assert rows == [
        {"name": "chrome.exe", "pid": 1234, "memory_kb": 12345},
        {"name": "System", "pid": 4, "memory_kb": 8192},
    ]
    assert all("command_line" not in row for row in rows)
    assert all("path" not in row for row in rows)


def test_tasklist_parser_handles_empty_malformed_and_unavailable_memory():
    rows = system_resources._parse_tasklist_csv(
        '\ufeff"app.exe","10","Console","1","N/A"\r\nmalformed\r\n'
    )
    assert rows == [{"name": "app.exe", "pid": 10, "memory_kb": None}]
    assert system_resources._parse_tasklist_csv("") == []


def test_installed_app_discovery_deduplicates_names_and_keeps_sources(monkeypatch):
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_shortcuts",
        lambda: [("Google Chrome", r"C:\\Start Menu\\Chrome.lnk"), ("Telegram", "ignored")],
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_registry_names",
        lambda: {"chrome", "code"},
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_start_menu_app_ids",
        lambda: [("Chrome", "Package.Chrome!App"), ("Android Studio", "Package.Studio!App")],
    )

    rows = system_resources.discover_installed_applications()
    indexed = {row["name"]: row["sources"] for row in rows}

    assert indexed["chrome"] == [
        "app_paths_registry",
        "start_menu_app_id",
        "start_menu_shortcut",
    ]
    assert indexed["telegram"] == ["start_menu_shortcut"]
    assert indexed["android studio"] == ["start_menu_app_id"]
    assert all("path" not in row and "app_id" not in row for row in rows)


def test_installed_app_discovery_is_resilient_when_windows_sources_fail(monkeypatch):
    def fail():
        raise OSError("registry unavailable")

    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_shortcuts",
        fail,
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_registry_names",
        fail,
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_start_menu_app_ids",
        fail,
    )
    assert system_resources.discover_installed_applications() == []


def test_installed_app_discovery_respects_result_limit(monkeypatch):
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_shortcuts",
        lambda: [(f"App {index}", f"shortcut-{index}") for index in range(10)],
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_registry_names",
        lambda: set(),
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_start_menu_app_ids",
        lambda: [],
    )
    assert len(system_resources.discover_installed_applications(max_items=3)) == 3


def test_running_process_discovery_is_empty_off_windows(monkeypatch):
    monkeypatch.setattr(system_resources, "_is_windows", lambda: False)
    monkeypatch.setattr(
        system_resources.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tasklist must not run")),
    )
    assert system_resources.discover_running_processes() == []


def test_running_process_discovery_uses_fixed_non_shell_tasklist_command(monkeypatch):
    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout='"notepad.exe","42","Console","1","4,096 K"\r\n',
        )

    monkeypatch.setattr(system_resources.subprocess, "run", fake_run)
    rows = system_resources.discover_running_processes(max_items=20)

    assert rows == [{"name": "notepad.exe", "pid": 42, "memory_kb": 4096}]
    command, kwargs = calls[0]
    assert command == ["tasklist.exe", "/FO", "CSV", "/NH"]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 10
    assert kwargs["check"] is False


def test_running_process_discovery_handles_command_failure(monkeypatch):
    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setattr(
        system_resources.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    assert system_resources.discover_running_processes() == []


def test_visible_window_and_drive_discovery_are_safe_off_windows(monkeypatch):
    monkeypatch.setattr(system_resources, "_is_windows", lambda: False)
    assert system_resources.discover_visible_windows() == []
    assert system_resources.discover_drives() == []
    assert system_resources.get_foreground_window() is None


def test_foreground_window_comes_only_from_visible_window_inventory(monkeypatch):
    windows = [
        {"handle": 10, "title": "Background", "is_foreground": False},
        {"handle": 20, "title": "Active", "is_foreground": True},
    ]
    monkeypatch.setattr(
        system_resources,
        "discover_visible_windows",
        lambda **kwargs: windows,
    )
    assert system_resources.get_foreground_window() == windows[1]


def test_system_information_uses_non_identifying_fields(monkeypatch):
    monkeypatch.setattr(system_resources, "_memory_bytes", lambda: (16, 8))
    info = system_resources.get_system_information()

    assert info["memory_total_bytes"] == 16
    assert info["memory_available_bytes"] == 8
    assert info["logical_cpu_count"] is not None
    assert "username" not in info
    assert "hostname" not in info
    assert "serial_number" not in info


def test_system_resource_inventory_collects_only_requested_scopes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        system_resources,
        "get_system_information",
        lambda: calls.append("system") or {"operating_system": "Windows"},
    )
    monkeypatch.setattr(
        system_resources,
        "discover_installed_applications",
        lambda: calls.append("applications") or [{"name": "notepad"}],
    )
    monkeypatch.setattr(
        system_resources,
        "discover_running_processes",
        lambda **kwargs: calls.append("processes") or [{"name": "notepad.exe", "pid": 4}],
    )
    monkeypatch.setattr(
        system_resources,
        "discover_visible_windows",
        lambda **kwargs: calls.append("windows") or [
            {"title": "Untitled - Notepad", "is_foreground": True}
        ],
    )
    monkeypatch.setattr(
        system_resources,
        "discover_drives",
        lambda: calls.append("drives") or [{"root": "C:\\"}],
    )

    inventory = system_resources.discover_system_resources(
        ["system", "windows"],
        max_windows=12,
    )

    assert calls == ["system", "windows"]
    assert inventory["scopes"] == ["system", "windows"]
    assert inventory["system"]["operating_system"] == "Windows"
    assert inventory["foreground_window"]["title"] == "Untitled - Notepad"
    assert "installed_applications" not in inventory
    assert "running_processes" not in inventory
    assert "drives" not in inventory
    assert inventory["schema_version"] == 1
    assert inventory["generated_at_utc"].endswith("+00:00")


def test_system_resource_inventory_defaults_to_all_documented_scopes(monkeypatch):
    monkeypatch.setattr(system_resources, "get_system_information", lambda: {})
    monkeypatch.setattr(system_resources, "discover_installed_applications", lambda: [])
    monkeypatch.setattr(system_resources, "discover_running_processes", lambda **kwargs: [])
    monkeypatch.setattr(system_resources, "discover_visible_windows", lambda **kwargs: [])
    monkeypatch.setattr(system_resources, "discover_drives", lambda: [])

    inventory = system_resources.discover_system_resources()

    assert inventory["scopes"] == [
        "applications",
        "drives",
        "processes",
        "system",
        "windows",
    ]
    assert inventory["installed_applications"] == []
    assert inventory["running_processes"] == []
    assert inventory["visible_windows"] == []
    assert inventory["foreground_window"] is None
    assert inventory["drives"] == []


@pytest.mark.parametrize(
    "scopes",
    [
        ["unknown"],
        [],
        ["system", "private_files"],
    ],
)
def test_system_resource_inventory_rejects_unknown_or_empty_scopes(scopes):
    with pytest.raises(ValueError):
        system_resources.discover_system_resources(scopes)


def test_drive_name_search_finds_files_and_folders_without_opening_contents(monkeypatch, tmp_path):
    project = tmp_path / "Project Reports"
    project.mkdir()
    (project / "final-report.pdf").write_text("private document body", encoding="utf-8")
    hidden = tmp_path / ".private"
    hidden.mkdir()
    (hidden / "report-secret.txt").write_text("hidden", encoding="utf-8")
    system = tmp_path / "Windows"
    system.mkdir()
    (system / "report-system.ini").write_text("system", encoding="utf-8")

    monkeypatch.setattr(
        system_resources,
        "discover_drives",
        lambda: [{"root": str(tmp_path), "accessible": True}],
    )

    result = system_resources.discover_files_and_folders(
        "report",
        max_results=20,
        max_directories=100,
        max_seconds=2,
    )

    matches = {(item["name"], item["kind"]) for item in result["results"]}
    assert ("Project Reports", "folder") in matches
    assert ("final-report.pdf", "file") in matches
    assert all("private" not in item["path"].casefold() for item in result["results"])
    assert all("windows" not in item["path"].casefold() for item in result["results"])
    assert "private document body" not in repr(result)
    assert result["drive_count"] == 1
    assert result["visited_directories"] >= 2


def test_drive_name_search_requires_a_specific_nontrivial_query():
    with pytest.raises(ValueError):
        system_resources.discover_files_and_folders("")
    with pytest.raises(ValueError):
        system_resources.discover_files_and_folders("x")


def test_drive_name_search_respects_result_and_directory_limits(monkeypatch, tmp_path):
    for index in range(5):
        folder = tmp_path / f"Report Folder {index}"
        folder.mkdir()
        (folder / f"report-{index}.txt").write_text("data", encoding="utf-8")

    monkeypatch.setattr(
        system_resources,
        "discover_drives",
        lambda: [{"root": str(tmp_path), "accessible": True}],
    )

    result = system_resources.discover_files_and_folders(
        "report",
        max_results=1,
        max_directories=100,
        max_seconds=2,
    )
    assert result["result_count"] == 1
    assert result["truncated"] is True
    assert result["stop_reason"] == "result_limit"

    limited = system_resources.discover_files_and_folders(
        "report",
        max_results=20,
        max_directories=1,
        max_seconds=2,
    )
    assert limited["visited_directories"] == 1
    assert limited["truncated"] is True
    assert limited["stop_reason"] == "directory_limit"


def test_system_resource_files_scope_is_explicit_and_query_scoped(monkeypatch):
    with pytest.raises(ValueError, match="requires a specific"):
        system_resources.discover_system_resources(["files"])

    monkeypatch.setattr(
        system_resources,
        "discover_files_and_folders",
        lambda query, **kwargs: {"query": query, "results": []},
    )
    inventory = system_resources.discover_system_resources(
        ["files"],
        query="project report",
    )
    assert inventory["files_and_folders"] == {
        "query": "project report",
        "results": [],
    }
    assert inventory["scopes"] == ["files"]


def test_default_resource_scopes_do_not_trigger_a_drive_wide_name_search(monkeypatch):
    monkeypatch.setattr(system_resources, "get_system_information", lambda: {})
    monkeypatch.setattr(system_resources, "discover_installed_applications", lambda: [])
    monkeypatch.setattr(system_resources, "discover_running_processes", lambda **kwargs: [])
    monkeypatch.setattr(system_resources, "discover_visible_windows", lambda **kwargs: [])
    monkeypatch.setattr(system_resources, "discover_drives", lambda: [])
    monkeypatch.setattr(
        system_resources,
        "discover_files_and_folders",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("drive name search must be explicitly requested")
        ),
    )

    inventory = system_resources.discover_system_resources()
    assert "files" not in inventory["scopes"]
    assert "files_and_folders" not in inventory


@pytest.mark.parametrize(
    "utterance, expected",
    [
        ("Show system info", {"scopes": ["system"]}),
        (
            "show system resources",
            {"scopes": ["applications", "drives", "processes", "system", "windows"]},
        ),
        (
            "show system inventory",
            {"scopes": ["applications", "drives", "processes", "system", "windows"]},
        ),
        (
            "show full system inventory",
            {"scopes": ["applications", "drives", "processes", "system", "windows"]},
        ),
        ("list installed applications", {"scopes": ["applications"]}),
        ("what applications are installed", {"scopes": ["applications"]}),
        ("show running processes", {"scopes": ["processes"]}),
        ("what apps are open", {"scopes": ["windows"]}),
        ("list logical drives", {"scopes": ["drives"]}),
        (
            "find a file named report.csv across all drives",
            {"scopes": ["files"], "query": "report.csv"},
        ),
        (
            "search all drives for JARVIS",
            {"scopes": ["files"], "query": "JARVIS"},
        ),
        (
            "search every drive for JARVIS",
            {"scopes": ["files"], "query": "JARVIS"},
        ),
        (
            "search all drives for a file named report.csv",
            {"scopes": ["files"], "query": "report.csv"},
        ),
        (
            "find all files named report.csv across every drive",
            {"scopes": ["files"], "query": "report.csv"},
        ),
        (
            "find \"project report\" across all drives",
            {"scopes": ["files"], "query": "project report"},
        ),
    ],
)
def test_system_resource_request_parser_recognizes_explicit_requests(utterance, expected):
    assert system_resources.parse_system_resource_request(utterance) == expected


@pytest.mark.parametrize(
    "utterance",
    [
        "open Notepad",
        "find a file named report",
        "search my Downloads folder for report",
        "show me everything",
        "show all files",
    ],
)
def test_system_resource_request_parser_does_not_capture_existing_commands(utterance):
    assert system_resources.parse_system_resource_request(utterance) is None


@pytest.mark.parametrize(
    "handle, expected",
    [
        (system_resources.ctypes.c_void_p(1234), 1234),
        (1234, 1234),
        (system_resources.ctypes.c_void_p(None), 0),
        (None, 0),
    ],
)
def test_win32_handle_conversion_accepts_ctypes_and_callback_values(handle, expected):
    assert system_resources._handle_to_int(handle) == expected


@pytest.mark.parametrize(
    "metadata, expected",
    [
        (
            {"ProductName": "Windows 10 Pro", "CurrentBuildNumber": "26100"},
            "Windows 11",
        ),
        (
            {"ProductName": "Windows 10 Pro", "CurrentBuildNumber": "19045"},
            "Windows 10",
        ),
        (
            {"ProductName": "Windows Server 2025", "CurrentBuildNumber": "26100"},
            "Windows Server 2025",
        ),
        (
            {"ProductName": "Windows 11 Pro", "CurrentBuildNumber": "22631"},
            "Windows 11",
        ),
    ],
)
def test_windows_version_label_uses_build_and_preserves_server_product(metadata, expected):
    assert system_resources._windows_version_label(metadata) == expected


def test_windows_version_fallback_uses_build_not_platform_release(monkeypatch):
    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setattr(system_resources, "_read_windows_version_registry", lambda: {})
    monkeypatch.setattr(system_resources.platform, "release", lambda: "10")
    monkeypatch.setattr(
        system_resources.platform,
        "version",
        lambda: "10.0.26100.3476",
    )

    fields = system_resources._windows_version_fields()

    assert fields["operating_system"] == "Windows 11"
    assert fields["os_build"] == "26100"
    assert fields["os_release"] == "Build 26100"


def test_windows_registry_reader_uses_the_current_version_key(monkeypatch):
    import sys

    captured = {}
    registry_values = {
        "ProductName": "Windows 10 Pro",
        "DisplayVersion": "24H2",
        "CurrentBuildNumber": "26100",
        "CurrentMajorVersionNumber": 10,
        "CurrentMinorVersionNumber": 0,
        "UBR": 3476,
    }

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()
        KEY_READ = 0x20019
        KEY_WOW64_64KEY = 0x0100

        @staticmethod
        def OpenKey(root, sub_key, reserved, access):
            captured["root"] = root
            captured["path"] = sub_key
            captured["reserved"] = reserved
            captured["access"] = access
            return FakeKey()

        @staticmethod
        def QueryValueEx(key, name):
            if name not in registry_values:
                raise OSError("missing value")
            return registry_values[name], 1

    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg)

    metadata = system_resources._read_windows_version_registry()

    assert captured["path"] == r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    assert captured["reserved"] == 0
    assert captured["access"] == FakeWinreg.KEY_READ | FakeWinreg.KEY_WOW64_64KEY
    assert metadata["CurrentBuildNumber"] == "26100"


def test_windows_system_information_uses_detected_version_fields(monkeypatch):
    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setattr(system_resources, "_memory_bytes", lambda: (32, 16))
    monkeypatch.setattr(
        system_resources,
        "_windows_version_fields",
        lambda: {
            "operating_system": "Windows 11",
            "os_release": "24H2",
            "os_version": "10.0.26100.3476",
            "os_build": "26100",
        },
    )

    info = system_resources.get_system_information()

    assert info["operating_system"] == "Windows 11"
    assert info["os_release"] == "24H2"
    assert info["os_build"] == "26100"
