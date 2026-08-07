"""Tests for the QA API endpoints (Module 7)."""

import time

import pytest

from src.api import qa as qa_api
from src.api.qa import QueryService
from src.config.settings import settings
from tests.qa_helpers import build_service


@pytest.fixture()
def service() -> QueryService:
    return build_service()


@pytest.fixture()
def patch_service(monkeypatch, service):
    monkeypatch.setattr(qa_api, "service_factory", lambda: service)


def test_post_query(client, patch_service):
    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provenance_id"]
    assert data["answer"]
    assert data["model"] == "mock-llm"
    assert data["query"] == "performance of contracts"
    assert data["evidence"]
    assert data["confidence"]["score"] > 0
    assert data["validity"]["supported"] is True
    assert data["citations"]
    assert data["reasoning_chain"]
    assert data["duration_ms"] >= 0


def test_post_query_accepts_options(client, patch_service):
    resp = client.post(
        "/api/v1/query",
        json={"query": "performance of contracts", "top_k": 3, "max_tokens": 100},
    )
    assert resp.status_code == 200
    assert len(resp.json()["evidence"]) <= 3


def test_post_query_empty_returns_422(client, patch_service):
    resp = client.post("/api/v1/query", json={"query": ""})
    assert resp.status_code == 422


def test_post_query_invalid_top_k_returns_422(client, patch_service):
    resp = client.post("/api/v1/query", json={"query": "x", "top_k": 0})
    assert resp.status_code == 422


def test_post_explain(client, patch_service):
    resp = client.post("/api/v1/explain", json={"query": "performance of contracts"})
    assert resp.status_code == 200
    data = resp.json()
    assert "provenance_id" not in data
    assert "answer" not in data
    assert data["evidence"]
    assert data["hierarchy_paths"]
    assert data["retrieval"]["keywords"]


def test_provenance_roundtrip(client, patch_service):
    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    provenance_id = resp.json()["provenance_id"]
    get_resp = client.get(f"/api/v1/provenance/{provenance_id}")
    assert get_resp.status_code == 200
    record = get_resp.json()
    assert record["provenance_id"] == provenance_id
    assert record["answer"] == resp.json()["answer"]


def test_provenance_missing_returns_404(client, patch_service):
    resp = client.get("/api/v1/provenance/doesnotexist")
    assert resp.status_code == 404


def test_explain_empty_returns_422(client, patch_service):
    resp = client.post("/api/v1/explain", json={"query": " "})
    assert resp.status_code == 422


def test_post_query_returns_with_mock_provider_without_uploads(client, patch_service):
    """Requirement: /query answers offline with the mock LLM — no upload needed."""
    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "mock-llm"
    assert data["answer"]
    assert data["provenance_id"]


def test_first_query_default_service_mock_no_uploads(client, monkeypatch):
    """First-ever /query triggers the lazy default-service build and still answers."""
    from src.llm import service as svc
    from tests.qa_helpers import build_fast_corpus

    monkeypatch.setattr(svc, "build_default_corpus", build_fast_corpus)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    for name in ("_default_service", "_default_graph", "_default_store", "_default_embedding"):
        monkeypatch.setattr(svc, name, None)
    monkeypatch.setattr(qa_api, "service_factory", svc.get_default_service)

    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "mock-llm"
    assert data["answer"]
    assert data["provenance_id"]


def test_post_query_llm_quota_returns_clean_429(client, monkeypatch):
    """Requirement: a quota-exhausted LLM yields HTTP 429 JSON, not a 500 traceback."""
    import time

    from src.llm.llm import RateLimitError

    class QuotaExhausted:
        def answer(self, **kwargs):
            raise RateLimitError(
                "LLM rate limit / quota exceeded",
                status_code=429,
                quota_exhausted=True,
                retry_after=7.0,
                provider="gemini",
                provider_body=(
                    '{"error":{"status":"RESOURCE_EXHAUSTED",'
                    '"message":"You exceeded your current quota, limit: 0"}}'
                ),
            )

    monkeypatch.setattr(qa_api, "service_factory", lambda: QuotaExhausted())
    start = time.perf_counter()
    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    elapsed = time.perf_counter() - start
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"] == "Gemini quota exceeded"
    assert body["provider"] == "gemini"
    assert body["retry_after"] == 7.0
    assert "RESOURCE_EXHAUSTED" in body["details"]
    assert "Traceback" not in resp.text
    assert elapsed < 2


def test_post_query_llm_rate_limit_returns_429_without_retry_after(client, monkeypatch):
    """Non-quota throttling also returns 429, omitting retry_after when unknown."""
    from src.llm.llm import RateLimitError

    class RateLimited:
        def answer(self, **kwargs):
            raise RateLimitError(
                "LLM rate limit exceeded",
                status_code=429,
                retry_after=None,
                provider="gemini",
                provider_body='{"error":{"status":"RATE_LIMITED","message":"slow down"}}',
            )

    monkeypatch.setattr(qa_api, "service_factory", lambda: RateLimited())
    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"] == "Gemini rate limited"
    assert body["provider"] == "gemini"
    assert "retry_after" not in body


def test_post_query_llm_unavailable_returns_500_within_bound(client, monkeypatch):
    class Broken:
        def answer(self, **kwargs):
            raise RuntimeError("Gemini unavailable")

    monkeypatch.setattr(qa_api, "service_factory", lambda: Broken())
    start = time.perf_counter()
    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    elapsed = time.perf_counter() - start

    assert resp.status_code == 500
    assert "Gemini unavailable" in resp.json()["detail"]
    assert "Traceback" in resp.json()["detail"]
    assert elapsed < 5


def test_post_query_hang_returns_500_within_bound(client, monkeypatch):
    class Slow:
        def answer(self, **kwargs):
            time.sleep(5)
            raise AssertionError("must have timed out")

    monkeypatch.setattr(settings, "QA_REQUEST_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(qa_api, "service_factory", lambda: Slow())
    start = time.perf_counter()
    resp = client.post("/api/v1/query", json={"query": "performance of contracts"})
    elapsed = time.perf_counter() - start

    assert resp.status_code == 500
    assert "timed out" in resp.json()["detail"].lower()
    assert elapsed < 5
