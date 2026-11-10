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
    assert "notepad.exe (PID 42)" in result["message"]
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
