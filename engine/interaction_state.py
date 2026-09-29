"""Ephemeral interaction state for J.A.R.V.I.S.

Phase 8.1:
Keeps short-lived state that describes what JARVIS is currently waiting for.
This is deliberately separate from long-term conversation memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InteractionState:
    """Current task/dialogue state for the active JARVIS interaction."""

    state_type: str = ""
    prompt: str = ""
    action_type: str = ""
    candidates: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def clear(self) -> None:
        self.state_type = ""
        self.prompt = ""
        self.action_type = ""
        self.candidates.clear()
        self.data.clear()

    def set(
        self,
        state_type: str,
        *,
        prompt: str = "",
        action_type: str = "",
        candidates: List[str] | None = None,
        **data: Any,
    ) -> None:
        self.state_type = state_type
        self.prompt = prompt
        self.action_type = action_type
        self.candidates = list(candidates or [])
        self.data = dict(data)

    def has_state(self) -> bool:
        return bool(self.state_type)

    def as_context(self) -> str:
        """Return a compact, non-sensitive description for interpretation."""
        if not self.has_state():
            return ""

        lines = [
            f"Current interaction state: {self.state_type}",
        ]

        if self.action_type:
            lines.append(
                f"Pending action: {self.action_type}"
            )

        if self.prompt:
            lines.append(
                f"JARVIS is waiting for: {self.prompt}"
            )

        if self.candidates:
            lines.append(
                "Available choices:"
            )
            lines.extend(
                f"{index}. {value}"
                for index, value in enumerate(
                    self.candidates,
                    start=1,
                )
            )

        for key, value in self.data.items():
            if value is not None and value != "":
                lines.append(
                    f"{key}: {value}"
                )

        return "\n".join(lines)


interaction_state = InteractionState()


def get_interaction_state() -> InteractionState:
    return interaction_state
