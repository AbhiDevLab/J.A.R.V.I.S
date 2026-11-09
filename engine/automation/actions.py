from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class AutomationAction:
    """
    Structured action requested by J.A.R.V.I.S.

    The executor decides whether the action requires
    authorization before it is performed.
    """

    action_type: str
    parameters: Dict[str, Any]
    risk: RiskLevel = RiskLevel.LOW
    # Set only by a trusted, typed automation handler when Windows elevation
    # is actually required. This never causes the parent JARVIS process to
    # run as Administrator.
    requires_admin: bool = False


# Actions that can affect the system substantially.
#
# This list is intentionally based on the semantic action,
# NOT on which Python API ultimately performs it.
HIGH_RISK_ACTIONS = {
    "shell_command",
    "powershell_command",
    "python_script",
    "delete_file",
    "delete_folder",
    "delete_all_matches",
    "kill_process",
    "system_power",
    "modify_system_settings",
    "install_software",
    "uninstall_software",
    "registry_write",
    "service_control",
    "firewall_configuration",
    "system_wide_install",
    "system_wide_uninstall",
    "elevated_powershell",
    "create_system_task",
    "user_account_management",
}


def requires_confirmation(action: AutomationAction) -> bool:
    """Backward-compatible wrapper around the central action policy."""
    from .policy import ApprovalMode, get_action_policy

    return get_action_policy(action).approval_mode is not ApprovalMode.AUTOMATIC