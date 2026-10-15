# 02 — Folder Structure

This document explains every top-level folder and every significant subfolder in the
repository: purpose, important files, dependencies, and how each interacts with the rest of
the project. All counts were measured against the working tree.

---

## 2.1 Top-level layout

```text
Project2/
├── src/                 # Python backend (55 modules across 14 packages)
├── ui/                  # React + TypeScript frontend
├── eval/                # Offline research evaluation harness (Module 10)
├── evaluation/          # Generated benchmark reports + figures
├── results/             # Production-pipeline evaluation run artefacts
├── validation/          # Manual/expected test-case validation suite
├── data/                # Corpus, uploads, processed docs, hierarchy, provenance
├── scripts/             # Maintenance + benchmark entry-point scripts
├── deploy/              # Docker, nginx, env profiles, config loader
├── monitoring/          # Prometheus + Grafana stack
├── docs/                # Hand-written developer/product documentation
├── paper/               # IEEE LaTeX paper, poster, slides
├── tests/               # pytest backend test suite (65 files, 1033 test funcs)
├── logs/                # Runtime log sinks (app/api/llm/retrieval/error/audit)
├── demo_*.py            # Standalone feature demos (5 scripts)
├── .github/workflows/   # CI/CD (ci.yml, docker.yml)
├── docker-compose.yml   # Full-stack Compose definition
├── pyproject.toml       # Python project metadata, ruff/mypy/pytest config
├── requirements.txt     # Runtime + dev dependencies (unpinned)
└── requirements-lock.txt# Fully pinned reproducible environment
```

---

## 2.2 `src/` — Backend source

**Purpose:** entire Python application (configuration, ingestion, hierarchy, graph,
retrieval, embeddings, LLM/explainability, evaluation, API, middleware, monitoring).

**Dependencies:** third-party packages in `requirements.txt` / `pyproject.toml`; internal
packages import each other in the order M1→M7.

**Interaction:** `src/main.py` builds the FastAPI app; `src/api/` exposes HTTP routes;
`src/llm/service.py` wires the retrieval engine (`src/retrieval/`, `src/embeddings/`) to the
LLM and provenance store.

| Sub-package | Purpose | Key files | Depends on |
|-------------|---------|-----------|------------|
| `src/config/` | Settings + logging | `settings.py` (all env vars), `logging_config.py` | pydantic-settings, structlog |
| `src/utils/` | Constants, exceptions, helpers | `constants.py`, `exceptions.py`, `helpers.py` | stdlib |
| `src/api/` | FastAPI routers | `router.py`, `qa.py`, `documents.py`, `health.py` | `src/llm`, `src/ingestion`, `src/hierarchy` |
| `src/middleware/` | Security middleware | `security.py` | `src/config` |
| `src/monitoring/` | Metrics collection | `metrics.py`, `middleware.py` | stdlib |
| `src/models/` | Shared API schemas | `schemas.py` | pydantic |
| `src/ingestion/` | Document loaders/OCR/cleaning | `pipeline.py`, `identity.py`, `pruning.py`, sub-dirs | pdfplumber, PyMuPDF, python-docx, pytesseract |
| `src/hierarchy/` | Legal hierarchy parser | `parser.py`, `patterns.py`, `tree_builder.py`, `validators.py`, `models.py` | `src/models` |
| `src/knowledge_graph/` | Graph build/traversal | `importer.py`, `neo4j_driver.py`, `schema.py`, `traversal.py`, `citation_extractor.py`, `canonical.py` | neo4j, `src/hierarchy` |
| `src/embeddings/` | Vector store + models | `models.py`, `providers.py`, `store.py`, `indexer.py`, `retriever.py`, `service.py`, `benchmark.py` | qdrant-client, sentence-transformers, torch, transformers |
| `src/retrieval/` | HHGR retrieval | `query.py`, `intent.py`, `scorer.py`, `ranker.py`, `context.py`, `query_expansion.py`, `metrics.py` | `src/knowledge_graph`, `src/embeddings` |
| `src/llm/` | Explainability + generation | `llm.py`, `prompts.py`, `explanation.py`, `provenance.py`, `schemas.py`, `service.py` | httpx, `src/retrieval` |
| `src/evaluation/` | Production evaluation pipeline | `runner.py`, `dataset.py`, `corpus.py`, `pipeline.py`, `metrics/`, `calibration.py`, `report.py`, `plots.py`, `analysis.py`, `sections.py` | `src/llm`, matplotlib |
| `src/main.py` | App factory + lifespan | — | all of the above |

**Counts:** 90 `.py` files under `src/` (including `__init__.py`); 14 sub-packages plus
`main.py`.

### `src/ingestion/` sub-structure
- `loaders/` — `pdf_loader.py`, `docx_loader.py`, `txt_loader.py`.
- `ocr/` — `engine.py` (PaddleOCR primary, Tesseract fallback).
- `cleaning/` — `text_cleaner.py` (header/footer stripping, legal-numbering preservation).
- `detection/` — `language_detector.py` (script ranges + langdetect), `scanner_detector.py`.
- `metadata/` — `extractor.py` (file + PDF metadata).

### `src/evaluation/` sub-structure
- `metrics/` — `retrieval.py`, `generation.py`, `performance.py`, `aggregate.py`.
- `__main__.py` — CLI entry (`python -m src.evaluation`).

---

## 2.3 `ui/` — Frontend source

**Purpose:** React 18 single-page application ("explain-ui" v1.0.0) that is the primary user
interface. It calls the backend through a Vite dev proxy and renders answers, evidence,
knowledge graph, hierarchy, and provenance.

**Important files:**

| Path | Role |
|------|------|
| `ui/src/main.tsx` | React root entry |
| `ui/src/App.tsx` | Router, QueryClient, layout |
| `ui/src/api/client.ts` | Axios client + endpoint functions |
| `ui/src/types/index.ts` | Shared TypeScript interfaces |
| `ui/src/pages/` | Home, Explain, Upload, Provenance, Settings (5 pages) |
| `ui/src/components/` | 14 components (AnswerCard, ConfidenceGauge, EvidencePanel, HierarchyTree, KnowledgeGraph, ProvenancePanel, …) |
| `ui/src/hooks/` | 6 hooks (query, explain, provenance, recent questions, settings, dark mode) |
| `ui/src/utils/` | `format.ts`, `graph.ts`, `highlight.ts` (+ tests) |
| `ui/vite.config.ts` | Dev server + `/api` proxy + Vitest config |
| `ui/package.json` | Dependencies and scripts |

**Dependencies:** React Query (server state), axios, react-router-dom, Cytoscape, React Flow,
Recharts, framer-motion, Tailwind.

**Interaction:** consumes `POST /api/v1/query`, `POST /api/v1/explain`,
`GET /api/v1/provenance/{id}`, `POST /api/v1/documents/upload` (see `ui/src/api/client.ts`).

---

## 2.4 `eval/` — Offline research harness (Module 10)

**Purpose:** a dedicated, offline, deterministic benchmark harness that compares HHGR
against baseline retrieval systems and runs ablations, producing the artefacts in
`evaluation/` used by the paper.

**Important files:** `cli.py` (entry point), `harness.py` (benchmark loop, `BenchmarkOutput`),
`systems.py` (baseline system implementations), `ablation.py` (6 variants), `corpus.py`,
`dataset.py` (gold loader), `metrics/retrieval.py`, `metrics/explainability.py`,
`metrics/ragas.py`, `metrics/semantic.py`, `figures.py`, `reports.py`.

**Dependencies:** `src/` modules (retrieval, embeddings) plus pandas/matplotlib for reports.

**Interaction:** reads `data/eval/gold/*.json` and `data/eval/config/experiment.json`;
writes `evaluation/reports/` and `evaluation/figures/`.

---

## 2.5 `evaluation/` — Generated offline benchmark artefacts

**Purpose:** output location for the `eval/` harness.

**Contents:** `reports/` (`benchmark.json`, `benchmark.md`, `benchmark.pdf`, `retrieval_summary.csv`,
`explainability.csv`, `ragas.csv`, `ablation.csv`, `per_query.csv`); `figures/` (8 figure pairs
SVG+PNG plus `figures.json`); `embed_retrieval_comparison_v243*.json` (V2.4.3 embedding
provider comparison).

---

## 2.6 `results/` — Production pipeline evaluation runs

**Purpose:** outputs of `scripts/run_final_evaluation.py` (the production 50-question
benchmark).

**Contents:** top-level final run (`evaluation_report.md`, `raw_results.json`, `raw_results.csv`,
`reliability_diagram.png`, `corpus_audit.json`, `corpus_dedup_report.json`,
`task22_verification_audit.json`, `task23_relevance_debug.json`) and historical runs
`baseline/`, `phase4/`, `pre-parser-fix/`, `v30_50q/`, `v30/`.

---

## 2.7 `validation/` — Manual validation suite

**Purpose:** a 130-case manual/expectation validation suite that exercises the live
`/query` endpoint and checks confidence, verification status, and grounding-guard behaviour.

**Important files:** `manual_test_cases.md` (test-case catalogue), `expected_results.json`
(per-case expectations), `run_manual_validation.py`,
`task22_verification_audit.py`, `validation_report.md` (results).

---

## 2.8 `data/` — Corpus and runtime data

**Purpose:** persistent corpus and runtime artefacts.

| Sub-folder | Purpose | Count (measured) |
|-----------|---------|------------------|
| `data/hierarchy/` | Parsed hierarchy JSON per document (nested-set trees) | 295 files |
| `data/processed/` | Cleaned/processed document JSON (pages + metadata) | 1632 files |
| `data/provenance/` | Persisted provenance blobs keyed by id | 271 files |
| `data/uploads/` | Raw uploaded documents | 2 files |
| `data/embeddings/` | Gzipped embedding snapshots | (`snapshot_*.json.gz`) |
| `data/eval/gold/` | Gold evaluation datasets (5 domains + manifest) | 6 files |
| `data/eval/` | 50-question benchmark CSV + experiment config | CSV + config |

**Interaction:** `src/config/settings.py` points at `data/provenance`,
`data/embeddings`; `src/hierarchy/parser.py` writes `data/hierarchy`; `src/ingestion/pipeline.py`
writes `data/processed`.

---

## 2.9 `scripts/` — Entry-point scripts

**Purpose:** operational, maintenance, and benchmark entry points.

**Important files:** `run_final_evaluation.py` (production benchmark, 5 paper tables),
`benchmark_semantic_dense.py` (embedding provider comparison), `audit_corpus.py`,
`corpus_dedup_report.py`, `prune_stale_artifacts.py`, `rebuild_assets.py`, `capture_before_state.py`,
`trace_pipeline.py`, `check_graph*.py`, `cleanup_provenance.py`, `nvidia_smoke.py`,
`reproduce.sh` (one-command reproduction), `_bootstrap.py` (path setup).

**Interaction:** imports `src/` and `eval/`; writes to `results/`, `evaluation/`, `data/`.

---

## 2.10 `deploy/` — Deployment and configuration

**Purpose:** containerization, edge routing, environment profiles, and production
configuration validation.

| Path | Purpose |
|------|---------|
| `deploy/backend/Dockerfile` | Multi-stage Python image (deps wheel stage + runtime), non-root user |
| `deploy/frontend/Dockerfile` | Multi-stage Node build + nginx runtime |
| `deploy/nginx/nginx.conf` | Edge reverse proxy (API + SPA + docs) |
| `deploy/nginx/nginx-frontend.conf` | SPA nginx config (try_files, asset caching, /healthz) |
| `deploy/scripts/entrypoint.sh` | Container entrypoint; validates production secrets, runs uvicorn |
| `deploy/config/loader.py` | Env-file loader + `validate_production` |
| `deploy/config/cli.py` | `load` / `validate` CLI |
| `deploy/env/.env.development` | Tracked development template |
| `deploy/env/.env.development.local` | Git-ignored local secrets (contains live NVIDIA key — see notes) |
| `deploy/env/.env.docker` | Docker/Compose profile |
| `deploy/env/.env.production` | Production template |

**Interaction:** Compose uses `.env.docker`; `src/config/settings.py` reads the
`.env.development[.local]` pair; `entrypoint.sh` invokes `deploy.config.cli validate`.

---

## 2.11 `monitoring/` — Observability stack

**Purpose:** Prometheus metrics scraping and Grafana dashboards.

**Contents:** `monitoring/docker-compose.monitoring.yml` (prometheus, grafana,
node-exporter, neo4j-exporter), `monitoring/prometheus/prometheus.yml` (4 scrape targets),
`monitoring/grafana/` (datasource/dashboard provisioning + `explaintool_overview.json`).

**Interaction:** Prometheus scrapes the backend `/metrics` endpoint (served by
`src/monitoring/middleware.py`).

---

## 2.12 `docs/` — Developer/product documentation

**Purpose:** hand-written documentation. Key files: `ARCHITECTURE.md`, `API.md`,
`Dataset.md`, `Evaluation.md`, `VerificationFramework.md`, `Configuration.md`,
`DEPLOYMENT.md`, `DEVELOPER.md`, `PRODUCTION.md`, `architecture_diagrams.md`,
`GitHubActions.md`, `TROUBLESHOOTING.md`, plus Task19–Task23 investigation docs and
`docs/releases/v1.0.0.md`. This `docs/report/` folder is the generated technical package.

---

## 2.13 `paper/` — Publication package

**Purpose:** IEEE conference paper and presentation assets.

**Contents:** `paper.tex` (IEEEtran, title "Explaintool: …"), `abstract.tex`,
`introduction.tex`, `methodology.tex`, `experiments.tex`, `results.tex`, `future-work.tex`,
`references.bib` (RAG, GraphRAG, RAGAS, BGE-M3, BM25), plus `poster/poster.tex`,
`presentation/slides.tex`, `README.md`.

---

## 2.14 `tests/` — Backend test suite

**Purpose:** pytest suite covering every module (ingestion, hierarchy, graph, embeddings,
retrieval, LLM, API, evaluation, security, deploy config). 65 `test_*.py` files with
**1033 test functions** measured. Configured via `pyproject.toml:61-63`
(`asyncio_mode = "auto"`, `testpaths = ["tests"]`). Shared fixtures in `tests/conftest.py`
and `tests/qa_helpers.py`.

---

## 2.15 `logs/`

**Purpose:** runtime log sinks created and managed by `src/config/logging_config.py`:
`app.log` (aggregate), `api.log`, `llm.log`, `retrieval.log`, `error.log`, `audit.log`.

---

## 2.16 Repository root support files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata + ruff/mypy/pytest config |
| `requirements.txt` / `requirements-lock.txt` | Dependencies (unpinned / pinned) |
| `docker-compose.yml` / `docker-compose.override.yml` | Stack definition / dev overrides |
| `README.md` | Project README |
| `FINAL_REPORT.md`, `IMPLEMENTATION_REPORT_ISSUE*.md`, `INVESTIGATION_REPORT*.md`, `ROOT_CAUSE_STARTUP_HANG.md`, `final_report_llm_model_config.md`, `PROJECT_PROGRESS.md`, `PROJECT_STATS.md`, `ISSUE13_STORAGE_ARTIFACTS.md` | Engineering/issue reports |
| `CHANGELOG.md`, `RELEASE_*.md`, `FINAL_RELEASE_AUDIT.md`, `PUBLIC_RELEASE_REPORT.md` | Release management |
| `CITATION.cff`, `LICENSE` (MIT), `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md` | Project governance |
| `demo_*.py` (5 files) | Feature demonstration scripts |
| `.github/workflows/ci.yml`, `docker.yml` | CI/CD |
| `.env` (root) | Present but **not loaded** by the app (see `15_Configuration.md`) |

---

## 2.17 How folders interact (dependency direction)

```text
data/eval/gold ─┐
                ├─► eval/ ──────────► evaluation/ (reports, figures)
data/ ──────────┤
 (hierarchy)    └─► src/ ─┬─► src/api/ ◄── ui/ (HTTP)
                          ├─► src/retrieval/ ◄─ src/embeddings/
                          ├─► src/llm/
                          └─► src/evaluation/ ──► results/

deploy/ + monitoring/ + docker-compose.yml  ──► running stack (api, react, nginx, neo4j, qdrant, redis)
```

- `src/` is the centre of gravity; `eval/` and `src/evaluation/` consume it read-only.
- `ui/` and `eval/` are the only external clients; both reach `src/` through stable
  interfaces (HTTP and Python APIs respectively).
- `deploy/` and `monitoring/` operate the built artefacts and never import application code,
  except `deploy/config/loader.py` which is invoked by the container entrypoint.
