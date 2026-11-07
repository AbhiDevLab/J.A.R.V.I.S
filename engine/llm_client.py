"""Reliable OmniRoute chat client for J.A.R.V.I.S.

Phase 8.7/8.8:
- Classifies provider failures for safe recovery.
- Retries only transient failures with a bounded backoff.
- Supports an explicitly configured fallback model on the same OmniRoute endpoint.
- Keeps a single, non-streaming string response contract for callers.

Provider selection and credentials remain the responsibility of Phase 10.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests


_RETRYABLE_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class LLMRequestError(RuntimeError):
    """A normalized, user-safe LLM failure.

    The category is suitable for diagnostics and recovery decisions. It does not
    include API keys, request headers, or raw provider response bodies.
    """

    def __init__(
        self,
        message: str,
        *,
        category: str,
        retryable: bool,
        status_code: Optional[int] = None,
        model: str = "",
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = bool(retryable)
        self.status_code = status_code
        self.model = model


def _positive_int(value: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _bounded_float(value: str, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "omniroute").strip().lower()
        self.base_url = os.getenv(
            "OMNIROUTE_BASE_URL", "http://localhost:20128/v1"
        ).strip().rstrip("/")
        self.api_key = os.getenv("OMNIROUTE_API_KEY", "").strip()
        self.model = os.getenv("OMNIROUTE_MODEL", "Teamax").strip()
        self.fallback_model = os.getenv("OMNIROUTE_FALLBACK_MODEL", "").strip()
        self.timeout = _positive_int(
            os.getenv("OMNIROUTE_TIMEOUT", "180"), 180, 1, 600
        )
        self.max_attempts = _positive_int(
            os.getenv("JARVIS_LLM_MAX_ATTEMPTS", "2"), 2, 1, 3
        )
        self.retry_backoff = _bounded_float(
            os.getenv("JARVIS_LLM_RETRY_BACKOFF", "0.5"), 0.5, 0.0, 2.0
        )

    def validate_config(self) -> None:
        """Validate the currently supported OmniRoute configuration."""
        if self.provider != "omniroute":
            raise LLMRequestError(
                "The configured LLM provider is not supported by this runtime.",
                category="configuration",
                retryable=False,
                model=self.model,
            )

        missing = [
            key
            for key, value in (
                ("OMNIROUTE_API_KEY", self.api_key),
                ("OMNIROUTE_BASE_URL", self.base_url),
                ("OMNIROUTE_MODEL", self.model),
            )
            if not value
        ]
        if missing:
            raise LLMRequestError(
                "Missing OmniRoute configuration: " + ", ".join(missing),
                category="configuration",
                retryable=False,
                model=self.model,
            )

        if self.fallback_model and self.fallback_model == self.model:
            # Treat an identical fallback as unset; it cannot provide resilience.
            self.fallback_model = ""

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        if not isinstance(data, dict):
            raise ValueError("response root is not an object")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("response contains no choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("response choice is malformed")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            message = {}

        content = message.get("content")
        if content is None:
            content = first_choice.get("text")

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("text") is not None:
                    parts.append(str(item["text"]))
            content = "".join(parts)

        if not isinstance(content, str) or not content.strip():
            raise ValueError("response content is empty")

        return content.strip()

    @staticmethod
    def _provider_error_is_transient(error: Any) -> bool:
        """Recognize common transient provider error labels without guessing."""
        if isinstance(error, dict):
            label = " ".join(
                str(error.get(key, ""))
                for key in ("code", "type", "message")
            ).casefold()
        else:
            label = str(error or "").casefold()
        return any(
            token in label
            for token in ("rate_limit", "rate limit", "overloaded", "temporarily unavailable", "timeout")
        )

    def _single_request(self, prompt: str, model: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise LLMRequestError(
                "The AI service timed out.",
                category="timeout",
                retryable=True,
                model=model,
            ) from exc
        except requests.ConnectionError as exc:
            raise LLMRequestError(
                "The AI service could not be reached.",
                category="connection",
                retryable=True,
                model=model,
            ) from exc
        except requests.RequestException as exc:
            raise LLMRequestError(
                "The AI request failed before a response was received.",
                category="transport",
                retryable=True,
                model=model,
            ) from exc

        status = getattr(response, "status_code", None)
        if not getattr(response, "ok", False):
            retryable = status in _RETRYABLE_HTTP_STATUSES
            category = (
                "rate_limit"
                if status == 429
                else "http_transient"
                if retryable
                else "http_client"
            )
            raise LLMRequestError(
                f"The AI service returned HTTP {status or 'error'}.",
                category=category,
                retryable=retryable,
                status_code=status,
                model=model,
            )

        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise LLMRequestError(
                "The AI service returned an unreadable response.",
                category="invalid_response",
                retryable=True,
                status_code=status,
                model=model,
            ) from exc

        if isinstance(data, dict) and data.get("error"):
            provider_error = data.get("error")
            transient = self._provider_error_is_transient(provider_error)
            raise LLMRequestError(
                "The AI provider reported a request error.",
                category="provider_transient" if transient else "provider_error",
                retryable=transient,
                status_code=status,
                model=model,
            )

        try:
            content = self._extract_content(data)
        except (ValueError, TypeError, AttributeError) as exc:
            raise LLMRequestError(
                "The AI service returned an empty or malformed answer.",
                category="invalid_response",
                retryable=True,
                status_code=status,
                model=model,
            ) from exc

        actual_model = data.get("model") if isinstance(data, dict) else None
        provider = data.get("provider") if isinstance(data, dict) else None
        print(f"OmniRoute response received using {actual_model or model}.")
        if provider:
            print(f"OmniRoute provider: {provider}")
        return content

    def _request_with_retries(self, prompt: str, model: str, attempts: int) -> str:
        last_error: Optional[LLMRequestError] = None
        for attempt in range(attempts):
            try:
                return self._single_request(prompt, model)
            except LLMRequestError as exc:
                last_error = exc
                print(
                    f"OmniRoute {exc.category} failure for model {model} "
                    f"(attempt {attempt + 1}/{attempts})."
                )
                if not exc.retryable or attempt + 1 >= attempts:
                    break
                delay = min(self.retry_backoff * (2 ** attempt), 2.0)
                if delay:
                    time.sleep(delay)

        assert last_error is not None
        raise last_error

    def ask(self, prompt: str) -> str:
        """Send a bounded, non-streaming request through OmniRoute."""
        self.validate_config()
        if not isinstance(prompt, str) or not prompt.strip():
            raise LLMRequestError(
                "The AI request did not contain a prompt.",
                category="invalid_request",
                retryable=False,
                model=self.model,
            )

        print(f"OmniRoute primary model: {self.model}")
        try:
            return self._request_with_retries(
                prompt, self.model, self.max_attempts
            )
        except LLMRequestError as primary_error:
            if not self.fallback_model or not primary_error.retryable:
                raise

            print(
                "Primary OmniRoute model unavailable; trying the configured "
                f"fallback model {self.fallback_model}."
            )
            try:
                result = self._request_with_retries(
                    prompt, self.fallback_model, 1
                )
                print(
                    f"OmniRoute fallback succeeded using {self.fallback_model}."
                )
                return result
            except LLMRequestError as fallback_error:
                raise LLMRequestError(
                    "The primary and configured fallback AI models are unavailable.",
                    category="fallback_failed",
                    retryable=False,
                    status_code=fallback_error.status_code,
                    model=self.fallback_model,
                ) from primary_error


llm_client = LLMClient()


def get_llm_client() -> LLMClient:
    """Return the process-wide LLM client."""
    return llm_client


def ask_llm(prompt: str) -> str:
    """Backward-compatible public API used by the rest of J.A.R.V.I.S."""
    return llm_client.ask(prompt)
