"""Tests for the LLM abstraction layer (Module 7)."""

import time

import httpx
import pytest

from src.config.settings import settings
from src.llm.llm import (
    GeminiClient,
    LlamaClient,
    LLMError,
    LLMResponse,
    MistralClient,
    MockLLMClient,
    OpenAICompatClient,
    QwenClient,
    RateLimitError,
    _mask_key,
    _masked_headers,
    get_llm_client,
)


def _make_response(
    status: int,
    body: dict | None = None,
    retry_after: str | None = None,
) -> httpx.Response:
    """Real httpx.Response so raise_for_status() raises a real HTTPStatusError."""
    headers = {"Content-Type": "application/json"}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    request = httpx.Request(
        "POST", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )
    return httpx.Response(status, request=request, json=body or {}, headers=headers)


def _quota_429_body() -> dict:
    return {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "You exceeded your current quota, limit: 0",
        }
    }


class TestFactory:
    def test_default_is_mock(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
        client = get_llm_client()
        assert isinstance(client, MockLLMClient)

    def test_provider_openai(self):
        client = get_llm_client(provider="openai", model="gpt-4o-mini", api_key="x")
        assert isinstance(client, OpenAICompatClient)
        assert client.model == "gpt-4o-mini"

    def test_provider_llama_defaults(self):
        client = get_llm_client(provider="llama")
        assert isinstance(client, LlamaClient)
        assert client.model == LlamaClient.default_model
        assert client.base_url == LlamaClient.default_base_url

    def test_provider_mistral_defaults(self):
        client = get_llm_client(provider="mistral")
        assert isinstance(client, MistralClient)
        assert client.model == MistralClient.default_model

    def test_provider_qwen_defaults(self):
        client = get_llm_client(provider="qwen")
        assert isinstance(client, QwenClient)
        assert client.model == QwenClient.default_model
        assert client.base_url == QwenClient.default_base_url

    def test_provider_gemini_uses_gemini_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "gem-key")
        monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
        client = get_llm_client(provider="gemini")
        assert isinstance(client, GeminiClient)
        assert client.model == "gemini-2.0-flash"
        assert client.api_key == "gem-key"
        assert "generativelanguage.googleapis.com" in client.base_url

    def test_unknown_provider_raises(self):
        with pytest.raises(LLMError):
            get_llm_client(provider="bogus")


class TestMockClient:
    def test_echoes_query_and_cites_sources(self):
        client = MockLLMClient()
        user = "QUESTION: performance of contracts\n[SOURCE 1] x\n[SOURCE 2] y\n"
        response = client.complete([
            {"role": "system", "content": "sys"},
            {"role": "user", "content": user},
        ])
        assert isinstance(response, LLMResponse)
        assert "performance of contracts" in response.text
        assert "[1]" in response.text
        assert "[2]" in response.text
        assert response.finish_reason == "stop"

    def test_chat_helper(self):
        client = MockLLMClient()
        response = client.chat(system="sys", user="QUESTION: hi")
        assert response.model == "mock-llm"

    def test_respects_max_tokens(self):
        client = MockLLMClient()
        response = client.complete(
            [{"role": "user", "content": "QUESTION: " + "x" * 500}], max_tokens=20
        )
        assert len(response.text) <= 20


class TestOpenAICompatClient:
    def test_chat_url(self):
        client = OpenAICompatClient(model="m", base_url="http://localhost:8000/v1", api_key="")
        assert client._chat_url == "http://localhost:8000/v1/chat/completions"

    def test_complete_parses_response(self, monkeypatch):
        def fake_post(url, json=None, headers=None, timeout=None):
            class FakeResp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "model": "gpt-test",
                        "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                        "usage": {"total_tokens": 7},
                    }

            assert "chat/completions" in url
            return FakeResp()

        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="gpt-test", base_url="http://x/v1", api_key="k")
        response = client.complete([{"role": "user", "content": "hi"}])
        assert response.text == "hello"
        assert response.model == "gpt-test"
        assert response.usage["total_tokens"] == 7

    def test_complete_network_error_raises(self, monkeypatch):
        def fail_post(url, json=None, headers=None, timeout=None):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(time, "sleep", lambda seconds: None)
        monkeypatch.setattr(httpx, "post", fail_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])

    def test_complete_bad_response_raises(self, monkeypatch):
        def fake_post(url, json=None, headers=None, timeout=None):
            class FakeResp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"foo": "bar"}

            return FakeResp()

        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])


class TestGeminiClient:
    def test_complete_uses_gemini_endpoint_and_key(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json

            class FakeResp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "model": "gemini-2.0-flash",
                        "choices": [{"message": {"content": "namaste"}}],
                        "usage": {"total_tokens": 9},
                    }

            return FakeResp()

        monkeypatch.setattr(httpx, "post", fake_post)
        client = GeminiClient(model="gemini-2.0-flash", api_key="gem-key")
        response = client.complete([{"role": "user", "content": "hi"}])
        assert response.text == "namaste"
        assert response.model == "gemini-2.0-flash"
        assert "generativelanguage.googleapis.com" in captured["url"]
        assert captured["headers"]["Authorization"] == "Bearer gem-key"
        assert captured["payload"]["model"] == "gemini-2.0-flash"

    def test_falls_back_to_gemini_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "from-settings")
        monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        client = GeminiClient()
        assert client.api_key == "from-settings"
        assert client.model == "gemini-2.5-flash"

    def test_honors_configured_gemini_model(self, monkeypatch):
        monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        client = GeminiClient(model=None)
        assert client.model == "gemini-2.5-flash"


class TestMasking:
    def test_mask_key_keeps_shape_only(self):
        key = "FAKE_TEST_KEY"
        masked = _mask_key(key)
        assert key not in masked
        assert masked.startswith("AQ.A")
        assert masked.endswith("vlrg")
        assert len(masked) < len(key)

    def test_mask_key_short_key(self):
        assert _mask_key("abc") == "***"
        assert _mask_key("") == ""

    def test_masked_headers_hide_authorization_only(self):
        masked = _masked_headers(
            {
                "Authorization": "Bearer super-secret-key",
                "Content-Type": "application/json",
            }
        )
        assert "super-secret-key" not in masked["Authorization"]
        assert masked["Content-Type"] == "application/json"


class TestRateLimitHandling:
    def test_quota_429_fails_immediately_without_retry(self, monkeypatch):
        attempts: list[int] = []
        sleeps: list[float] = []

        def fake_post(url, json=None, headers=None, timeout=None):
            attempts.append(1)
            return _make_response(429, body=_quota_429_body())

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(RateLimitError):
            client.complete([{"role": "user", "content": "hi"}])
        assert len(attempts) == 1
        assert sleeps == []

    def test_quota_429_carries_provider_retry_after_details(self, monkeypatch):
        body = {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": (
                    "You exceeded your current quota, please check your plan and "
                    "billing details. Please retry in 7.894865518s."
                ),
            }
        }

        def fake_post(url, json=None, headers=None, timeout=None):
            return _make_response(429, body=body)

        monkeypatch.setattr(time, "sleep", lambda seconds: None)
        monkeypatch.setattr(httpx, "post", fake_post)
        client = GeminiClient(model="m", api_key="k")
        with pytest.raises(RateLimitError) as exc_info:
            client.complete([{"role": "user", "content": "hi"}])
        error = exc_info.value
        assert error.status_code == 429
        assert error.quota_exhausted is True
        assert error.provider == "gemini"
        assert error.retry_after == pytest.approx(7.894865518)
        assert "RESOURCE_EXHAUSTED" in error.provider_body

    def test_non_quota_429_never_retried(self, monkeypatch):
        attempts: list[int] = []
        body = {"error": {"code": 429, "status": "RATE_LIMITED", "message": "slow down"}}

        def fake_post(url, json=None, headers=None, timeout=None):
            attempts.append(1)
            return _make_response(429, body=body)

        monkeypatch.setattr(time, "sleep", lambda seconds: None)
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(RateLimitError) as exc_info:
            client.complete([{"role": "user", "content": "hi"}])
        error = exc_info.value
        assert error.quota_exhausted is False
        assert len(attempts) == 1

    def test_retries_500_then_succeeds(self, monkeypatch):
        attempts: list[int] = []
        sleeps: list[float] = []

        def fake_post(url, json=None, headers=None, timeout=None):
            attempts.append(1)
            if len(attempts) <= 2:
                return _make_response(500, body={"error": "boom"})
            return _ok_response()

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        response = client.complete([{"role": "user", "content": "hi"}])
        assert response.text == "ok"
        assert len(attempts) == 3
        assert sleeps == [1.0, 2.0]

    def test_retries_503_honors_retry_after_header(self, monkeypatch):
        attempts: list[int] = []
        sleeps: list[float] = []

        def fake_post(url, json=None, headers=None, timeout=None):
            attempts.append(1)
            return _make_response(503, retry_after="5")

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])
        assert len(attempts) == 4
        assert sleeps == [5.0, 5.0, 5.0]

    def test_uses_exponential_backoff_on_503(self, monkeypatch):
        sleeps: list[float] = []

        def fake_post(url, json=None, headers=None, timeout=None):
            return _make_response(503)

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])
        assert sleeps == [1.0, 2.0, 4.0]

    def test_body_retry_delay_used_on_503_when_no_header(self, monkeypatch):
        sleeps: list[float] = []
        body = {
            "error": {
                "code": 503,
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "7s",
                    }
                ],
            }
        }

        def fake_post(url, json=None, headers=None, timeout=None):
            return _make_response(503, body=body)

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])
        assert sleeps == [7.0, 7.0, 7.0]

    @pytest.mark.parametrize("status", [400, 401, 403, 404])
    def test_never_retries_4xx(self, monkeypatch, status):
        attempts: list[int] = []
        sleeps: list[float] = []

        def fake_post(url, json=None, headers=None, timeout=None):
            attempts.append(1)
            return _make_response(status, body={"error": "nope"})

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])
        assert len(attempts) == 1
        assert sleeps == []

    def test_connection_error_retried_then_raises(self, monkeypatch):
        attempts: list[int] = []
        sleeps: list[float] = []

        def fail_post(url, json=None, headers=None, timeout=None):
            attempts.append(1)
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fail_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])
        assert len(attempts) == 4
        assert sleeps == [1.0, 2.0, 4.0]

    def test_read_timeout_retried_then_raises(self, monkeypatch):
        attempts: list[int] = []

        def fail_post(url, json=None, headers=None, timeout=None):
            attempts.append(1)
            raise httpx.ReadTimeout("read timed out")

        monkeypatch.setattr(time, "sleep", lambda seconds: None)
        monkeypatch.setattr(httpx, "post", fail_post)
        client = OpenAICompatClient(model="m", base_url="http://x/v1", api_key="k")
        with pytest.raises(LLMError):
            client.complete([{"role": "user", "content": "hi"}])
        assert len(attempts) == 4

    def test_rate_limit_error_never_leaks_api_key(self, monkeypatch):
        sleeps: list[float] = []

        def fake_post(url, json=None, headers=None, timeout=None):
            return _make_response(429, body=_quota_429_body())

        monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(httpx, "post", fake_post)
        client = OpenAICompatClient(
            model="m", base_url="http://x/v1", api_key="super-secret-key"
        )
        with pytest.raises(RateLimitError) as exc_info:
            client.complete([{"role": "user", "content": "hi"}])
        error = exc_info.value
        assert "super-secret-key" not in str(error)
        assert "super-secret-key" not in error.provider_body


def _ok_response() -> object:
    class OkResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "gpt-test",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            }

    return OkResp()
