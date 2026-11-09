"""Fail-closed boundary for future one-shot Windows UAC broker execution."""
from __future__ import annotations

from typing import Any


def execute_privileged_action(action: Any) -> dict[str, Any]:
    """Dispatch an approved admin-only action to the privileged broker.

    Phase 7.4.1 defines the contract and blocks unsafe fallback execution.
    The dedicated broker/UAC hand-off is implemented in Phase 7.4.4. Until
    that broker is registered, no action marked requires_admin is executed.
    """
    if not bool(getattr(action, "requires_admin", False)):
        return {
            "success": False,
            "message": "The privileged broker only accepts explicitly elevated actions.",
            "error_code": "invalid_privilege_request",
        }

    return {
        "success": False,
        "message": (
            "This operation requires administrator privileges, but the "
            "one-shot JARVIS privileged broker is not installed yet. "
            "No UAC prompt was launched and no system changes were made."
        ),
        "error_code": "privileged_broker_unavailable",
        "elevation_requested": False,
        "system_modified": False,
    }
