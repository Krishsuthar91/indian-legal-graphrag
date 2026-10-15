# Configuration

All runtime configuration flows through a single pydantic-settings model in `src/config/settings.py`. There are **no** scattered `os.getenv` calls — every setting is a typed field with a default.

## Where settings come from

The loader resolves values in this order (later wins):

| Priority | Source |
|----------|--------|
| 1 (lowest) | Field defaults in `src/config/settings.py` |
| 2 | `deploy/env/.env.development` — tracked template, committed to the repo |
| 3 | `deploy/env/.env.development.local` — git-ignored, **for real secrets/overrides** |
| 4 (highest) | OS environment variables / docker-compose `environment:` |

The loader always reads the `deploy/env/` files (regardless of machine), which keeps local runs, Docker and CI consistent. In production, secrets are injected via docker-compose `env_file`/`environment`, which override the template.

## Env templates

| File | Purpose |
|------|---------|
| `deploy/env/.env.development` | Development defaults (tracked, safe placeholders) |
| `deploy/env/.env.development.local` | Your local overrides + real `NVIDIA_API_KEY` (git-ignored via `.env.*.local`) |
| `deploy/env/.env.docker` | Copied into the backend image at build time; overridden at runtime by compose |
| `deploy/env/.env.production` | Production template — copy to a real `.env.production` with real secrets, never commit |

Never commit real keys. The tracked templates keep empty/placeholder secrets and `.gitignore` + `.dockerignore` exclude local env files.

## LLM configuration (provider priority)

```
LLM_PROVIDER=nvidia
```

- **Model name:** `NVIDIA_MODEL` is the **single source of truth** for the NVIDIA model (default `nvidia/nemotron-3-super-120b-a12b`). The generic `LLM_MODEL` never overrides it.
- **API key / base URL:** generic `LLM_API_KEY` / `LLM_BASE_URL` **win** over `NVIDIA_API_KEY` / `NVIDIA_BASE_URL` when both are set. Falls back to the `NVIDIA_*` pair for the NVIDIA provider.
- **Providers:** `mock` (offline, deterministic), `nvidia` (production), plus `openai | llama | mistral | qwen | gemini` (all OpenAI-compatible).
- **Retired model ids** are rejected by NVIDIA NIM with `HTTP 410` (e.g. `meta/llama-3.3-70b-instruct` EOL 2026-08-26). See `final_report_llm_model_config.md` for the precedence breakdown.

## Key setting groups

| Group | Example settings |
|-------|------------------|
| Application | `APP_ENV`, `APP_DEBUG`, `APP_HOST`, `APP_PORT`, `APP_LOG_LEVEL` |
| LLM / NVIDIA | `LLM_PROVIDER`, `NVIDIA_MODEL`, `NVIDIA_API_KEY`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT_SECONDS` |
| Datastores | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `REDIS_URL`, `QDRANT_URL`, `QDRANT_IN_MEMORY`, `QDRANT_TIMEOUT_SECONDS` |
| QA / Retrieval | `QA_TOP_K`, `QA_CONFIDENCE_THRESHOLD`, `QA_INDEX_IN_MEMORY`, `QA_QUERY_EXPANSION_ENABLED`, `QA_REQUEST_TIMEOUT_SECONDS` |
| Security | `API_KEY_AUTH_ENABLED`, `API_KEY`, `RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_MINUTE`, `REQUEST_MAX_BODY_BYTES` |
| CORS | `CORS_ORIGINS` |
| Logging | `LOG_ROTATION_ENABLED`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT` |

> The QA request deadline (`QA_REQUEST_TIMEOUT_SECONDS`) also caps LLM retries, so a `/query` request never exceeds the deadline even on transient LLM failures.

## Changing a setting

1. Add the typed field to `src/config/settings.py` (with default + docstring).
2. Add the line to the relevant `deploy/env/.env.*` template.
3. Use `settings.<FIELD>` where you need the value — never `os.getenv`.