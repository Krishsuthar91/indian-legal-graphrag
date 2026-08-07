"""LLM abstraction layer — OpenAI-compatible, Llama, Mistral, Qwen.

All real providers speak the OpenAI ``/chat/completions`` protocol, so they share
one ``httpx``-based implementation. A deterministic ``MockLLMClient`` keeps tests
and the default demo fully offline.
"""

from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.config.logging_config import get_logger
from src.config.settings import settings

log = get_logger("llm")

# Retry policy.
# 429 (quota/rate limit) is NEVER retried — it fails immediately. Only truly
# transient failures are retried: 5xx status codes, connection errors, and
# read/connect timeouts.
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 16.0
_TRANSIENT_STATUS_CODES = {500, 502, 503, 504}


class LLMError(Exception):
    """Raised when an LLM backend cannot be reached or returns an unusable response."""


class RateLimitError(LLMError):
    """Raised when the provider throttles or quota-exhausts a request.

    Carries the provider's response details so the API layer can return a clean
    HTTP 429 instead of a generic 500 traceback.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        retry_after: float | None = None,
        provider_body: str = "",
        quota_exhausted: bool = False,
        provider: str = "",
        model: str = "",
        url: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.provider_body = provider_body
        self.quota_exhausted = quota_exhausted
        self.provider = provider
        self.model = model
        self.url = url


def _backoff(attempt: int) -> float:
    """Exponential backoff for a retry attempt (0-indexed)."""
    return min(_BACKOFF_BASE_SECONDS * (2**attempt), _MAX_BACKOFF_SECONDS)


def _is_quota_exhausted(body: str) -> bool:
    """Heuristic: does a provider 429 body indicate quota exhaustion?"""
    lowered = body.lower()
    return any(
        token in lowered
        for token in ("resource_exhausted", "quota", "billing", "limit: 0")
    )


def _is_transient_network_error(exc: BaseException) -> bool:
    """Connection errors and read/connect timeouts are transient."""
    return isinstance(exc, httpx.TransportError)


def _mask_key(key: str) -> str:
    """Mask an API key so logs never leak it (show shape only)."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def _masked_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return headers safe to log: Authorization is masked, everything else kept."""
    return {
        header: (_mask_key(value) if header.lower() == "authorization" else value)
        for header, value in headers.items()
    }


def _safe_text(resp: Any, limit: int = 4000) -> str:
    """Best-effort body text from an httpx response or test fake."""
    try:
        text = resp.text
        if isinstance(text, str):
            return text[:limit]
    except Exception:
        pass
    try:
        body = resp.json()
        if isinstance(body, (dict, list)):
            return json.dumps(body, ensure_ascii=False)[:limit]
    except Exception:
        pass
    return ""


def _parse_retry_after_seconds(resp: Any) -> float | None:
    """Read a retry delay from the Retry-After header or the body's retryDelay."""
    headers = getattr(resp, "headers", None)
    if headers is not None:
        for name in ("Retry-After", "retry-after"):
            value = headers.get(name)
            if value:
                try:
                    return max(0.0, float(value))
                except (TypeError, ValueError):
                    return None
    match = re.search(r'retryDelay"?\s*:\s*"?(\d+(?:\.\d+)?)s', _safe_text(resp, 8000))
    if match:
        return max(0.0, float(match.group(1)))
    match = re.search(
        r"retry (?:in|after) (\d+(?:\.\d+)?)s", _safe_text(resp, 8000), re.IGNORECASE
    )
    if match:
        return max(0.0, float(match.group(1)))
    return None


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
        log.info(
            "llm.request_start",
            url=self._chat_url,
            model=self.model,
            request_headers=_masked_headers(headers),
            request_body=payload,
        )

        resp: Any = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = httpx.post(
                    self._chat_url,
                    json=payload,
                    headers=headers,
                    timeout=httpx.Timeout(
                        self.timeout,
                        connect=min(10.0, self.timeout),
                        read=self.timeout,
                        write=self.timeout,
                        pool=self.timeout,
                    ),
                )
            except httpx.HTTPError as exc:
                if attempt < _MAX_RETRIES and _is_transient_network_error(exc):
                    wait = _backoff(attempt)
                    log.warning(
                        "llm.retry_scheduled",
                        url=self._chat_url,
                        model=self.model,
                        attempt=attempt + 1,
                        wait_seconds=wait,
                        error=str(exc),
                    )
                    time.sleep(wait)
                    continue
                log.error(
                    "llm.request_failed",
                    url=self._chat_url,
                    model=self.model,
                    attempt=attempt,
                    error=str(exc),
                )
                raise LLMError(f"LLM request failed: {exc}") from exc

            status_code = getattr(resp, "status_code", None)
            if status_code == 429:
                self._log_rate_limit(resp)
                raise self._build_rate_limit_error(resp)

            if status_code in _TRANSIENT_STATUS_CODES and attempt < _MAX_RETRIES:
                retry_after = _parse_retry_after_seconds(resp)
                wait = retry_after if retry_after is not None else _backoff(attempt)
                log.error(
                    "llm.transient_status",
                    url=self._chat_url,
                    model=self.model,
                    attempt=attempt,
                    status_code=status_code,
                    retry_after=retry_after,
                    response_headers=(
                        dict(resp.headers) if hasattr(resp, "headers") else None
                    ),
                    response_body=_safe_text(resp)[:2000],
                )
                log.info(
                    "llm.retry_scheduled",
                    url=self._chat_url,
                    model=self.model,
                    attempt=attempt + 1,
                    wait_seconds=wait,
                )
                time.sleep(wait)
                continue
            break

        try:
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            status_code = getattr(resp, "status_code", None)
            log.error(
                "llm.request_failed",
                url=self._chat_url,
                model=self.model,
                status_code=status_code,
                response_headers=(
                    dict(resp.headers) if hasattr(resp, "headers") else None
                ),
                response_body=_safe_text(resp),
                error=str(exc),
            )
            raise LLMError(f"LLM request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            log.error(
                "llm.request_failed",
                url=self._chat_url,
                model=self.model,
                error=str(exc),
            )
            raise LLMError(f"LLM request failed: {exc}") from exc

        log.info(
            "llm.request_complete",
            url=self._chat_url,
            model=self.model,
            status_code=getattr(resp, "status_code", None),
        )

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

    def _log_rate_limit(self, resp: Any) -> None:
        """Log a 429 without sleeping or retrying (quota errors fail fast)."""
        body = _safe_text(resp)
        log.error(
            "llm.rate_limited",
            url=self._chat_url,
            model=self.model,
            attempt=0,
            retried=False,
            max_retries=_MAX_RETRIES,
            status_code=getattr(resp, "status_code", None),
            retry_after=_parse_retry_after_seconds(resp),
            response_headers=(
                dict(resp.headers) if hasattr(resp, "headers") else None
            ),
            response_body=body[:2000],
            quota_exhausted=_is_quota_exhausted(body),
        )

    def _build_rate_limit_error(self, resp: Any) -> RateLimitError:
        """Build a RateLimitError from a 429 response, preserving provider details."""
        body = _safe_text(resp)
        quota_exhausted = _is_quota_exhausted(body)
        retry_after = _parse_retry_after_seconds(resp)
        return RateLimitError(
            (
                f"LLM rate limit / quota exceeded (HTTP "
                f"{getattr(resp, 'status_code', 429)}). "
                f"quota_exhausted={quota_exhausted} retry_after={retry_after} "
                f"provider_body={body[:500]!r}"
            ),
            status_code=getattr(resp, "status_code", None) or 429,
            retry_after=retry_after,
            provider_body=body,
            quota_exhausted=quota_exhausted,
            provider=self.name,
            model=self.model,
            url=self._chat_url,
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


class GeminiClient(OpenAICompatClient):
    """Google Gemini via its OpenAI-compatible endpoint.

    Uses ``Authorization: Bearer <GEMINI_API_KEY>`` against the Google-hosted
    ``/v1beta/openai/chat/completions`` endpoint. Set ``LLM_PROVIDER=gemini``
    with ``GEMINI_API_KEY`` (and optionally ``GEMINI_MODEL``).
    """

    name = "gemini"
    default_model = "gemini-2.0-flash"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> None:
        api_key = api_key or settings.GEMINI_API_KEY
        base_url = base_url or settings.GEMINI_BASE_URL or None
        model = model or settings.GEMINI_MODEL or None
        super().__init__(
            model=model, base_url=base_url, api_key=api_key, timeout=timeout, **kwargs
        )


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
    elif selected == "gemini":
        cls = GeminiClient
    else:
        raise LLMError(f"Unknown LLM provider: {selected!r}")

    if issubclass(cls, OpenAICompatClient):
        client: LLMClient = cls(
            model=model, base_url=base_url, api_key=api_key, timeout=timeout
        )
    else:
        client = cls(model=model)

    log.info(
        "llm.client_configured",
        provider=selected,
        model=client.model,
        base_url=getattr(client, "base_url", None),
        timeout=timeout,
        has_api_key=bool(getattr(client, "api_key", "")),
        api_key_length=len(getattr(client, "api_key", "") or ""),
    )
    return client


def log_llm_configuration() -> None:
    """Log the resolved LLM configuration at startup (never the key itself)."""
    gemini_key = settings.GEMINI_API_KEY
    llm_key = settings.LLM_API_KEY
    log.info(
        "llm.configuration",
        provider=settings.LLM_PROVIDER,
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        gemini_model=settings.GEMINI_MODEL,
        gemini_base_url=settings.GEMINI_BASE_URL,
        gemini_key_configured=bool(gemini_key),
        gemini_key_length=len(gemini_key),
        gemini_key_masked=_mask_key(gemini_key),
        llm_key_configured=bool(llm_key),
        llm_key_length=len(llm_key),
    )
