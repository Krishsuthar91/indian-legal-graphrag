# Project Progress — Explainable Multilingual Hierarchical Graph-RAG with HHGR

Status tracker for the staged build. All modules are complete. Backend: 361 pytest
tests pass. Frontend (Module 8): 49 Vitest tests pass and `npm run build` succeeds.

## Module 1 — Foundation (DONE)
- FastAPI skeleton, pydantic settings, structlog logging, health endpoints,
  utilities (constants, exceptions, helpers).
- Tests: `tests/test_health.py`.

## Module 2 — Legal Document Ingestion (DONE)
- PDF / DOCX / TXT loaders, scanned-vs-digital detection, OCR (PaddleOCR with
  Tesseract fallback), language detection (en/hi/kn/ta/te/ml/bn), metadata
  extraction, text cleaning preserving legal numbering.
- Demos: `python demo_ingest.py`.

## Module 3 — Legal Hierarchy Parser (DONE)
- Numbering patterns, stack-based parent assignment, Nested Set Index
  (left/right/depth) via DFS, validators.
- Output: `data/hierarchy/*.json`. Demo: `python demo_hierarchy.py`.

## Module 4 — Knowledge Graph Builder (DONE)
- `InMemoryGraph` / `Neo4jDriver`, citation extraction (Sections, Rules,
  Articles, Orders, AIR/SCC cases), entity resolution, PART_OF / CITES /
  REFERENCES edges, traversal APIs, graph stats.
- Demo: `python demo_kg.py` (verified 11 nodes / 10 edges on sample).

## Module 5 — Hybrid Hierarchical Graph Retrieval (HHGR) (DONE)
- `parse_query` (multilingual tokenization), ancestor/descendant context +
  evidence propagation, four weighted signals (text / citation / hierarchy /
  structural), `retrieve()` ranker with signal breakdown and context path.
- Demo: `python demo_retrieval.py`.

## Module 6 — Embedding & Vector Retrieval Layer (DONE)
- Model registry (bge-m3 / LaBSE / MuRIL / IndicBERT) + deterministic provider,
  Qdrant store (4 collections, UUID5 ids, batched upserts, language filter),
  full/incremental/sync indexing, hybrid `VectorRetriever` (dense + graph +
  hierarchy fusion, default weights 0.40/0.35/0.25), latency benchmark.
- Demo: `python demo_embeddings.py`.

## Module 7 — Explainable LLM Answer Generation (DONE)
- LLM abstraction layer: OpenAI-compatible `httpx` client shared by OpenAI,
  Llama, Mistral, Qwen; deterministic offline mock client.
- Prompt builder: numbered evidence blocks, graph reasoning chain, hierarchy
  paths, cite-only-the-evidence instructions.
- Explainability engine: 6-step reasoning chain, hierarchy paths, source
  citations, counter-authority detection, confidence scoring, validity flags.
- Provenance store (in-memory + JSON) keyed by `provenance_id`.
- API endpoints:
  - `POST /api/v1/query` — answer with full provenance
  - `POST /api/v1/explain` — retrieval explanation without the LLM
  - `GET  /api/v1/provenance/{id}` — fetch a stored provenance record
- Tests: `tests/test_llm_clients.py`, `test_llm_prompts.py`,
  `test_llm_provenance.py`, `test_llm_explanation.py`, `test_llm_service.py`,
  `test_qa_api.py` (+ shared `tests/qa_helpers.py`).

## Module 8 — React Frontend & Explainability Dashboard (DONE)
- Vite + React 18 + TypeScript app in `ui/` consuming the Modules 1–7 API
  (`POST /api/v1/query`, `POST /api/v1/explain`, `GET /api/v1/provenance/{id}`).
- Pages: Home (search box, language selector, recent questions), Explain (query flow
  with "retrieval only" toggle), Provenance (id lookup), Settings (dark mode, defaults).
- Answer view: answer, model, response time, Recharts confidence gauge, validity badge,
  citations, provenance link.
- Evidence panel with section numbers, source paths, dense/graph/hierarchy score bars,
  and keyword highlighting.
- React Flow hierarchy tree (Document → Chapter → Section → Clause) with
  expand/collapse; Cytoscape.js knowledge graph (statutes/cases/citations, dashed
  counter-authority edges, hover tooltips, zoom/pan).
- Provenance panel: 6-step retrieval path, hybrid score breakdown, retrieval weights.
- React Query state, friendly errors with retry, responsive Tailwind layout, dark mode,
  lazy routes + vendor chunk splitting.
- Unit tests: 49 (Vitest + Testing Library), including mocked Cytoscape and jsdom setup.

## Module 9 — Production Deployment & Enterprise Infrastructure (DONE)
- **Containers** — multi-stage `deploy/backend/Dockerfile` (Python 3.11-slim,
  cached wheel layer, non-root user, container HEALTHCHECK) and
  `deploy/frontend/Dockerfile` (Node 20 build → nginx:alpine static serve);
  root `.dockerignore`.
- **Compose stack** — `docker-compose.yml` with six services (`api`, `react`,
  `nginx`, `neo4j`, `qdrant`, `redis`), per-service healthchecks, `depends_on`
  with `condition: service_healthy`, and named persistent volumes; dev
  `docker-compose.override.yml` (hot reload + direct ports).
- **Reverse proxy** — `deploy/nginx/nginx.conf` edge config (routes `/api/*`
  and `/docs` to `api:8000`, SPA to `react:80`, gzip, security headers, CSP,
  WebSocket upgrade, commented TLS block) + `deploy/nginx/nginx-frontend.conf`.
- **Configuration** — `deploy/env/.env.{production,development,docker}`
  profiles; `deploy/config/loader.py` env loader + fail-fast production secret
  validation (`LLM_API_KEY` for real providers, `API_KEY` when auth enabled,
  `APP_DEBUG=false`); `deploy/config/cli.py` (`load` / `validate` commands).
- **Security middleware** (`src/middleware/security.py`) — additive: optional
  `X-API-Key` auth (probes stay public), in-process per-IP rate limiting,
  request body size limit, and security headers.
- **Health probes** — additive `/api/v1/live`, `/api/v1/check/database`,
  `/api/v1/check/vector`, `/api/v1/check/llm` (all return `200` with a
  `ServiceHealth` body even on dependency failure).
- **Logging** — per-channel rotating file sinks (`app/api/llm/retrieval/
  error/audit.log`) with daily rotation via `LOG_ROTATION_ENABLED`.
- **Monitoring** — stdlib-only `/metrics` exporter (`src/monitoring/`, no
  `prometheus_client` dependency), `monitoring/prometheus/prometheus.yml`,
  Grafana provisioning (datasource + dashboard provider) and a prebuilt
  "Explaintool Overview" dashboard, plus an optional overlay
  `monitoring/docker-compose.monitoring.yml` (prometheus, grafana,
  node-exporter, neo4j-exporter).
- **CI** — `.github/workflows/ci.yml`: ruff lint, pytest, vitest + build,
  docker image builds, compose YAML validation, and deploy-config checks.
- **Docs** — `docs/DEPLOYMENT.md`, `docs/DEVELOPER.md`, `docs/PRODUCTION.md`,
  `docs/TROUBLESHOOTING.md`, `docs/ARCHITECTURE.md`.
- **Tests** — `tests/test_health_probes.py`, `tests/test_security_middleware.py`,
  `tests/test_deploy_config.py` (18 new tests; no existing tests modified).

## Verification
- Backend: `pytest` → 361 passed (343 pre-existing unchanged + 18 new Module 9).
- Frontend:
  - `cd ui && npm install` → clean
  - `npm run build` → type-check + production build OK (code-split chunks)
  - `npm test` → 49 passed
  - `npm run preview` → serves dist with HTTP 200 smoke test
- `ruff check .` → 78 pre-existing errors (Modules 7–9 code is clean; the
  baseline is unrelated to these modules).
- Deployment config: `deploy.config.cli validate` passes for development /
  docker profiles and fails fast for the production template (missing
  `LLM_API_KEY`).
- Compose: all three YAML files parse (services verified); nginx configs pass
  a brace-balance structural check.
- Environment limitation: Docker / nginx are not installed on this machine, so
  `docker compose up` and `nginx -t` could not be executed locally; validation
  is offline and CI is configured to perform the container builds.

## Next
- Module 10 — not started (per scope).
