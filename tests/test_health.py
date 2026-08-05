"""Tests for health and root endpoints."""


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "service" in data
    assert data["service"] == "explaintool"


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_readiness(client):
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    assert resp.json()["ready"] == "ok"
