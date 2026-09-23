from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class RiskLevel(str, Enum):
    LOW = "low"
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
    "kill_process",
    "system_power",
    "modify_system_settings",
    "install_software",
    "uninstall_software",
}


def requires_confirmation(action: AutomationAction) -> bool:
    """
    Determine whether this action must pass the security gate.
    """

    if action.action_type in HIGH_RISK_ACTIONS:
        return True

    return action.risk == RiskLevel.HIGH