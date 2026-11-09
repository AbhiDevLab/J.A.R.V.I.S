"""Phase 7.4.1 central permission policy and authorization regressions."""
from __future__ import annotations

import sqlite3

from engine.automation.actions import AutomationAction, RiskLevel, requires_confirmation
from engine.automation import executor
from engine.automation.audit import list_recent_audit_events, record_action_event
from engine.automation.policy import (
    ActionTier,
    ApprovalMode,
    action_fingerprint,
    classify_action,
    describe_action,
    get_action_policy,
)


def make_action(action_type, parameters=None, *, risk=RiskLevel.LOW, requires_admin=False):
    return AutomationAction(
        action_type=action_type,
        parameters=dict(parameters or {}),
        risk=risk,
        requires_admin=requires_admin,
    )


def test_policy_classifies_ordinary_sensitive_and_critical_operations():
    assert classify_action(make_action("open_application", {"application": "notepad"})) is ActionTier.ORDINARY
    assert classify_action(make_action("read_application", {"application": "notepad"})) is ActionTier.ORDINARY
    assert classify_action(make_action("close_application", {"application": "telegram"})) is ActionTier.SENSITIVE
    assert classify_action(make_action("type_text", {"application": "notepad", "text": "hello"})) is ActionTier.SENSITIVE
    assert classify_action(make_action("create_file", {"path": "notes.txt"})) is ActionTier.SENSITIVE
    assert classify_action(make_action("delete_file", {"path": "notes.txt"})) is ActionTier.CRITICAL
    assert classify_action(make_action("shell_command", {"command": "whoami"})) is ActionTier.CRITICAL


def test_unknown_action_types_fail_closed_as_critical():
    assert classify_action(make_action("future_unregistered_action")) is ActionTier.CRITICAL


def test_high_risk_marker_overrides_an_ordinary_action_type():
    action = make_action("read_application", risk=RiskLevel.HIGH)
    assert classify_action(action) is ActionTier.CRITICAL
    assert requires_confirmation(action) is True


def test_admin_required_metadata_always_forces_critical_tier():
    action = make_action("open_application", {"application": "services"}, requires_admin=True)
    assert classify_action(action) is ActionTier.CRITICAL
    assert get_action_policy(action).requires_face is True


def test_policy_settings_cannot_downgrade_sensitive_or_critical_actions(monkeypatch):
    monkeypatch.setenv("JARVIS_POLICY_ORDINARY", "automatic")
    monkeypatch.setenv("JARVIS_POLICY_SENSITIVE", "automatic")
    monkeypatch.setenv("JARVIS_POLICY_CRITICAL", "confirm")
    monkeypatch.setenv("JARVIS_ADMIN_ACCESS", "ondemand")

    sensitive = get_action_policy(make_action("type_text", {"text": "hello"}))
    critical = get_action_policy(make_action("delete_file", {"path": "x"}))

    assert sensitive.approval_mode is ApprovalMode.CONFIRM
    assert sensitive.requires_face is False
    assert critical.approval_mode is ApprovalMode.VOICE_FACE_UAC
    assert critical.requires_face is True


def test_ordinary_actions_do_not_require_confirmation():
    action = make_action("open_folder", {"path": "C:/Users/Test/Downloads"})
    assert requires_confirmation(action) is False


def test_sensitive_and_critical_actions_require_confirmation():
    assert requires_confirmation(make_action("close_application", {"application": "telegram"})) is True
    assert requires_confirmation(make_action("shell_command", {"command": "whoami"})) is True


def test_action_fingerprint_is_order_independent_but_argument_sensitive():
    first = make_action("move_file", {"source": "a.txt", "destination": "b.txt"})
    same = make_action("move_file", {"destination": "b.txt", "source": "a.txt"})
    changed = make_action("move_file", {"source": "a.txt", "destination": "c.txt"})

    assert action_fingerprint(first) == action_fingerprint(same)
    assert action_fingerprint(first) != action_fingerprint(changed)


def test_approval_description_contains_sensitive_target_and_typed_text():
    action = make_action(
        "type_text",
        {"application": "notepad", "text": "Phase 7.4 approved"},
    )
    description = describe_action(action)
    assert "notepad" in description
    assert "Phase 7.4 approved" in description


def test_audit_log_records_hash_and_metadata_without_raw_arguments(monkeypatch, tmp_path):
    database = tmp_path / "audit.sqlite3"
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(database))
    secret_command = "echo TOP_SECRET_TOKEN_123"
    action = make_action("shell_command", {"command": secret_command})

    assert record_action_event(action, ActionTier.CRITICAL, "requested", "policy_started")
    events = list_recent_audit_events()
    assert len(events) == 1
    assert events[0]["action_type"] == "shell_command"
    assert events[0]["permission_tier"] == "critical"
    assert events[0]["action_fingerprint"] == action_fingerprint(action)
    assert secret_command not in repr(events)
    assert "TOP_SECRET_TOKEN_123" not in repr(events)

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(automation_audit)")}
    assert "command" not in columns
    assert "parameters" not in columns


def test_executor_runs_ordinary_operation_without_authorization(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setattr(
        executor,
        "request_authorization",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ordinary action asked for approval")),
    )
    monkeypatch.setattr(
        executor,
        "_execute_open_application",
        lambda action: {"success": True, "message": "Opened Notepad."},
    )

    result = executor.execute_action(make_action("open_application", {"application": "notepad"}))
    assert result["success"] is True


def test_executor_requests_voice_confirmation_without_face_for_sensitive_action(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    approvals = []
    monkeypatch.setattr(
        executor,
        "request_authorization",
        lambda action, require_face=True: approvals.append((action_fingerprint(action), require_face)) or True,
    )
    monkeypatch.setattr(
        executor,
        "_execute_close_application",
        lambda action: {"success": True, "message": "Closed Telegram."},
    )

    result = executor.execute_action(make_action("close_application", {"application": "telegram"}))
    expected = make_action("close_application", {"application": "telegram"})
    assert result["success"] is True
    assert approvals == [(action_fingerprint(expected), False)]


def test_executor_requires_face_for_critical_action(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    approvals = []
    monkeypatch.setattr(
        executor,
        "request_authorization",
        lambda action, require_face=True: approvals.append(require_face) or True,
    )
    monkeypatch.setattr(
        executor,
        "_execute_shell_command",
        lambda action: {"success": True, "message": "Command completed."},
    )

    result = executor.execute_action(make_action("shell_command", {"command": "whoami"}))
    assert result["success"] is True
    assert approvals == [True]


def test_executor_blocks_sensitive_action_when_audit_store_unavailable(monkeypatch):
    executed = []
    monkeypatch.setattr(executor, "record_action_event", lambda *args, **kwargs: False)
    monkeypatch.setattr(executor, "request_authorization", lambda *args, **kwargs: True)
    monkeypatch.setattr(executor, "_execute_close_application", lambda action: executed.append(action))

    result = executor.execute_action(make_action("close_application", {"application": "telegram"}))
    assert result["success"] is False
    assert result["error_code"] == "audit_unavailable"
    assert executed == []


def test_executor_cancels_if_action_arguments_change_during_approval(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    executed = []

    def mutate_during_approval(action, *, require_face=True):
        action.parameters["application"] = "different-application"
        return True

    monkeypatch.setattr(executor, "request_authorization", mutate_during_approval)
    monkeypatch.setattr(executor, "_execute_close_application", lambda action: executed.append(action))

    result = executor.execute_action(make_action("close_application", {"application": "telegram"}))
    assert result["success"] is False
    assert result["error_code"] == "approval_fingerprint_mismatch"
    assert executed == []


def test_admin_required_action_uses_broker_and_never_normal_handler(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    approvals = []
    broker_calls = []
    normal_calls = []
    monkeypatch.setattr(
        executor,
        "request_authorization",
        lambda action, require_face=True: approvals.append(require_face) or True,
    )
    monkeypatch.setattr(
        executor,
        "execute_privileged_action",
        lambda action: broker_calls.append(action) or {
            "success": False,
            "error_code": "privileged_broker_unavailable",
            "message": "Broker unavailable.",
        },
    )
    monkeypatch.setattr(executor, "_execute_shell_command", lambda action: normal_calls.append(action))

    result = executor.execute_action(
        make_action("shell_command", {"command": "net start Spooler"}, requires_admin=True)
    )
    assert result["success"] is False
    assert result["error_code"] == "privileged_broker_unavailable"
    assert approvals == [True]
    assert len(broker_calls) == 1
    assert normal_calls == []


def test_executor_does_not_authorize_unsupported_action(monkeypatch):
    monkeypatch.setattr(
        executor,
        "request_authorization",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unsupported action prompted")),
    )
    result = executor.execute_action(make_action("unregistered_thing"))
    assert result["success"] is False
    assert result["error_code"] == "unsupported_action"


def test_critical_authorization_is_denied_when_approval_is_not_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    calls = []
    monkeypatch.setattr(executor, "request_authorization", lambda action, require_face=True: False)
    monkeypatch.setattr(executor, "_execute_shell_command", lambda action: calls.append(action))

    result = executor.execute_action(make_action("shell_command", {"command": "whoami"}))
    assert result["success"] is False
    assert result["cancelled"] is True
    assert calls == []


def test_sensitive_voice_approval_does_not_start_face_authentication(monkeypatch):
    import sys
    from types import ModuleType
    from engine.automation import security

    spoken = []
    fake_command = ModuleType("engine.command")
    fake_command.speak = lambda message: spoken.append(message)
    fake_command.takecommand = lambda: "I confirm"

    monkeypatch.setitem(sys.modules, "engine.command", fake_command)
    face_calls = []
    monkeypatch.setattr(security.recognizer, "AuthenticateFace", lambda: face_calls.append(True) or 1)

    approved = security.request_authorization(
        make_action("close_application", {"application": "telegram"}),
        require_face=False,
    )

    assert approved is True
    assert face_calls == []
    assert any("close application: telegram" in message for message in spoken)


def test_critical_voice_approval_requires_successful_face_authentication(monkeypatch):
    import sys
    from types import ModuleType
    from engine.automation import security

    fake_command = ModuleType("engine.command")
    fake_command.speak = lambda message: None
    fake_command.takecommand = lambda: "confirm"
    monkeypatch.setitem(sys.modules, "engine.command", fake_command)

    monkeypatch.setattr(security.recognizer, "AuthenticateFace", lambda: 1)
    assert security.request_authorization(
        make_action("delete_file", {"path": "C:/Temp/important.txt"}),
        require_face=True,
    ) is True

    monkeypatch.setattr(security.recognizer, "AuthenticateFace", lambda: 0)
    assert security.request_authorization(
        make_action("delete_file", {"path": "C:/Temp/important.txt"}),
        require_face=True,
    ) is False


def test_authorization_rejects_non_explicit_confirmation_without_face_auth(monkeypatch):
    import sys
    from types import ModuleType
    from engine.automation import security

    fake_command = ModuleType("engine.command")
    fake_command.speak = lambda message: None
    fake_command.takecommand = lambda: "That sounds reasonable"
    monkeypatch.setitem(sys.modules, "engine.command", fake_command)

    face_calls = []
    monkeypatch.setattr(security.recognizer, "AuthenticateFace", lambda: face_calls.append(True) or 1)

    assert security.request_authorization(
        make_action("delete_file", {"path": "C:/Temp/important.txt"}),
        require_face=True,
    ) is False
    assert face_calls == []


def test_authorization_normalization_handles_voice_punctuation():
    from engine.automation.security import _normalize

    assert _normalize("I confirm!") == "i confirm"
    assert _normalize("CANCEL.") == "cancel"


def test_admin_never_policy_blocks_elevation_dispatch(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_AUTOMATION_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("JARVIS_ADMIN_ACCESS", "never")
    monkeypatch.setattr(executor, "request_authorization", lambda action, require_face=True: True)
    broker_calls = []
    monkeypatch.setattr(executor, "execute_privileged_action", lambda action: broker_calls.append(action))

    result = executor.execute_action(
        make_action("shell_command", {"command": "net start Spooler"}, requires_admin=True)
    )
    assert result["success"] is False
    assert result["error_code"] == "admin_access_disabled"
    assert broker_calls == []
