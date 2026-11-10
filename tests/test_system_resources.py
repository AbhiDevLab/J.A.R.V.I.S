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
    # Isolate the newer path-verified App Paths collector; this test covers
    # the legacy name-only fallback below.
    monkeypatch.setattr(
        system_resources,
        "discover_application_path_executables",
        lambda: [],
    )
    monkeypatch.setattr(
        system_resources,
        "discover_uninstall_registry_applications",
        lambda: [],
    )
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
    by_name = {row["name"]: row for row in rows}
    assert by_name["chrome"]["category"] == "packaged_application"
    assert by_name["chrome"]["is_installed"] is True
    assert by_name["chrome"]["display_name"] == "Chrome"
    assert by_name["telegram"]["category"] == "shortcut_only"
    assert by_name["telegram"]["is_installed"] is None
    assert all("path" not in row and "app_id" not in row for row in rows)


def test_installed_app_discovery_is_resilient_when_windows_sources_fail(monkeypatch):
    monkeypatch.setattr(
        system_resources,
        "discover_uninstall_registry_applications",
        lambda: [],
    )
    def fail():
        raise OSError("registry unavailable")

    monkeypatch.setattr(
        system_resources,
        "discover_application_path_executables",
        fail,
    )

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
        system_resources,
        "discover_application_path_executables",
        lambda: [],
    )
    monkeypatch.setattr(
        system_resources,
        "discover_uninstall_registry_applications",
        lambda: [],
    )
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
        "ProductName": "Windows 10 Home Single Language",
        "EditionID": "CoreSingleLanguage",
        "InstallationType": "Client",
        "DisplayVersion": "26H2",
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
    assert metadata["EditionID"] == "CoreSingleLanguage"


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


def test_physical_core_record_parser_counts_cores_and_rejects_malformed_records():
    core_record = (0).to_bytes(4, "little") + (16).to_bytes(4, "little") + bytes(8)
    numa_record = (1).to_bytes(4, "little") + (16).to_bytes(4, "little") + bytes(8)
    raw = core_record + numa_record + core_record

    assert system_resources._count_processor_core_records(raw) == 2
    assert system_resources._count_processor_core_records(raw, len(raw) - 1) is None
    assert system_resources._count_processor_core_records(b"bad") is None


def test_get_system_information_uses_live_cpu_memory_and_edition_sources(monkeypatch):
    gib = 1024 ** 3
    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setattr(system_resources, "_memory_bytes", lambda: (int(15.7 * gib), int(2.0 * gib)))
    monkeypatch.setattr(system_resources, "_installed_memory_bytes", lambda: 16 * gib)
    monkeypatch.setattr(system_resources, "_physical_core_count", lambda: 10)
    monkeypatch.setattr(
        system_resources,
        "_read_cpu_registry_details",
        lambda: {
            "ProcessorNameString": "13th Gen Intel(R) Core(TM) i7-13620H",
            "Identifier": "Intel64 Family 6 Model 186",
            "VendorIdentifier": "GenuineIntel",
            "~MHz": 2400,
        },
    )
    monkeypatch.setattr(
        system_resources,
        "_windows_version_fields",
        lambda: {
            "operating_system": "Windows 11",
            "os_edition": "Home Single Language",
            "os_installation_type": "Client",
            "os_release": "26H2",
            "os_version": "10.0.26300.9711",
            "os_build": "26300",
            "os_update_revision": "9711",
        },
    )
    monkeypatch.setattr(system_resources.os, "cpu_count", lambda: 16)

    info = system_resources.get_system_information()

    assert info["processor"] == "13th Gen Intel(R) Core(TM) i7-13620H"
    assert info["physical_core_count"] == 10
    assert info["logical_cpu_count"] == 16
    assert info["processor_clock_mhz"] == 2400
    assert info["memory_installed_bytes"] == 16 * gib
    assert info["memory_total_bytes"] == int(15.7 * gib)
    assert info["memory_used_bytes"] == int(15.7 * gib) - int(2.0 * gib)
    assert info["memory_load_percent"] > 0
    assert info["os_edition"] == "Home Single Language"
    assert info["os_build"] == "26300"
    assert info["os_update_revision"] == "9711"


def test_uninstall_registry_discovery_separates_apps_from_windows_components(monkeypatch):
    import sys

    uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    entries = {
        "App-One": {
            "DisplayName": "Example Desktop App",
            "DisplayVersion": "3.2.1",
            "Publisher": "Example Publisher",
        },
        "Windows-Feature": {
            "DisplayName": "Example Windows Feature",
            "SystemComponent": 1,
            "Publisher": "Microsoft Corporation",
        },
        "Update-One": {
            "DisplayName": "Example Security Update",
            "ReleaseType": "Security Update",
            "Publisher": "Microsoft Corporation",
        },
    }

    class FakeKey:
        def __init__(self, name="root"):
            self.name = name
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()
        HKEY_CURRENT_USER = object()
        KEY_READ = 0x20019
        KEY_WOW64_64KEY = 0x0100
        KEY_WOW64_32KEY = 0x0200

        @staticmethod
        def OpenKey(root, path, reserved=0, access=0):
            if path == uninstall_key:
                return FakeKey("parent")
            if path in entries:
                return FakeKey(path)
            raise OSError("key not found")

        @staticmethod
        def EnumKey(parent, index):
            names = list(entries)
            if index >= len(names):
                raise OSError("no more entries")
            return names[index]

        @staticmethod
        def QueryValueEx(key, name):
            values = entries[key.name]
            if name not in values:
                raise OSError("value not found")
            return values[name], 1

    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg)

    rows = system_resources.discover_uninstall_registry_applications()
    indexed = {item["name"]: item for item in rows}

    assert indexed["example desktop app"]["category"] == "installed_application"
    assert indexed["example desktop app"]["publisher"] == "Example Publisher"
    assert indexed["example desktop app"]["version"] == "3.2.1"
    assert indexed["example windows feature"]["category"] == "windows_component"
    assert indexed["example security update"]["category"] == "windows_component"


def test_application_inventory_does_not_promote_shortcuts_to_installed_apps(monkeypatch):
    monkeypatch.setattr(
        system_resources,
        "discover_application_path_executables",
        lambda: [],
    )
    monkeypatch.setattr(
        system_resources,
        "discover_uninstall_registry_applications",
        lambda: [],
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_shortcuts",
        lambda: [("Portable Tool", r"C:\\Users\\Test\\Desktop\\Portable Tool.lnk")],
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_application_registry_names",
        lambda: {"portabletool"},
    )
    monkeypatch.setattr(
        system_resources._application_discovery,
        "discover_start_menu_app_ids",
        lambda: [("Packaged App", "Package.Test!App")],
    )

    rows = system_resources.discover_installed_applications()
    indexed = {item["name"]: item for item in rows}

    # A shortcut title and a registry executable token that differ in
    # spelling are kept separate until a verified alias connects them.
    assert indexed["portable tool"]["category"] == "shortcut_only"
    assert indexed["portable tool"]["is_installed"] is None
    assert indexed["portabletool"]["category"] == "registered_executable"
    assert indexed["portabletool"]["is_installed"] is None
    assert indexed["packaged app"]["category"] == "packaged_application"
    assert indexed["packaged app"]["is_installed"] is True


def test_installed_memory_reader_converts_win32_kilobytes_to_bytes(monkeypatch):
    class FakeFunction:
        argtypes = None
        restype = None
        def __call__(self, pointer):
            import ctypes
            ctypes.cast(
                pointer,
                ctypes.POINTER(ctypes.c_ulonglong),
            ).contents.value = 16 * 1024 * 1024
            return 1

    class FakeKernel32:
        GetPhysicallyInstalledSystemMemory = FakeFunction()

    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setattr(
        system_resources.ctypes,
        "WinDLL",
        lambda *args, **kwargs: FakeKernel32(),
        raising=False,
    )

    assert system_resources._installed_memory_bytes() == 16 * 1024 ** 3


def test_cpu_registry_reader_returns_runtime_processor_identity(monkeypatch):
    import sys

    values = {
        "ProcessorNameString": "13th Gen Intel(R) Core(TM) i7-13620H",
        "Identifier": "Intel64 Family 6 Model 186 Stepping 2",
        "VendorIdentifier": "GenuineIntel",
        "~MHz": 2400,
    }

    class FakeKey:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()
        KEY_READ = 0x20019

        @staticmethod
        def OpenKey(root, path, reserved, access):
            assert path == r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            return FakeKey()

        @staticmethod
        def QueryValueEx(key, name):
            if name not in values:
                raise OSError("missing")
            return values[name], 1

    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg)

    result = system_resources._read_cpu_registry_details()

    assert result["ProcessorNameString"] == values["ProcessorNameString"]
    assert result["VendorIdentifier"] == "GenuineIntel"
    assert result["~MHz"] == 2400


def test_windows_version_fields_preserve_runtime_edition_and_ubr(monkeypatch):
    monkeypatch.setattr(system_resources, "_read_windows_version_registry", lambda: {
        "ProductName": "Windows 10 Home Single Language",
        "EditionID": "CoreSingleLanguage",
        "InstallationType": "Client",
        "DisplayVersion": "26H2",
        "CurrentMajorVersionNumber": 10,
        "CurrentMinorVersionNumber": 0,
        "CurrentBuildNumber": "26300",
        "UBR": 9711,
    })

    fields = system_resources._windows_version_fields()

    assert fields["operating_system"] == "Windows 11"
    assert fields["os_edition"] == "Home Single Language"
    assert fields["os_release"] == "26H2"
    assert fields["os_version"] == "10.0.26300.9711"
    assert fields["os_build"] == "26300"
    assert fields["os_update_revision"] == "9711"


def test_drive_discovery_returns_runtime_volume_label_and_filesystem(monkeypatch):
    from types import SimpleNamespace

    class FakeFunction:
        def __init__(self, callback):
            self.callback = callback
            self.argtypes = None
            self.restype = None
        def __call__(self, *args):
            return self.callback(*args)

    class FakeKernel32:
        def __init__(self):
            self.GetLogicalDrives = FakeFunction(lambda: 1 << 2)
            self.GetDriveTypeW = FakeFunction(lambda root: 3)
            def volume_info(root, volume_label, volume_size, serial, max_component,
                            flags, filesystem, filesystem_size):
                volume_label.value = "Windows"
                filesystem.value = "NTFS"
                return 1
            self.GetVolumeInformationW = FakeFunction(volume_info)

    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setattr(
        system_resources.ctypes,
        "WinDLL",
        lambda *args, **kwargs: FakeKernel32(),
        raising=False,
    )
    monkeypatch.setattr(
        system_resources.shutil,
        "disk_usage",
        lambda root: SimpleNamespace(
            total=500 * 1024 ** 3,
            used=300 * 1024 ** 3,
            free=200 * 1024 ** 3,
        ),
    )

    drives = system_resources.discover_drives()

    assert drives == [
        {
            "root": "C:\\",
            "type": "fixed",
            "accessible": True,
            "volume_label": "Windows",
            "filesystem": "NTFS",
            "total_bytes": 500 * 1024 ** 3,
            "used_bytes": 300 * 1024 ** 3,
            "free_bytes": 200 * 1024 ** 3,
        }
    ]


def test_application_process_relationships_prefer_paths_and_join_windows_by_pid():
    applications = [
        {
            "name": "chrome",
            "display_name": "Google Chrome",
            "_executable_names": ["chrome.exe"],
            "_executable_paths": [r"c:\\program files\\google\\chrome\\application\\chrome.exe"],
            "_install_locations": [r"c:\\program files\\google\\chrome"],
        },
        {
            "name": "brave",
            "display_name": "Brave",
            "_executable_names": ["brave.exe"],
            "_executable_paths": [],
            "_install_locations": [],
        },
        {
            "name": "app alpha",
            "display_name": "App Alpha",
            "_executable_names": ["shared.exe"],
            "_executable_paths": [],
            "_install_locations": [],
        },
        {
            "name": "app beta",
            "display_name": "App Beta",
            "_executable_names": ["shared.exe"],
            "_executable_paths": [],
            "_install_locations": [],
        },
    ]
    processes = [
        {
            "name": "chrome.exe",
            "pid": 100,
            "memory_kb": 12000,
            "_image_path": r"c:\\program files\\google\\chrome\\application\\chrome.exe",
        },
        {
            "name": "brave.exe",
            "pid": 200,
            "memory_kb": 14000,
        },
        {
            "name": "shared.exe",
            "pid": 300,
            "memory_kb": 1000,
        },
        {
            "name": "svchost.exe",
            "pid": 400,
            "memory_kb": 2000,
        },
    ]
    windows = [
        {
            "process_id": 100,
            "title": "JARVIS - Brave",
            "is_foreground": True,
        },
        {
            "process_id": 100,
            "title": "Settings",
            "is_foreground": False,
        },
        {
            "process_id": 200,
            "title": "Brave",
            "is_foreground": False,
        },
    ]

    result = system_resources.build_application_process_relationships(
        applications,
        processes,
        windows,
    )
    rows = {row["pid"]: row for row in result["items"]}

    assert rows[100]["application"] == "Google Chrome"
    assert rows[100]["match_basis"] == "exact_executable_path"
    assert rows[100]["window_count"] == 2
    assert rows[100]["has_foreground_window"] is True
    assert rows[200]["application"] == "Brave"
    assert rows[200]["match_basis"] == "unique_executable_name"
    assert rows[300]["match_status"] == "ambiguous"
    assert "App Alpha" in rows[300]["application"]
    assert "App Beta" in rows[300]["application"]
    assert rows[400]["application"] == "Unmapped"
    assert result["matched_count"] == 2
    assert result["ambiguous_count"] == 1
    assert result["unmapped_count"] == 1


def test_application_process_relationship_query_filters_by_app_or_process():
    applications = [
        {
            "name": "chrome",
            "display_name": "Google Chrome",
            "_executable_names": ["chrome.exe"],
            "_executable_paths": [],
            "_install_locations": [],
        },
        {
            "name": "brave",
            "display_name": "Brave",
            "_executable_names": ["brave.exe"],
            "_executable_paths": [],
            "_install_locations": [],
        },
    ]
    processes = [
        {"name": "chrome.exe", "pid": 1},
        {"name": "brave.exe", "pid": 2},
    ]

    result = system_resources.build_application_process_relationships(
        applications,
        processes,
        [],
        query="chrome",
    )

    assert [item["pid"] for item in result["items"]] == [1]
    assert result["query"] == "chrome"
    assert result["matched_count"] == 1


def test_relationship_scope_collects_dependencies_internally_and_hides_paths(monkeypatch):
    calls = []
    monkeypatch.setattr(
        system_resources,
        "discover_installed_applications",
        lambda **kwargs: (
            calls.append(("applications", kwargs))
            or [{
                "name": "sample",
                "display_name": "Sample App",
                "_executable_names": ["sample.exe"],
                "_executable_paths": [r"c:\\apps\\sample.exe"],
                "_install_locations": [r"c:\\apps"],
            }]
        ),
    )
    monkeypatch.setattr(
        system_resources,
        "discover_running_processes",
        lambda **kwargs: (
            calls.append(("processes", kwargs))
            or [{
                "name": "sample.exe",
                "pid": 42,
                "_image_path": r"c:\\apps\\sample.exe",
            }]
        ),
    )
    monkeypatch.setattr(
        system_resources,
        "discover_visible_windows",
        lambda **kwargs: (
            calls.append(("windows", kwargs))
            or [{
                "process_id": 42,
                "title": "Sample App",
                "is_foreground": True,
            }]
        ),
    )

    inventory = system_resources.discover_system_resources(["relationships"])

    assert [name for name, _kwargs in calls] == [
        "applications",
        "processes",
        "windows",
    ]
    assert calls[0][1]["include_relationship_metadata"] is True
    assert calls[1][1]["include_image_paths"] is True
    assert "installed_applications" not in inventory
    assert "running_processes" not in inventory
    assert "visible_windows" not in inventory
    relation = inventory["application_process_relationships"]["items"][0]
    assert relation["application"] == "Sample App"
    assert relation["match_basis"] == "exact_executable_path"
    assert "c:\\apps" not in str(inventory).casefold()


def test_relationship_scope_is_not_added_to_normal_inventory_defaults():
    assert "relationships" not in system_resources._DEFAULT_SCOPES
    assert "relationships" in system_resources._VALID_SCOPES


def test_relationship_request_parser_recognizes_generic_and_app_specific_queries():
    assert system_resources.parse_system_resource_request(
        "show application process relationships"
    ) == {"scopes": ["relationships"]}
    assert system_resources.parse_system_resource_request(
        "which processes belong to Chrome"
    ) == {"scopes": ["relationships"], "query": "Chrome"}


def test_application_path_normalization_and_icon_extraction_are_conservative():
    assert system_resources._normalize_executable_path(
        r"C:\\Program Files\\Sample\\sample.exe"
    ) == system_resources._normalize_executable_path(
        r"c:\\program files\\sample\\sample.exe"
    )
    assert system_resources._extract_registered_executable_path(
        r'"C:\\Program Files\\Sample\\sample.exe",0'
    ) == r"C:\\Program Files\\Sample\\sample.exe"
    assert system_resources._extract_registered_executable_path(
        r"C:\\Program Files\\Sample\\sample.dll,0"
    ) is None


def test_application_path_registry_evidence_returns_existing_executable_only(monkeypatch, tmp_path):
    import sys

    executable = tmp_path / "sample.exe"
    executable.write_bytes(b"test executable")

    class FakeKey:
        def __init__(self, name):
            self.name = name
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()
        HKEY_CURRENT_USER = object()
        KEY_READ = 0x20019
        KEY_WOW64_64KEY = 0x0100
        KEY_WOW64_32KEY = 0x0200

        @staticmethod
        def OpenKey(root, path, reserved=0, access=0):
            if path == r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths":
                return FakeKey("parent")
            if path == "sample.exe":
                return FakeKey("sample.exe")
            raise OSError("missing key")

        @staticmethod
        def EnumKey(parent, index):
            if index == 0:
                return "sample.exe"
            raise OSError("no more entries")

        @staticmethod
        def QueryValueEx(key, name):
            if name is None:
                return str(executable), 1
            raise OSError("missing value")

    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg)

    entries = system_resources.discover_application_path_executables()

    assert len(entries) == 1
    assert entries[0]["name"] == "sample"
    assert entries[0]["executable_name"] == "sample.exe"
    assert entries[0]["path_verified"] is True
    assert entries[0]["executable_path"] == system_resources._normalize_executable_path(
        str(executable)
    )


def test_application_path_registry_ignores_non_executable_and_missing_targets(monkeypatch):
    import sys

    entries = {
        "library.dll": r"C:\Apps\library.dll",
        "missing.exe": r"C:\Apps\missing.exe",
    }

    class FakeKey:
        def __init__(self, name):
            self.name = name
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()
        HKEY_CURRENT_USER = object()
        KEY_READ = 0x20019

        @staticmethod
        def OpenKey(root, path, reserved=0, access=0):
            if path == r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths":
                return FakeKey("parent")
            if path in entries:
                return FakeKey(path)
            raise OSError("missing key")

        @staticmethod
        def EnumKey(parent, index):
            names = list(entries)
            if index >= len(names):
                raise OSError("no more entries")
            return names[index]

        @staticmethod
        def QueryValueEx(key, name):
            return entries[key.name], 1

    monkeypatch.setattr(system_resources, "_is_windows", lambda: True)
    monkeypatch.setattr(
        system_resources.Path,
        "is_file",
        lambda self: False,
    )
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg)

    rows = system_resources.discover_application_path_executables()

    assert rows == []
