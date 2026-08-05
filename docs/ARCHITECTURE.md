# Architecture Overview

End-to-end architecture of the Explaintool system (Modules 1–9).

## High-level flow

```
 Legal PDF/DOCX/TXT ──► Ingestion ──► Hierarchy Parser ──► Knowledge Graph
        (M2)              (M2)            (M3)                 (M4)
                                                              │  │
   Question ──► QueryParser ──► HHGR Retrieval ◄── Vector Store (M6)
    (M5)          (M5)              │                      │
                                    ▼                      │
                            Explainability (M7) ◄──────────┘
                                    │
                                    ▼
                     Cited Answer + Provenance ──► UI Dashboard (M8)

   Deployment / Monitoring / Security / CI ──────────────── (M9)
```

## Module 9 — Production & Enterprise Infrastructure

Module 9 is purely additive: it deploys, secures, monitors, and tests the
Modules 1–8 application without touching backend logic or frontend features.

### Containers

| Service | Image / build                 | Role                                     |
|---------|-------------------------------|------------------------------------------|
| `nginx` | `nginx:1.27-alpine` + mounted conf | Edge reverse proxy, TLS, gzip, headers |
| `react` | `deploy/frontend/Dockerfile`  | Static SPA bundle (internal nginx)       |
| `api`   | `deploy/backend/Dockerfile`   | FastAPI backend (uvicorn, 2 workers)     |
| `neo4j` | `neo4j:5-community`           | Knowledge graph                          |
| `qdrant`| `qdrant/qdrant:latest`        | Vector store                             |
| `redis` | `redis:7-alpine`              | Cache / future rate-limit backing        |

All six define healthchecks; `api` starts only after the datastores are
healthy, `nginx` after `api` + `react`. Data lives in named volumes.

### Deployment artifacts (`deploy/`)

```
deploy/
├── backend/Dockerfile        # multi-stage Python 3.11 image
├── frontend/Dockerfile       # Node build → nginx runtime
├── nginx/nginx.conf          # edge reverse proxy (TLS-ready)
├── nginx/nginx-frontend.conf # static SPA serving
├── env/.env.{production,development,docker}
├── config/loader.py          # env profile loader + validation
├── config/cli.py             # CLI: load / validate
├── scripts/entrypoint.sh     # container entrypoint (fail-fast)
└── security/                 # reserved for security policy files
```

### Security middleware (`src/middleware/security.py`)

- API-key auth (`X-API-Key`) on protected routes; probes stay public
- In-process per-IP rate limiting (60s sliding window)
- Request body size limit
- Security headers (CSP, X-Frame-Options, nosniff, Referrer-Policy)

### Health probes (`src/api/health.py`)

| Endpoint | Meaning |
|----------|---------|
| `/health` | process alive (pre-existing) |
| `/ready` | readiness (pre-existing) |
| `/live` | liveness (new) |
| `/check/database` | Neo4j probe (new) |
| `/check/vector` | Qdrant probe (new) |
| `/check/llm` | LLM probe (new) |

### Monitoring (`monitoring/`)

- `prometheus/prometheus.yml` scrapes api, qdrant, neo4j-exporter,
  node-exporter
- `grafana/provisioning/*` auto-configures the Prometheus datasource and
  dashboard provider
- `grafana/dashboards/explaintool_overview.json` ships an "Overview" panel
  (latency, request rate, memory, storage activity)
- `docker-compose.monitoring.yml` is the optional overlay stack
- The backend exposes a stdlib-only `/metrics` collector
  (`src/monitoring/`): no `prometheus_client` dependency

### Logging (`src/config/logging_config.py`)

Per-channel rotating file sinks (`app/api/llm/retrieval/error/audit.log`),
selected by logger-name prefix; rotation enabled via
`LOG_ROTATION_ENABLED`.

### CI (`/.github/workflows/ci.yml`)

Runs on push/PR to `main`/`develop`:

1. **Backend lint** — `ruff check .`
2. **Backend tests** — `pytest -q` (uploads coverage artifact)
3. **Frontend tests** — `npm ci && npm test && npm run build` (uploads `dist`)
4. **Docker build** — validates compose YAML, builds api + react images
5. **Deploy config** — asserts production validation fails fast without
   secrets, dev profile passes

## Data flow details

### Ingestion → Graph (Modules 2–4)

1. Loader parses PDF/DOCX/TXT; scanner detector + OCR handle scanned pages;
   language detection tags the document; cleaner preserves legal numbering.
2. Hierarchy parser builds a Document → Chapter → Section → Clause tree with
   a nested-set index.
3. Graph builder emits nodes/edges (PART_OF, CITES, REFERENCES), resolves
   duplicate legal entities, exposes traversal + stats.

### Retrieval (Modules 5–6)

HHGR fuses four weighted signals (text, citation, hierarchy, structural);
the vector layer adds multilingual dense search over Qdrant (4 collections)
and fuses dense / graph / hierarchy with configurable weights.

### Answer generation (Module 7)

The explainability engine builds evidence blocks with citations, runs a
6-step reasoning chain, detects counter-authority, scores confidence, flags
validity, and persists provenance for every answer.

### Frontend (Module 8)

React 18 + TypeScript SPA: query flow, provenance browser, hierarchy viewer
(React Flow), knowledge-graph explorer (Cytoscape), confidence gauge, dark
mode — all backed by React Query over the `/api/v1` endpoints.

## Extending the system

- **New LLM provider** — add a class in `src/llm/llm.py` and register it in
  `get_llm_client()`; update env validation in `deploy/config/loader.py`.
- **New route** — add a router under `src/api/` and include it in
  `src/api/router.py`.
- **New metric** — use `src/monitoring/metrics.py` (inc/set/observe) and add
  a panel in the Grafana dashboard JSON.
- **New dependency service** — add a service to `docker-compose.yml` with a
  healthcheck, a `deploy/env` variable, and a `/api/v1/check/<name>` probe.
