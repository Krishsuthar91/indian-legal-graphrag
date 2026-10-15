# 03 — Backend Architecture

The backend is a single **FastAPI** application (`explaintool` 1.0.0) written in Python
≥3.11. This document describes the application factory, lifespan, middleware stack, routing,
dependency wiring, configuration, logging, error handling, and the service layer.

Primary source: `src/main.py`; supporting modules in `src/api/`, `src/config/`,
`src/middleware/`, `src/monitoring/`, `src/llm/service.py`.

---

## 3.1 Application entry point

`src/main.py` creates the ASGI application:

- Reads `settings` from `src/config/settings.py:15` (pydantic-settings singleton).
- Configures structured logging via `setup_logging()` (`src/config/logging_config.py`).
- Builds the app with `create_app()` (`src/main.py`), attaches the lifespan context, the
  middleware stack, and the routers.
- Exposes module-level `app` for `uvicorn src.main:app`.

### FastAPI metadata
- Title/version/description come from `settings` (`src/config/settings.py`).
- Interactive docs at `/docs` (Swagger UI) and `/redoc`.
- OpenAPI schema at `/openapi.json`.

### Lifespan
A single `lifespan` async context manager runs startup and shutdown:

**Startup**
1. Log startup; initialize logging sinks.
2. Initialize the **explanation service** (LLM + retrieval engine + provenance store) and
   store it on `app.state` so routers can reuse it.
3. Probe optional dependencies (Neo4j, Qdrant, LLM) lazily — an unavailable dependency is
   reported by `GET /api/v1/health` and the `check/*` endpoints rather than crashing boot.

**Shutdown**
1. Close HTTP clients (LLM `httpx` client) and the Neo4j driver if open.
2. Flush logs.

Lazy initialization is deliberate: the service starts even when Neo4j/Qdrant/LLM are
unreachable, which is important for tests and for the readiness/liveness probes.

---

## 3.2 Layered architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ Transport        src/main.py · src/api/*                      │
│                  root route · health · qa · documents         │
├──────────────────────────────────────────────────────────────┤
│ Middleware       Metrics → Security → CORS                    │
├──────────────────────────────────────────────────────────────┤
│ Service          src/llm/service.py (ExplanationService)      │
│                  orchestrates retrieval + LLM + provenance    │
├──────────────────────────────────────────────────────────────┤
│ Domain           src/retrieval/ · src/embeddings/ ·           │
│                  src/knowledge_graph/ · src/hierarchy/ ·      │
│                  src/ingestion/ · src/llm/explanation.py      │
├──────────────────────────────────────────────────────────────┤
│ Infra            src/config/ · src/monitoring/ · src/utils/   │
└──────────────────────────────────────────────────────────────┘
```

Routers depend on the service layer; the service layer orchestrates the domain modules;
domain modules depend only on infrastructure and third-party clients. This keeps HTTP
concerns out of the algorithms, which is what makes the `eval/` harness able to call the
domain layer directly.

---

## 3.3 Middleware stack

Middleware is registered in `src/main.py` and executes in this order (outermost first):

1. **MetricsMiddleware** (`src/monitoring/middleware.py`) — times every request, records
   `http_requests_total` and `http_request_duration_seconds` counters/histograms, and exposes
   `GET /metrics` in Prometheus text format for the `monitoring/` stack.
2. **SecurityHeadersMiddleware** (`src/middleware/security.py`) — adds `X-Content-Type-Options`,
   `X-Frame-Options`, `Referrer-Policy`, and related hardening headers; enforces body-size
   limits for uploads.
3. **CORSMiddleware** — origins are driven by `settings.cors_origins`
   (`src/config/settings.py`, default includes `http://localhost:5173` and `:3000`).

---

## 3.4 Routers and endpoints

Routers are mounted under the versioned prefix `/api/v1` (`src/api/router.py`). The root
route `/` is registered directly on the app (`src/main.py:191`), so the full surface is
**11 REST endpoints** (10 under `/api/v1` + root) plus the operational `/metrics`.

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/` | `src/main.py:191` | Service banner + links to docs/health |
| GET | `/api/v1/health` | `src/api/health.py` | Aggregate health (version, components) |
| GET | `/api/v1/ready` | `src/api/health.py` | Readiness probe |
| GET | `/api/v1/live` | `src/api/health.py` | Liveness probe |
| GET | `/api/v1/check/database` | `src/api/health.py` | Neo4j connectivity |
| GET | `/api/v1/check/vector` | `src/api/health.py` | Qdrant connectivity |
| GET | `/api/v1/check/llm` | `src/api/health.py` | LLM provider reachability |
| POST | `/api/v1/query` | `src/api/qa.py` | Full QA: retrieve + LLM answer + provenance |
| POST | `/api/v1/explain` | `src/api/qa.py` | Explainability only (no LLM call) |
| GET | `/api/v1/provenance/{provenance_id}` | `src/api/qa.py` | Re-fetch persisted provenance |
| POST | `/api/v1/documents/upload` | `src/api/documents.py:165` | Upload + index a document |

See `12_API_Documentation.md` for request/response schemas and examples.

### `qa` router (`src/api/qa.py`)
- `POST /query` accepts `QueryRequest` and returns `QueryResponse`. It calls
  `ExplanationService.answer(...)`, which retrieves evidence, verifies it, calls the LLM, and
  persists provenance. On success the response carries the answer, evidence, confidence,
  verification badge, and a provenance id.
- `POST /explain` accepts `ExplainRequest` and returns `ExplanationResponse` **without** an
  LLM call — it returns retrieval + reasoning + explanations synchronously (used by the
  "explain only" and settings flows).
- `GET /provenance/{id}` loads a persisted provenance record from
  `src/llm/provenance.py` (backed by `data/provenance/`).

### `documents` router (`src/api/documents.py`)
- `POST /documents/upload` accepts `multipart/form-data`, validates type/size, saves to
  `data/uploads/`, then runs `ingest_upload(...)` (ingestion → hierarchy → graph → vector
  index) and returns a document id and indexing summary.

### `health` router (`src/api/health.py`)
- `HealthResponse` (aggregate) and `ServiceHealth` (per-component) schemas.
- `/health` reports overall status and version; `/ready` and `/live` are Kubernetes-style
  probes; `check/*` perform active dependency checks with short timeouts.

---

## 3.5 Service layer — `ExplanationService`

`src/llm/service.py` is the orchestration hub. Responsibilities:

1. **Query understanding** — delegate to `src/retrieval/query.py` (parsing, act detection,
   expansion).
2. **Retrieval** — call the HHGR retriever (`src/embeddings/retriever.py`) which internally
   fuses dense + graph (4-signal HHGR) + hierarchy.
3. **Verification** — run the verification framework (sufficiency, relevance, claim
   entailment, confidence calibration, badge) before generation (`src/llm/explanation.py`).
4. **Grounding guard** — check the generated answer against retrieved evidence; when evidence
   is insufficient or contradicted, return a grounded refusal/flag instead of a hallucination
   (`src/llm/service.py:275-328`).
5. **Generation** — call the configured LLM (`src/llm/llm.py`) with a legal prompt
   (`src/llm/prompts.py`).
6. **Provenance** — assemble and persist the full record (`src/llm/provenance.py`).

The service is instantiated once at startup and shared via `app.state`.

---

## 3.6 Configuration

`src/config/settings.py` defines a single `Settings` (pydantic-settings) instance.

- Sources (precedence): process environment → `.env.development.local` (git-ignored secrets)
  → `.env.development` → defaults.
- **Important:** the root `.env` file is **not** loaded by the application; configuration is
  read from `deploy/env/`-style profiles. See `15_Configuration.md` and
  `docs/Configuration.md`.
- Grouped settings include: app (name/version/env/log level), API (host/port/CORS),
  Neo4j (URI/user/password/database), Qdrant (host/port/collections), embeddings
  (provider/model/allow-deterministic-fallback), LLM (provider, NVIDIA NIM key/base URL/model,
  timeouts, retries), retrieval (weights, top-k, thresholds), storage (paths), and
  provenance (retention). Full table in `15_Configuration.md`.

---

## 3.7 Logging

`src/config/logging_config.py` configures a dual-sink logger:

- **Console** — human-readable, level from `LOG_LEVEL`.
- **File** — rotating JSON structured logs under `logs/` (`app.log`, `api.log`, `llm.log`,
  `retrieval.log`, `error.log`, `audit.log`), using `structlog`/`python-json-logger`.

Every request is logged with a correlation id; LLM and retrieval stages add structured
fields (latency, tokens, signal scores) that feed the audit log.

---

## 3.8 Error handling

- Domain exceptions (`src/utils/exceptions.py`) are raised with stable codes and mapped to
  HTTP responses.
- Validation errors return FastAPI's 422 shape; unexpected errors return a generic 500
  without leaking internals (the security middleware and exception handlers cooperate).
- The LLM client (`src/llm/llm.py`) implements retry/backoff and returns typed failures so
  the service can degrade gracefully (e.g. `no_answer` with a reason).

---

## 3.9 Concurrency and performance

- `httpx.AsyncClient` is used for LLM calls; retrieval and embedding calls are async where
  the clients support it.
- Heavy CPU work (OCR, embeddings warm-up) is isolated so it cannot block the event loop for
  long; the embedding provider optionally offloads to GPU when available.
- Deterministic mode (`EMBEDDING_FORCE_DETERMINISTIC` / `force_deterministic`) is available
  for reproducible tests and offline evaluation, bypassing model downloads.

---

## 3.10 Backend dependency graph (simplified)

```text
main.py
 ├─ api/router.py ─┬─ api/health.py ── config/settings.py
 │                 ├─ api/qa.py ── llm/service.py
 │                 └─ api/documents.py ── ingestion/pipeline.py ── hierarchy/parser.py
 │                                                              └─ knowledge_graph/importer.py
 ├─ llm/service.py ─┬─ embeddings/retriever.py ── embeddings/{store,models,providers}.py
 │                  ├─ llm/explanation.py ── retrieval/* ── knowledge_graph/traversal.py
 │                  ├─ llm/llm.py ── config/settings.py
 │                  └─ llm/provenance.py ── data/provenance/
 ├─ monitoring/middleware.py
 ├─ middleware/security.py
 └─ config/logging_config.py
```

---

## 3.11 Key backend files quick reference

| File | Responsibility |
|------|----------------|
| `src/main.py` | App factory, lifespan, middleware, root route |
| `src/api/router.py` | Aggregates `health`/`qa`/`documents` routers under `/api/v1` |
| `src/api/qa.py` | `/query`, `/explain`, `/provenance/{id}` |
| `src/api/documents.py` | `/documents/upload`, `ingest_upload` |
| `src/api/health.py` | `/health`, `/ready`, `/live`, `/check/*` |
| `src/config/settings.py` | All configuration + defaults |
| `src/config/logging_config.py` | Structured dual-sink logging |
| `src/middleware/security.py` | Security headers, size limits |
| `src/monitoring/middleware.py` | Prometheus metrics + `/metrics` |
| `src/llm/service.py` | End-to-end orchestration |
| `src/llm/llm.py` | LLM provider clients (NVIDIA NIM, Gemini, mock) |
| `src/llm/explanation.py` | Explainability engine (largest module) |
| `src/llm/provenance.py` | Provenance assembly + persistence |
| `src/llm/schemas.py` | LLM/explanation Pydantic schemas |
| `src/models/schemas.py` | Shared API schemas |
