"""Central, fail-closed permission policy for desktop/system automation."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .actions import HIGH_RISK_ACTIONS


class ActionTier(str, Enum):
    ORDINARY = "ordinary"
    SENSITIVE = "sensitive"
    CRITICAL = "critical"


class ApprovalMode(str, Enum):
    AUTOMATIC = "automatic"
    CONFIRM = "confirm"
    VOICE_FACE_UAC = "voice_face_uac"


@dataclass(frozen=True)
class PermissionConfig:
    ordinary_mode: str
    sensitive_mode: str
    critical_mode: str
    admin_access_mode: str


@dataclass(frozen=True)
class ActionPolicy:
    tier: ActionTier
    approval_mode: ApprovalMode
    requires_face: bool
    administrator_access: str


# These maps describe the semantic effect, not the Python API used.
# Unlisted actions are CRITICAL by default.
ORDINARY_ACTIONS = {
    "open_application",
    "read_application",
    "open_file",
    "open_folder",
    "list_directory",
    "find_file",
}

SENSITIVE_ACTIONS = {
    "close_application",
    "open_application_and_type",
    "type_text",
    "create_file",
    "create_folder",
    "rename_file",
    "rename_folder",
    "move_file",
    "copy_file",
}

CRITICAL_ACTIONS = set(HIGH_RISK_ACTIONS) | {
    "registry_write",
    "service_control",
    "firewall_configuration",
    "system_wide_install",
    "system_wide_uninstall",
    "elevated_powershell",
    "create_system_task",
    "user_account_management",
}


def _safe_setting(name: str, default: str, allowed: set[str]) -> str:
    value = str(os.getenv(name, default) or default).strip().lower()
    return value if value in allowed else default


def get_permission_config() -> PermissionConfig:
    """Read policy settings while enforcing a non-downgradable security floor."""
    return PermissionConfig(
        ordinary_mode=_safe_setting(
            "JARVIS_POLICY_ORDINARY", "automatic", {"automatic", "confirm"}
        ),
        # Sensitive operations can never be downgraded to automatic.
        sensitive_mode=_safe_setting(
            "JARVIS_POLICY_SENSITIVE", "confirm", {"confirm"}
        ),
        # Critical operations can never be downgraded below voice + face.
        critical_mode=_safe_setting(
            "JARVIS_POLICY_CRITICAL", "voice_face_uac", {"voice_face_uac"}
        ),
        admin_access_mode=_safe_setting(
            "JARVIS_ADMIN_ACCESS", "ondemand", {"ondemand", "never"}
        ),
    )


def classify_action(action: Any) -> ActionTier:
    """Return an action's minimum required trust tier.

    Unknown types and explicitly elevated actions fail closed as CRITICAL.
    A HIGH risk marker always overrides the ordinary/sensitive allowlists.
    """
    action_type = str(getattr(action, "action_type", "") or "").strip().lower()
    risk = getattr(action, "risk", None)
    risk_value = str(getattr(risk, "value", risk) or "").strip().lower()

    if (
        bool(getattr(action, "requires_admin", False))
        or action_type in CRITICAL_ACTIONS
        or risk_value == "high"
    ):
        return ActionTier.CRITICAL

    if action_type in SENSITIVE_ACTIONS or risk_value == "medium":
        return ActionTier.SENSITIVE

    if action_type in ORDINARY_ACTIONS:
        return ActionTier.ORDINARY

    return ActionTier.CRITICAL


def get_action_policy(action: Any) -> ActionPolicy:
    tier = classify_action(action)
    config = get_permission_config()
    if tier is ActionTier.ORDINARY:
        mode = ApprovalMode(config.ordinary_mode)
    elif tier is ActionTier.SENSITIVE:
        mode = ApprovalMode.CONFIRM
    else:
        mode = ApprovalMode.VOICE_FACE_UAC
    return ActionPolicy(
        tier=tier,
        approval_mode=mode,
        requires_face=tier is ActionTier.CRITICAL,
        administrator_access=config.admin_access_mode,
    )


def action_fingerprint(action: Any) -> str:
    """Hash the exact operation and arguments for one-shot approval binding."""
    risk = getattr(action, "risk", None)
    payload = {
        "action_type": str(getattr(action, "action_type", "") or ""),
        "parameters": getattr(action, "parameters", {}) or {},
        "risk": str(getattr(risk, "value", risk) or ""),
        "requires_admin": bool(getattr(action, "requires_admin", False)),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def describe_action(action: Any, *, max_detail: int = 260) -> str:
    """Produce a concise approval description from the structured action."""
    action_type = str(getattr(action, "action_type", "") or "unknown").strip()
    params = getattr(action, "parameters", {}) or {}
    labels = {
        "close_application": "close application",
        "type_text": "type text into an application",
        "open_application_and_type": "open an application and type text",
        "create_file": "create a file",
        "create_folder": "create a folder",
        "rename_file": "rename a file",
        "rename_folder": "rename a folder",
        "move_file": "move a file",
        "copy_file": "copy a file",
        "delete_file": "delete a file",
        "delete_folder": "delete a folder",
        "delete_all_matches": "delete all matching files",
        "shell_command": "execute a shell command",
        "powershell_command": "execute a PowerShell command",
        "python_script": "run a Python script",
        "kill_process": "terminate a process",
        "system_power": "perform a system power operation",
        "modify_system_settings": "change system settings",
        "install_software": "install software",
        "uninstall_software": "uninstall software",
        "registry_write": "modify the Windows registry",
        "service_control": "control a Windows service",
        "firewall_configuration": "change firewall configuration",
        "create_system_task": "create a system scheduled task",
    }
    description = labels.get(action_type, action_type.replace("_", " "))

    target = (
        params.get("path")
        or params.get("application")
        or params.get("process_name")
        or params.get("service_name")
        or params.get("name")
    )
    if action_type in {"move_file", "copy_file"}:
        source = params.get("source") or params.get("path")
        destination = params.get("destination") or params.get("destination_path")
        if source or destination:
            target = f"from {source or 'the selected source'} to {destination or 'the selected destination'}"
    elif action_type == "delete_all_matches":
        paths = params.get("paths") or []
        target = f"{len(paths)} matching items" if isinstance(paths, (list, tuple)) else target
    elif action_type in {"shell_command", "powershell_command"}:
        target = params.get("command") or params.get("script") or target

    if target not in (None, ""):
        detail = str(target).strip()
        if len(detail) > max_detail:
            detail = detail[:max_detail].rstrip() + " … (truncated)"
        description = f"{description}: {detail}"

    if bool(getattr(action, "requires_admin", False)):
        description += " (requires administrator privileges)"
    return description
