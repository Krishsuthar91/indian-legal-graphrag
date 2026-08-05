"""Tests for the LLM abstraction layer (Module 7)."""

import httpx
import pytest

from src.llm.llm import (
    LlamaClient,
    LLMError,
    LLMResponse,
    MistralClient,
    MockLLMClient,
    OpenAICompatClient,
    QwenClient,
    get_llm_client,
)


class TestFactory:
    def test_default_is_mock(self):
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
