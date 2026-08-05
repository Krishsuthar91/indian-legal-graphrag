"""Tests for the Module 9 deployment config loader / secret validation."""

from __future__ import annotations

import os

import pytest

from deploy.config.loader import (
    ENV_DIR,
    load_environment,
    validate_production,
)


@pytest.fixture()
def clean_env(monkeypatch):
    """Isolate process environment mutations from load_environment."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def test_env_files_exist():
    assert (ENV_DIR / ".env.production").exists()
    assert (ENV_DIR / ".env.development").exists()
    assert (ENV_DIR / ".env.docker").exists()


def test_load_development_profile(clean_env):
    values = load_environment("development")
    assert values["APP_ENV"] == "development"
    assert values["LLM_PROVIDER"] == "mock"


def test_env_vars_override_file(clean_env, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    values = load_environment("development")
    assert values["LLM_PROVIDER"] == "openai"


def test_validate_development_passes(clean_env):
    values = load_environment("development")
    assert validate_production(values) == []


def test_validate_production_fails_without_llm_key(clean_env):
    values = load_environment("production")
    errors = validate_production(values)
    assert any("LLM_API_KEY" in e for e in errors)


def test_validate_requires_api_key_when_auth_enabled(clean_env):
    values = load_environment("development")
    values["API_KEY_AUTH_ENABLED"] = "true"
    values["API_KEY"] = ""
    errors = validate_production(values)
    assert any("API_KEY" in e for e in errors)


def test_validate_rejects_debug_in_production(clean_env):
    values = load_environment("production")
    values["APP_DEBUG"] = "true"
    errors = validate_production(values)
    assert any("APP_DEBUG" in e for e in errors)


def test_offline_llm_provider_does_not_require_key(clean_env):
    values = load_environment("development")
    values["LLM_PROVIDER"] = "mock"
    values["APP_ENV"] = "production"
    errors = validate_production(values)
    assert not any("LLM_API_KEY" in e for e in errors)
