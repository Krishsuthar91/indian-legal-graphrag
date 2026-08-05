"""Tests for the QA API endpoints (Module 7)."""

import pytest

from src.api import qa as qa_api
from src.api.qa import QueryService
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
