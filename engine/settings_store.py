"""Persistent user settings for J.A.R.V.I.S."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any


_SETTINGS_LOCK = Lock()

_DEFAULT_SETTINGS: dict[str, Any] = {
    "voice_enabled": True,
    "response_language": "auto",
}

_SETTINGS_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "settings.json"
)


def _ensure_settings_file() -> None:
    _SETTINGS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if _SETTINGS_PATH.exists():
        return

    _SETTINGS_PATH.write_text(
        json.dumps(
            _DEFAULT_SETTINGS,
            indent=2,
        ),
        encoding="utf-8",
    )


def _normalise_settings(
    settings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "voice_enabled": bool(
            settings.get(
                "voice_enabled",
                _DEFAULT_SETTINGS["voice_enabled"],
            )
        ),
        "response_language": (
            str(
                settings.get(
                    "response_language",
                    _DEFAULT_SETTINGS[
                        "response_language"
                    ],
                )
            )
            .strip()
            .lower()
        ),
    }


def load_settings() -> dict[str, Any]:
    with _SETTINGS_LOCK:
        try:
            _ensure_settings_file()

            raw = json.loads(
                _SETTINGS_PATH.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(raw, dict):
                raise ValueError(
                    "Settings file must contain an object."
                )

            settings = {
                **_DEFAULT_SETTINGS,
                **raw,
            }

            settings = _normalise_settings(
                settings
            )

            # Repair invalid values automatically.
            if settings["response_language"] not in {
                "auto",
                "en",
                "hi",
            }:
                settings["response_language"] = "auto"

            return settings

        except Exception as exc:
            print(
                f"Settings load error: {exc}"
            )

            return dict(
                _DEFAULT_SETTINGS
            )


def save_settings(
    settings: dict[str, Any],
) -> dict[str, Any]:
    with _SETTINGS_LOCK:
        try:
            _ensure_settings_file()

            normalised =_normalise_settings(settings)

            if normalised[
                "response_language"
            ] not in {
                "auto",
                "en",
                "hi",
            }:
                normalised[
                    "response_language"
                ] = "auto"

            _SETTINGS_PATH.write_text(
                json.dumps(
                    normalised,
                    indent=2,
                ),
                encoding="utf-8",
            )

            return normalised

        except Exception as exc:
            print(
                f"Settings save error: {exc}"
            )

            return load_settings()


def update_settings(
    updates: dict[str, Any],
) -> dict[str, Any]:
    current = load_settings()

    if "voice_enabled" in updates:
        current["voice_enabled"] = bool(
            updates["voice_enabled"]
        )

    if "response_language" in updates:
        current["response_language"] = (
            str(
                updates[
                    "response_language"
                ]
            )
            .strip()
            .lower()
        )

    return save_settings(current)