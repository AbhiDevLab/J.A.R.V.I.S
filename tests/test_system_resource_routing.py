"""End-to-end routing and policy tests for system resource discovery."""
from __future__ import annotations

from engine.automation.actions import AutomationAction, RiskLevel
from engine.automation.executor import execute_action
from engine.automation.policy import ActionTier, classify_action
from engine.automation.router import route_command
from engine.context_interpreter import should_interpret_query
from engine.intent_classifier import SemanticIntent, classify_intent


def test_resource_inventory_queries_use_deterministic_voice_fast_path(monkeypatch):
    monkeypatch.setenv("JARVIS_INTERPRETATION_MODE", "auto")

    for query in (
        "show system info",
        "show system resources",
        "list installed applications",
        "show running processes",
        "what apps are open",
        "list logical drives",
        "find a file named report across all drives",
    ):
        assert should_interpret_query(query, is_voice_input=True) is False

    # A pending confirmation/clarification always retains priority.
    assert should_interpret_query(
        "show running processes",
        interaction_state="Pending confirmation: close Notepad",
        is_voice_input=True,
    ) is True


def test_resource_inventory_queries_classify_as_automation_without_llm():
    query = "show running processes"
    result = classify_intent(
        query,
        raw_text=query,
        interpretation=None,
        voice_input=True,
    )

    assert result.intent is SemanticIntent.AUTOMATION
    assert result.normalized_query == query
    assert result.source == "system_resource_discovery"
    assert result.should_route_automation is True


def test_resource_inventory_requests_route_to_typed_read_only_actions():
    cases = {
        "show system info": (["system"], None),
        "show system resources": (
            ["applications", "drives", "processes", "system", "windows"],
            None,
        ),
        "list installed applications": (["applications"], None),
        "show running processes": (["processes"], None),
        "what apps are open": (["windows"], None),
        "list logical drives": (["drives"], None),
        "find a file named report.csv across all drives": (["files"], "report.csv"),
    }

    for query, (scopes, expected_query) in cases.items():
        action = route_command(query)
        assert action is not None
        assert action.action_type == "discover_system_resources"
        assert action.parameters["scopes"] == scopes
        assert action.parameters.get("query") == expected_query


def test_resource_discovery_is_classified_as_an_ordinary_action():
    action = AutomationAction(
        action_type="discover_system_resources",
        parameters={"scopes": ["processes"]},
        risk=RiskLevel.LOW,
    )
    assert classify_action(action) is ActionTier.ORDINARY


def test_resource_discovery_executes_without_confirmation_and_records_audit(
    monkeypatch,
    tmp_path,
):
    from engine.automation.audit import list_recent_audit_events
    from engine.automation import executor

    monkeypatch.setenv(
        "JARVIS_AUTOMATION_AUDIT_DB",
        str(tmp_path / "resource-audit.sqlite3"),
    )
    monkeypatch.setattr(
        executor,
        "discover_system_resources",
        lambda scopes, query=None: {
            "schema_version": 1,
            "scopes": list(scopes),
            "running_processes": [
                {"name": "notepad.exe", "pid": 42},
                {"name": "chrome.exe", "pid": 99},
            ],
        },
    )
    monkeypatch.setattr(
        executor,
        "request_authorization",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("read-only inventory must not request confirmation")
        ),
    )

    action = AutomationAction(
        action_type="discover_system_resources",
        parameters={"scopes": ["processes"]},
        risk=RiskLevel.LOW,
    )
    result = execute_action(action)

    assert result["success"] is True
    assert "2 running processes returned" in result["spoken_message"]
    assert result["message"].startswith("# J.A.R.V.I.S — System resource report")
    assert "## Running processes" in result["message"]
    assert "| notepad.exe | 42 |" in result["message"]
    assert "## System overview" not in result["message"]
    assert result["summary"] == result["spoken_message"]
    assert result["inventory"]["scopes"] == ["processes"]

    events = list_recent_audit_events()
    assert len(events) == 2
    assert {event["event"] for event in events} == {
        "requested",
        "execution_succeeded",
    }
    assert all(event["action_type"] == "discover_system_resources" for event in events)
    assert all(event["permission_tier"] == "ordinary" for event in events)


def test_resource_report_labels_installed_and_usable_memory_separately(monkeypatch):
    from engine.automation import executor

    monkeypatch.setattr(
        executor,
        "discover_system_resources",
        lambda scopes, query=None: {
            "schema_version": 1,
            "scopes": ["system", "applications", "drives"],
            "system": {
                "operating_system": "Windows 11",
                "os_edition": "Home Single Language",
                "os_release": "26H2",
                "os_version": "10.0.26300.9711",
                "os_build": "26300",
                "os_update_revision": "9711",
                "architecture": "AMD64",
                "processor": "13th Gen Intel(R) Core(TM) i7-13620H",
                "physical_core_count": 10,
                "logical_cpu_count": 16,
                "processor_clock_mhz": 2400,
                "memory_installed_bytes": 16 * 1024 ** 3,
                "memory_total_bytes": int(15.7 * 1024 ** 3),
                "memory_used_bytes": int(13.6 * 1024 ** 3),
                "memory_available_bytes": int(2.1 * 1024 ** 3),
                "memory_load_percent": 86.6,
            },
            "installed_applications": [
                {
                    "name": "example app",
                    "category": "installed_application",
                    "publisher": "Example Publisher",
                    "version": "1.2.3",
                    "sources": ["uninstall_registry_machine"],
                },
                {
                    "name": "portable tool",
                    "category": "shortcut_only",
                    "publisher": None,
                    "version": None,
                    "sources": ["start_menu_shortcut"],
                },
            ],
            "drives": [
                {
                    "root": "C:\\",
                    "type": "fixed",
                    "volume_label": "Windows",
                    "filesystem": "NTFS",
                    "total_bytes": 500 * 1024 ** 3,
                    "used_bytes": 300 * 1024 ** 3,
                    "free_bytes": 200 * 1024 ** 3,
                }
            ],
        },
    )
    action = AutomationAction(
        action_type="discover_system_resources",
        parameters={"scopes": ["system", "applications", "drives"]},
        risk=RiskLevel.LOW,
    )

    result = executor._execute_system_resource_discovery(action)
    report = result["message"]

    assert "Windows 11 Home Single Language 26H2" in report
    assert "10.0.26300.9711" in report
    assert "26300 (UBR 9711)" in report
    assert "13th Gen Intel(R) Core(TM) i7-13620H" in report
    assert "10 physical cores, 16 logical processors" in report
    assert "Installed physical RAM | 16.0 GB" in report
    assert "Usable physical RAM | 15.7 GB" in report
    assert "Calculated physical memory use | 86.6%" in report
    assert "Installed desktop applications" in report
    assert "Start Menu shortcuts (installation not verified)" in report
    assert "NTFS" in report
