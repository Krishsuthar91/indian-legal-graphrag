"""Tests for the Module 9 health probe endpoints."""


def test_liveness(client):
    resp = client.get("/api/v1/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_check_llm_with_mock_provider(client):
    resp = client.get("/api/v1/check/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "llm"
    assert "status" in data
    assert "latency_ms" in data


def test_check_database_reports_failure_when_unreachable(client):
    resp = client.get("/api/v1/check/database")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "database"
    assert data["ok"] is False
    assert data["status"] == "failed"


def test_check_vector_reports_failure_when_unreachable(client):
    resp = client.get("/api/v1/check/vector")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "vector"
    assert data["ok"] is False
    assert data["status"] == "failed"


def test_check_endpoints_are_public(client):
    for path in (
        "/api/v1/check/database",
        "/api/v1/check/vector",
        "/api/v1/check/llm",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
