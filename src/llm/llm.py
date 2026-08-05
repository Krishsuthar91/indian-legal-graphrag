"""LLM abstraction layer — OpenAI-compatible, Llama, Mistral, Qwen.

All real providers speak the OpenAI ``/chat/completions`` protocol, so they share
one ``httpx``-based implementation. A deterministic ``MockLLMClient`` keeps tests
and the default demo fully offline.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.config.logging_config import get_logger
from src.config.settings import settings

log = get_logger("llm")


class LLMError(Exception):
    """Raised when an LLM backend cannot be reached or returns an unusable response."""


@dataclass
class LLMResponse:
    """Normalized response from any LLM backend."""

    text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""


class LLMClient(ABC):
    """Base interface shared by all chat-completion clients."""

    name: str = "base"
    default_model: str = ""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        self.model = model or self.default_model

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """Send chat messages and return the assistant reply."""

    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """Convenience wrapper for a single system + user turn."""
        return self.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )


class OpenAICompatClient(LLMClient):
    """Generic client for any OpenAI-compatible ``/chat/completions`` endpoint.

    Works with the OpenAI API, Mistral API, and locally served models (vLLM,
    llama.cpp, Ollama, Transformers) that expose the same protocol.
    """

    name = "openai"
    default_model = "gpt-4o-mini"
    default_base_url = "https://api.openai.com/v1"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, **kwargs)
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "") or settings.LLM_API_KEY
        self.timeout = timeout

    @property
    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = httpx.post(
                self._chat_url, json=payload, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.error("llm.request_failed", url=self._chat_url, error=str(exc))
            raise LLMError(f"LLM request failed: {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"]
            finish_reason = data["choices"][0].get("finish_reason", "")
        except (KeyError, IndexError, TypeError) as exc:
            log.error("llm.bad_response", url=self._chat_url, body=data)
            raise LLMError("LLM response did not contain a completion") from exc

        return LLMResponse(
            text=text or "",
            model=data.get("model", self.model),
            usage=data.get("usage") or {},
            finish_reason=finish_reason or "",
        )


class LlamaClient(OpenAICompatClient):
    """Local Llama (llama.cpp / Ollama / vLLM) via its OpenAI-compatible API."""

    name = "llama"
    default_model = "llama-3.1-8b-instruct"
    default_base_url = "http://localhost:8080/v1"


class MistralClient(OpenAICompatClient):
    """Mistral Cloud (or self-hosted) via its OpenAI-compatible API."""

    name = "mistral"
    default_model = "mistral-small-latest"
    default_base_url = "https://api.mistral.ai/v1"


class QwenClient(OpenAICompatClient):
    """Qwen (Transformers / vLLM) via its OpenAI-compatible API."""

    name = "qwen"
    default_model = "Qwen/Qwen2.5-7B-Instruct"
    default_base_url = "http://localhost:8000/v1"


class MockLLMClient(LLMClient):
    """Deterministic offline client for tests and the default demo (no network).

    Echoes the query and lists the sources referenced in the prompt so generated
    answers remain deterministic and inspectable.
    """

    name = "mock"
    default_model = "mock-llm"

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> LLMResponse:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        sources = _extract_source_numbers(user)
        citation_note = (
            f"Sources cited: {', '.join(f'[{n}]' for n in sources)}."
            if sources
            else "No sources cited."
        )
        query_line = user.split("QUESTION:", 1)[-1].splitlines()[0].strip()
        text = (
            f"[mock] Based on the retrieved legal evidence, the answer addresses: "
            f"{query_line}. {citation_note}"
        )
        return LLMResponse(
            text=text[: max(1, max_tokens)],
            model=self.model,
            usage={"prompt_tokens": len(user) // 4, "completion_tokens": len(text) // 4},
            finish_reason="stop",
        )


def _extract_source_numbers(user_prompt: str) -> list[str]:
    """Pull ``[SOURCE n]`` markers out of a formatted prompt (for the mock client)."""
    numbers: list[str] = []
    for line in user_prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("[SOURCE"):
            num = stripped[len("[SOURCE"):].strip()
            num = num.split("]", 1)[0].strip()
            if num.isdigit() and num not in numbers:
                numbers.append(num)
    return numbers


def get_llm_client(
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
) -> LLMClient:
    """Factory returning the client for the requested provider.

    Falls back to environment settings, then to the offline mock client.
    """
    selected = (provider or settings.LLM_PROVIDER or "mock").lower().strip()
    model = model or settings.LLM_MODEL or None
    base_url = base_url or settings.LLM_BASE_URL or None
    api_key = api_key or settings.LLM_API_KEY or None
    timeout = timeout or settings.LLM_TIMEOUT_SECONDS

    cls: type[LLMClient]
    if selected in ("mock", "", "offline"):
        cls = MockLLMClient
    elif selected == "openai":
        cls = OpenAICompatClient
    elif selected == "llama":
        cls = LlamaClient
    elif selected == "mistral":
        cls = MistralClient
    elif selected == "qwen":
        cls = QwenClient
    else:
        raise LLMError(f"Unknown LLM provider: {selected!r}")

    if issubclass(cls, OpenAICompatClient):
        return cls(model=model, base_url=base_url, api_key=api_key, timeout=timeout)
    return cls(model=model)
