# Explainable Multilingual Hierarchical Graph-RAG with HHGR

A production-grade research project for Indian Legal Document Intelligence using Hybrid Hierarchical Graph Retrieval.

## Module 1 — Foundation

This module provides the project skeleton, configuration, logging, FastAPI server, utilities, and tests.

## Module 2 — Legal Document Ingestion

Loads PDF / DOCX / TXT documents, detects scanned vs digital PDFs, OCRs scanned pages
(PaddleOCR with Tesseract fallback), detects the document language (en/hi/kn/ta/te/ml/bn),
extracts metadata, and cleans text while preserving legal numbering.

## Module 3 — Legal Hierarchy Parser

Parses legal documents into a hierarchical tree (Document → Chapter → Section → Clause,
plus Explanation, Illustration, Proviso, Schedule, etc.) using 20+ numbering patterns,
assigns parents with a stack-based algorithm, and builds a Nested Set Index (left/right/depth)
via DFS for fast subtree queries.

## Module 4 — Knowledge Graph Builder

Builds a graph from the parsed hierarchy using `InMemoryGraph` (Neo4j-compatible API) or the
real `Neo4jDriver`. Extracts legal citations (Sections, Rules, Articles, Orders, AIR/SCC case
citations), resolves duplicate entities, creates PART_OF / CITES / REFERENCES edges, and
provides traversal APIs (parents, children, citation chains, shortest paths) and graph stats.

## Module 5 — Hybrid Hierarchical Graph Retrieval (HHGR)

Hybrid retrieval over the knowledge graph that combines four weighted signals:
- **text** — lexical overlap between query keywords and node title/text (multilingual tokenization)
- **citation** — query legal references (e.g. "Section 4") matching node numbering or text
- **hierarchy** — evidence propagated from seed matches to ancestors and descendants along PART_OF edges
- **structural** — node importance (degree + subtree size), normalized per query

`retrieve(graph, query, top_k)` returns ranked `RetrievalResult`s with a per-signal score
breakdown, the ancestor context path, and matched keywords.

## Module 6 — Embedding & Vector Retrieval Layer

Semantic retrieval over Qdrant fused with the Module 5 graph signals:
- **embedding providers** — bge-m3 / LaBSE / MuRIL / IndicBERT specs in a registry; a
  deterministic (dependency-free) provider keeps tests and demos fast; sentence-transformers /
  transformers providers load the real multilingual models
- **Qdrant store** — 4 collections (documents / chapters / sections / clauses), deterministic
  UUID5 point ids, batched upserts, language-filtered `query_points` search with cosine
  normalized to [0, 1], delete / count / indexed-payload introspection, in-memory mode
- **indexer** — full indexing from hierarchy JSON or graph, incremental indexing that re-embeds
  only new / text-changed nodes (md5 `text_hash`), and `sync_graph` that deletes stale points
- **vector retriever** — `dense_search` (multilingual), `graph_retrieval` (Module 5 HHGR),
  `hierarchy_retrieval` (evidence propagation from dense seeds), and `hybrid_retrieve` that fuses
  all three signals with configurable weights (default dense .40 / graph .35 / hierarchy .25)
- **benchmark** — per-query latency (mean / p50 / p95) for embedding, dense search, and hybrid

## Module 7 — Explainable LLM Answer Generation

Generates cited, explainable answers over the HHGR + vector retrieval layers:
- **LLM abstraction** — one OpenAI-compatible `httpx` client shared by OpenAI, Llama,
  Mistral, and Qwen (plus an offline `mock` client so tests and demos need no network/keys)
- **prompt builder** — numbered evidence blocks (`[SOURCE 1]`, ...), graph reasoning
  chain, hierarchy paths, and strict cite-only-the-evidence instructions
- **explainability engine** — retrieval provenance per stage, a 6-step graph reasoning
  chain (parse → dense → graph → hierarchy → fusion → verification), hierarchy paths,
  source citations, counter-authority detection (overruled/superseded/repealed/void),
  confidence scoring (base score + keyword coverage + sufficiency + citation bonus), and
  validity flags (supported / has_conflicts / cites_counter_authority / insufficient)
- **provenance store** — every answer is persisted (in-memory + JSON) keyed by a
  `provenance_id` for full auditability
- **API** — `POST /api/v1/query` (answer + provenance), `POST /api/v1/explain`
  (retrieval explanation without the LLM), `GET /api/v1/provenance/{id}`

## Module 8 — React Frontend & Explainability Dashboard

A `ui/` Vite + React 18 + TypeScript dashboard over the Modules 1–7 API. Backend modules
are untouched.- **Pages** — Home (search box, language selector, recent questions), Explain (full query
  flow with a "retrieval only" `/explain` toggle), Provenance (look up any
  `/provenance/{id}`), Settings (dark mode, defaults, API info)
- **Answer view** — answer text, model name, response time, confidence gauge (Recharts),
  validity badge, source citations, provenance link
- **Evidence panel** — supporting evidence with section numbers, case citations, source
  document path, dense/graph/hierarchy score bars, and keyword highlighting
- **Hierarchy viewer** — React Flow (`@xyflow/react`) tree of
  Document → Chapter → Section → Clause with expand/collapse
- **Knowledge graph** — Cytoscape.js with statutes/cases/citations node shapes and
  colors, dashed counter-authority edges, hover tooltips, zoom/pan, and re-layout
- **Provenance panel** — 6-step retrieval path, hybrid score breakdown per evidence node,
  and retrieval weights (dense / graph / hierarchy)
- **Robustness** — React Query state management, friendly error messages with retry,
  responsive Tailwind layout (desktop / tablet / mobile), dark mode (persisted), unit
  tests (49), lazy-loaded routes + vendor chunk splitting

## Module 9 — Production Deployment & Enterprise Infrastructure

Production-readiness for the Modules 1–8 application (additive only — no backend
logic or frontend features changed).

- **Containers** — multi-stage `deploy/backend/Dockerfile` (Python 3.11-slim, cached
  dependency layer, non-root user, healthcheck) and `deploy/frontend/Dockerfile`
  (Node 20 build → nginx:alpine)
- **Compose** — six-service `docker-compose.yml` (`api`, `react`, `nginx`, `neo4j`,
  `qdrant`, `redis`) with healthchecks, `depends_on` gating, and named volumes;
  dev override `docker-compose.override.yml`
- **Edge nginx** — `deploy/nginx/nginx.conf` reverse proxy (API + SPA + docs),
  gzip, security headers, WebSocket upgrade, TLS-ready
- **Configuration** — `deploy/env/.env.{production,development,docker}` profiles +
  fail-fast secret validation (`python -m deploy.config.cli validate --env production`)
- **Security** — `src/middleware/security.py`: API-key auth, per-IP rate limiting,
  request-size limits, security headers (all opt-in via settings)
- **Health probes** — additive `/api/v1/live`, `/check/database`, `/check/vector`,
  `/check/llm` returning structured `ServiceHealth`
- **Monitoring** — stdlib-only `/metrics` endpoint, `monitoring/` Prometheus +
  Grafana overlay (prebuilt "Overview" dashboard)
- **Logging** — per-channel rotating log files (`logs/app|api|llm|retrieval|error|audit.log`)
- **CI** — `.github/workflows/ci.yml` (ruff, pytest, vitest+build, docker builds)
- **Docs** — `docs/DEPLOYMENT.md`, `docs/DEVELOPER.md`, `docs/PRODUCTION.md`,
  `docs/TROUBLESHOOTING.md`, `docs/ARCHITECTURE.md`

Deploy with `docker compose up --build -d` and visit http://localhost.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment
cp .env.example .env

# Run the backend server
uvicorn src.main:app --reload

# Run backend tests
pytest

# Run the end-to-end demos (in order)
python demo_ingest.py       # Module 2 — ingest a sample PDF
python demo_hierarchy.py    # Module 3 — parse a document into a hierarchy
python demo_kg.py           # Module 4 — build the knowledge graph
python demo_retrieval.py    # Module 5 — hybrid hierarchical graph retrieval
python demo_embeddings.py   # Module 6 — vector store + hybrid dense/graph/hierarchy retrieval
```

### Frontend (Module 8)

```bash
cd ui
npm install
npm run dev      # http://localhost:5173 (proxies /api to http://localhost:8000)
npm run build    # type-check (tsc -b) + production build to ui/dist
npm test         # 49 Vitest + Testing Library unit tests
npm run preview  # serve the production build
```

The embedding demo runs on the deterministic provider (no downloads). For real multilingual
vectors, install `sentence-transformers` / `torch` and set `EMBEDDING_MODEL=BAAI/bge-m3` (or
LaBSE / MuRIL / IndicBERT) in `.env`. Qdrant runs via Docker (`docker-compose up`).

## Docker

```bash
docker-compose up --build          # production-style six-service stack (http://localhost)
# dev override: docker-compose -f docker-compose.yml -f docker-compose.override.yml up
# validate secrets: python -m deploy.config.cli validate --env production
```

## Project Structure

```
explaintool/
├── src/
│   ├── main.py              # FastAPI entry point (+ security & metrics middleware)
│   ├── middleware/
│   │   └── security.py      # Module 9 — API key / rate limit / size / headers
│   ├── monitoring/
│   │   ├── metrics.py       # Module 9 — stdlib Prometheus collector
│   │   └── middleware.py    # Module 9 — /metrics endpoint
│   ├── config/
│   │   ├── settings.py      # Pydantic settings
│   │   └── logging_config.py  # rotating per-channel file logging
│   ├── api/
│   │   ├── router.py        # API router
│   │   ├── health.py        # Health + dependency probes (/live, /check/*)
│   │   └── qa.py            # QA endpoints (/query, /explain, /provenance/{id})
│   ├── models/
│   │   └── schemas.py       # Pydantic models (HealthResponse, ServiceHealth, ...)
│   ├── ingestion/
│   ├── hierarchy/
│   ├── knowledge_graph/
│   ├── retrieval/
│   ├── embeddings/
│   ├── llm/
│   └── utils/
├── ui/                        # Module 8 — React frontend (Vite + TS)
├── deploy/                    # Module 9 — Docker, nginx, env profiles, config loader
│   ├── backend/Dockerfile
│   ├── frontend/Dockerfile
│   ├── nginx/nginx.conf + nginx-frontend.conf
│   ├── env/.env.{production,development,docker}
│   ├── config/{loader.py,cli.py}
│   └── scripts/entrypoint.sh
├── monitoring/                # Module 9 — Prometheus + Grafana overlay
├── docs/                      # Module 9 — DEPLOYMENT / DEVELOPER / PRODUCTION / TROUBLESHOOTING / ARCHITECTURE
├── .github/workflows/ci.yml   # Module 9 — CI pipeline
├── tests/                     # 361 backend tests (343 pre-existing + 18 Module 9)
├── logs/
├── data/
├── pyproject.toml
├── requirements.txt
├── docker-compose.yml         # six-service production stack
└── docker-compose.override.yml
```
