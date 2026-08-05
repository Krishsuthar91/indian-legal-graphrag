"""Environment file loader and production secret validation.

These helpers are used by deployment tooling (entrypoint scripts, CI) and by
the application itself when running in production mode to fail fast if
required secrets are missing.

Usage:
    from deploy.config.loader import load_environment
    load_environment("production")
"""

from __future__ import annotations

import os
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent.parent
ENV_DIR = DEPLOY_DIR / "env"

ENV_FILES: dict[str, str] = {
    "production": "production",
    "development": "development",
    "docker": "docker",
    "test": "development",
}

# Secrets that MUST be present when a real LLM provider is configured.
CONDITIONAL_SECRETS = {
    "LLM_PROVIDER": "LLM_API_KEY",
    "API_KEY_AUTH_ENABLED": "API_KEY",
}

# Providers that work without a secret (offline / local).
_OFFLINE_PROVIDERS = {"", "mock", "offline"}

DEFAULTS: dict[str, str] = {
    "APP_ENV": "development",
    "APP_NAME": "explaintool",
    "APP_LOG_LEVEL": "INFO",
    "NEO4J_URI": "bolt://localhost:7687",
    "REDIS_URL": "redis://localhost:6379/0",
    "QDRANT_URL": "http://localhost:6333",
}


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_environment(env: str = "production") -> dict[str, str]:
    """Load the matching .env.{profile} into the process environment.

    Returns a dict of the resolved variables. Real values already set in the
    environment (e.g. injected by Docker / CI) take precedence over the file.
    """
    profile = ENV_FILES.get(env, env)
    env_file = ENV_DIR / f".env.{profile}"

    values: dict[str, str] = dict(DEFAULTS)
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key:
                values[key] = val.strip().strip('"').strip("'")

    for key in list(values):
        if key in os.environ and os.environ[key]:
            values[key] = os.environ[key]

    for key, val in values.items():
        os.environ.setdefault(key, val)

    return values


def validate_production(env: dict[str, str] | None = None) -> list[str]:
    """Return a list of missing/invalid secrets for production startup.

    Empty list means the environment is safe to start. Never raise inside
    health probes — the entrypoint decides whether to fail fast.
    """
    values = env if env is not None else load_environment("production")
    errors: list[str] = []

    for flag, secret in CONDITIONAL_SECRETS.items():
        if flag == "LLM_PROVIDER":
            provider = (values.get("LLM_PROVIDER") or "mock").strip().lower()
            if provider in _OFFLINE_PROVIDERS:
                continue
        elif not _truthy(values.get(flag, "false")):
            continue
        if not values.get(secret):
            errors.append(
                f"{flag} is enabled but required secret {secret} is empty"
            )

    if values.get("APP_ENV") == "production" and _truthy(
        values.get("APP_DEBUG", "false")
    ):
        errors.append("APP_DEBUG must be false in production")

    return errors
