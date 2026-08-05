"""Tests for the Module 9 security middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config.settings import settings
from src.middleware.security import SecurityMiddleware


def _build_app():
    app = FastAPI()

    @app.get("/api/v1/data")
    def data():
        return {"ok": True}

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    app.add_middleware(SecurityMiddleware)
    return app


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """Defaults matching the app baseline so patches are isolated per test."""
    monkeypatch.setattr(settings, "API_KEY_AUTH_ENABLED", False)
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 120)
    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_BYTES", 1048576)


def test_security_headers_present(monkeypatch):
    with TestClient(_build_app()) as client:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy")


def test_api_key_required_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY", "secret-token")
    with TestClient(_build_app()) as client:
        assert client.get("/api/v1/data").status_code == 401
        assert (
            client.get("/api/v1/data", headers={"x-api-key": "wrong"}).status_code
            == 401
        )
        resp = client.get("/api/v1/data", headers={"x-api-key": "secret-token"})
        assert resp.status_code == 200


def test_api_key_bypasses_public_probes(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY", "secret-token")
    with TestClient(_build_app()) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_rate_limit_blocks_excess_requests(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 3)
    with TestClient(_build_app()) as client:
        for _ in range(3):
            assert client.get("/api/v1/data").status_code == 200
        assert client.get("/api/v1/data").status_code == 429


def test_request_size_limit(monkeypatch):
    monkeypatch.setattr(settings, "REQUEST_MAX_BODY_BYTES", 16)
    with TestClient(_build_app()) as client:
        resp = client.post(
            "/api/v1/data",
            json={"payload": "x" * 100},
            headers={"content-length": "500"},
        )
        assert resp.status_code == 413
