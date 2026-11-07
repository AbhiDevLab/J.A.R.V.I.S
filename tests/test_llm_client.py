"""Phase 8.7/8.8 tests for bounded LLM recovery and OmniRoute fallback."""

from unittest.mock import patch

import pytest
import requests

from engine.llm_client import LLMClient, LLMRequestError


def configure_client(monkeypatch, **overrides):
    values = {
        "LLM_PROVIDER": "omniroute",
        "OMNIROUTE_BASE_URL": "http://localhost:20128/v1",
        "OMNIROUTE_API_KEY": "test-key",
        "OMNIROUTE_MODEL": "primary-model",
        "OMNIROUTE_FALLBACK_MODEL": "",
        "OMNIROUTE_TIMEOUT": "5",
        "JARVIS_LLM_MAX_ATTEMPTS": "2",
        "JARVIS_LLM_RETRY_BACKOFF": "0",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return LLMClient()


def response(status_code=200, payload=None):
    class FakeResponse:
        def __init__(self):
            self.status_code = status_code
            self.ok = 200 <= status_code < 400

        def json(self):
            if isinstance(payload, Exception):
                raise payload
            return payload or {}

    return FakeResponse()


def success_response(text="JARVIS response", model="primary-model"):
    return response(
        200,
        {
            "model": model,
            "choices": [{"message": {"content": text}}],
        },
    )


def test_successful_response_keeps_string_contract(monkeypatch):
    client = configure_client(monkeypatch)
    with patch("engine.llm_client.requests.post", return_value=success_response()):
        assert client.ask("hello") == "JARVIS response"


def test_connection_timeout_retries_once_then_succeeds(monkeypatch):
    client = configure_client(monkeypatch)
    with patch(
        "engine.llm_client.requests.post",
        side_effect=[requests.Timeout(), success_response()],
    ) as post:
        with patch("engine.llm_client.time.sleep") as sleep:
            assert client.ask("hello") == "JARVIS response"

    assert post.call_count == 2
    sleep.assert_called_once_with(0)


def test_non_retryable_http_401_is_not_retried_or_fallen_back(monkeypatch):
    client = configure_client(
        monkeypatch,
        OMNIROUTE_FALLBACK_MODEL="fallback-model",
    )
    with patch(
        "engine.llm_client.requests.post",
        return_value=response(401, {"error": "unauthorized"}),
    ) as post:
        with pytest.raises(LLMRequestError) as exc_info:
            client.ask("hello")

    assert exc_info.value.category == "http_client"
    assert exc_info.value.retryable is False
    assert post.call_count == 1


def test_primary_model_retries_then_uses_configured_omniroute_fallback(monkeypatch):
    client = configure_client(
        monkeypatch,
        OMNIROUTE_FALLBACK_MODEL="fallback-model",
    )
    with patch(
        "engine.llm_client.requests.post",
        side_effect=[
            response(503, {"error": "temporarily unavailable"}),
            response(503, {"error": "temporarily unavailable"}),
            success_response("Fallback answer", "fallback-model"),
        ],
    ) as post:
        assert client.ask("hello") == "Fallback answer"

    assert post.call_count == 3
    models = [call.kwargs["json"]["model"] for call in post.call_args_list]
    assert models == ["primary-model", "primary-model", "fallback-model"]


def test_invalid_json_is_retried_and_then_classified(monkeypatch):
    client = configure_client(monkeypatch)
    with patch(
        "engine.llm_client.requests.post",
        side_effect=[
            response(200, ValueError("bad JSON")),
            response(200, ValueError("bad JSON")),
        ],
    ) as post:
        with pytest.raises(LLMRequestError) as exc_info:
            client.ask("hello")

    assert post.call_count == 2
    assert exc_info.value.category == "invalid_response"
    assert exc_info.value.retryable is True


def test_empty_model_content_is_not_returned_as_a_success(monkeypatch):
    client = configure_client(monkeypatch)
    empty = response(200, {"choices": [{"message": {"content": "  "}}]})
    with patch(
        "engine.llm_client.requests.post",
        side_effect=[empty, empty],
    ):
        with pytest.raises(LLMRequestError) as exc_info:
            client.ask("hello")

    assert exc_info.value.category == "invalid_response"


def test_transient_provider_error_object_is_retried(monkeypatch):
    client = configure_client(monkeypatch)
    with patch(
        "engine.llm_client.requests.post",
        side_effect=[
            response(200, {"error": {"code": "overloaded"}}),
            success_response(),
        ],
    ) as post:
        assert client.ask("hello") == "JARVIS response"

    assert post.call_count == 2


def test_fallback_model_identical_to_primary_is_ignored(monkeypatch):
    client = configure_client(
        monkeypatch,
        OMNIROUTE_FALLBACK_MODEL="primary-model",
    )
    with patch(
        "engine.llm_client.requests.post",
        return_value=response(503, {"error": "unavailable"}),
    ) as post:
        with pytest.raises(LLMRequestError):
            client.ask("hello")

    assert post.call_count == 2


def test_invalid_configuration_fails_before_network_call(monkeypatch):
    client = configure_client(monkeypatch, OMNIROUTE_API_KEY="")
    with patch("engine.llm_client.requests.post") as post:
        with pytest.raises(LLMRequestError) as exc_info:
            client.ask("hello")

    assert exc_info.value.category == "configuration"
    assert exc_info.value.retryable is False
    post.assert_not_called()


def test_invalid_provider_is_not_silently_switched(monkeypatch):
    client = configure_client(monkeypatch, LLM_PROVIDER="openai")
    with patch("engine.llm_client.requests.post") as post:
        with pytest.raises(LLMRequestError) as exc_info:
            client.ask("hello")

    assert exc_info.value.category == "configuration"
    post.assert_not_called()


def test_extract_content_accepts_openai_compatible_text_parts():
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "world"},
                    ]
                }
            }
        ]
    }
    assert LLMClient._extract_content(payload) == "Hello world"
