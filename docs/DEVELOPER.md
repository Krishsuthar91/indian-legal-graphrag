# Developer Guide

Guide for developers working on the Explaintool codebase (Modules 1–9).

## Repository layout

```
explaintool/
├── src/                      # Python backend (FastAPI)
│   ├── main.py               # App entry point + middleware wiring
│   ├── config/               # settings.py, logging_config.py
│   ├── api/                  # health.py, qa.py, router.py
│   ├── middleware/           # security.py (Module 9)
│   ├── monitoring/           # metrics.py, middleware.py (Module 9)
│   ├── ingestion/            # loaders, OCR, detection, metadata, cleaning
│   ├── hierarchy/            # patterns, tree builder, validators, parser
│   ├── knowledge_graph/      # Neo4jDriver + InMemoryGraph
│   ├── retrieval/            # HHGR query / context / scorer / ranker
│   ├── embeddings/           # providers, store, indexer, retriever
│   └── llm/                  # abstraction, prompts, provenance, service
├── ui/                       # React 18 + TypeScript dashboard (Module 8)
├── tests/                    # pytest suite (backend)
├── deploy/                   # Module 9 — Docker, nginx, env, config loader
├── monitoring/               # Module 9 — Prometheus + Grafana overlay
├── docs/                     # Module 9 — operational documentation
├── .github/workflows/ci.yml  # Module 9 — CI pipeline
├── docker-compose.yml        # Module 9 — six-service stack
└── pyproject.toml
```

## Local setup

### Backend (Python 3.11+)

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn src.main:app --reload          # http://localhost:8000
pytest                                 # 360+ backend tests
ruff check .                           # lint (repo has pre-existing fixes)
```

### Frontend (Node 20+)

```bash
cd ui
npm install
npm run dev                            # http://localhost:5173 (proxies /api)
npm test                               # 49 Vitest tests
npm run build                          # type-check + production bundle
```

## Running demos

```bash
python demo_ingest.py       # Module 2 — ingest sample PDF
python demo_hierarchy.py    # Module 3 — parse hierarchy
python demo_kg.py           # Module 4 — build knowledge graph
python demo_retrieval.py    # Module 5 — HHGR retrieval
python demo_embeddings.py   # Module 6 — vector + hybrid retrieval
```

## Configuration

Settings live in `src/config/settings.py` (pydantic `BaseSettings`), loaded
from `.env` or process environment. See `.env.example`. For deployment the
profiles in `deploy/env/` override local `.env`.

New Module 9 settings:

| Setting                  | Default   | Purpose                                  |
|--------------------------|-----------|------------------------------------------|
| `API_KEY_AUTH_ENABLED`   | `false`   | Require `X-API-Key` on protected routes  |
| `API_KEY`                | `""`      | Shared API key when auth is enabled      |
| `RATE_LIMIT_ENABLED`     | `false`   | In-process per-IP rate limiting          |
| `RATE_LIMIT_PER_MINUTE`  | `120`     | Requests per IP per 60s window           |
| `REQUEST_MAX_BODY_BYTES` | `1048576` | Max accepted request body                |
| `LOG_ROTATION_ENABLED`   | `false`   | Daily rotated log files                  |
| `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` | — | (reserved rotation knobs)        |

## Logging

`src/config/logging_config.py` (structlog) writes:

- `logs/app.log` — everything
- `logs/api.log`, `logs/llm.log`, `logs/retrieval.log`, `logs/error.log`,
  `logs/audit.log` — per-channel files selected by logger name prefix
  (e.g. `get_logger("llm")` → `logs/llm.log`)

Enable rotation with `LOG_ROTATION_ENABLED=true` (midnight rotation,
`backupCount` retained files).

## Metrics

The backend exposes Prometheus metrics at `/metrics` (stdlib collector —
no `prometheus_client` dependency):

- `http_requests_total` (counter, method/path/status labels)
- `http_request_duration_ms` (observations + `_count`/`_sum`)
- `process_rss_bytes`, `process_uptime_seconds`

Neo4j/Qdrant metrics are scraped via their own exporters (see
`monitoring/docker-compose.monitoring.yml` and `docs/DEPLOYMENT.md`).

## Testing module 9 additions

```bash
pytest tests/test_health_probes.py          # new health endpoints
pytest tests/test_security_middleware.py    # API key / rate limit / size / headers
pytest tests/test_deploy_config.py          # env loader + secret validation
```

## Code conventions

- Keep backend logic untouched: Module 9 only adds routes/middleware/docs.
- Additive changes only — existing endpoints and their responses are stable.
- Match ruff rules (`pyproject.toml`: E, F, I, N, W, UP), 100-col lines.
- No comments unless they carry meaning; match surrounding style.
