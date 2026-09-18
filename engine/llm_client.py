"""
Provider-neutral LLM client for J.A.R.V.I.S.

Phase 5B:
- Uses the local OmniRoute OpenAI-compatible API.
- Sends requests to a configured Teamax combo.
- Explicitly disables streaming because J.A.R.V.I.S expects one complete
  response string.
- Leaves model routing/fallback entirely to OmniRoute.
"""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


class LLMClient:
    def __init__(self):
        self.provider = os.getenv(
            "LLM_PROVIDER",
            "omniroute",
        ).strip().lower()

        self.base_url = os.getenv(
            "OMNIROUTE_BASE_URL",
            "http://localhost:20128/v1",
        ).rstrip("/")

        self.api_key = os.getenv(
            "OMNIROUTE_API_KEY",
            "",
        ).strip()

        self.model = os.getenv(
            "OMNIROUTE_MODEL",
            "Teamax",
        ).strip()

        try:
            self.timeout = int(
                os.getenv(
                    "OMNIROUTE_TIMEOUT",
                    "180",
                )
            )
        except Exception:
            self.timeout = 180

    def validate_config(self) -> None:
        """Validate the OmniRoute configuration before startup."""
        if self.provider != "omniroute":
            raise ValueError(
                "Unsupported LLM_PROVIDER. "
                "Phase 5B currently requires: omniroute"
            )

        missing = []

        if not self.api_key:
            missing.append(
                "OMNIROUTE_API_KEY"
            )

        if not self.base_url:
            missing.append(
                "OMNIROUTE_BASE_URL"
            )

        if not self.model:
            missing.append(
                "OMNIROUTE_MODEL"
            )

        if missing:
            raise ValueError(
                "Missing OmniRoute configuration: "
                + ", ".join(missing)
            )

    @staticmethod
    def _extract_content(
        data: Dict[str, Any],
    ) -> str:
        choices = data.get("choices")

        if not choices:
            raise RuntimeError(
                "OmniRoute returned no choices."
            )

        first_choice = choices[0]

        message = first_choice.get(
            "message",
            {},
        )

        content = message.get(
            "content"
        )

        if content is None:
            content = first_choice.get(
                "text"
            )

        if isinstance(content, list):
            parts = []

            for item in content:
                if isinstance(item, dict):
                    text = item.get(
                        "text"
                    )

                    if text:
                        parts.append(
                            str(text)
                        )

            content = "".join(parts)

        if not content:
            raise RuntimeError(
                "OmniRoute returned an empty response."
            )

        return str(content).strip()

    def ask(
        self,
        prompt: str,
    ) -> str:
        """
        Send one non-streaming chat request to OmniRoute.

        Teamax remains responsible for model selection/routing/fallback.
        """
        self.validate_config()

        url = (
            f"{self.base_url}"
            "/chat/completions"
        )

        headers = {
            "Authorization":
                f"Bearer {self.api_key}",
            "Content-Type":
                "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
        }

        print(
            f"🧠 OmniRoute → {self.model}"
        )

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

        except requests.RequestException as e:
            raise RuntimeError(
                f"OmniRoute connection failed: {e}"
            ) from e

        if not response.ok:
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text

            raise RuntimeError(
                "OmniRoute request failed "
                f"with HTTP {response.status_code}: "
                f"{error_body}"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise RuntimeError(
                "OmniRoute returned invalid JSON."
            ) from e

        if data.get("error"):
            raise RuntimeError(
                f"OmniRoute error: "
                f"{data['error']}"
            )

        content = self._extract_content(
            data
        )

        actual_model = data.get(
            "model"
        )

        provider = data.get(
            "provider"
        )

        if actual_model:
            print(
                f"OmniRoute model: "
                f"{actual_model}"
            )

        if provider:
            print(
                f"OmniRoute provider: "
                f"{provider}"
            )

        print(
            "OmniRoute response received."
        )

        return content


llm_client = LLMClient()


def get_llm_client() -> LLMClient:
    return llm_client


def ask_llm(prompt: str) -> str:
    return llm_client.ask(prompt)