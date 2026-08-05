# Project Progress — Explainable Multilingual Hierarchical Graph-RAG with HHGR

Status tracker for the staged build. All modules are complete. Backend: 447 pytest
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

## Module 10 — Research Evaluation & Publication Package (DONE)
- **Gold dataset** — `eval/dataset.py` + `data/eval/gold/*.json` (34 items, 5
  domains): 10 grounded Contract Act items (node ids `n_0001..n_0010`, doc
  `0940d367554383c5`) + 6 domain-probes each for BNS / BNSS / BSA / SC
  judgments (scored via citation-string → node matching). Schema validation,
  `manifest.json`, and `load_all_gold`.
- **Retrieval metrics** — `eval/metrics/retrieval.py`: Recall@K, Precision@K,
  Hit Rate@K, MRR, MAP, NDCG@K (binary or graded), `latency_stats`
  (mean/p50/p95 ms, throughput QPS), `aggregate_metrics`, `summarize`.
- **Explainability metrics** — `eval/metrics/explainability.py`: citation
  accuracy (label+numbering anchors), hierarchy correctness (true ancestor
  chain), graph-path accuracy, provenance completeness (0.5 structural + 0.5
  gold recall), evidence coverage (answer-token coverage), counter-authority
  precision/recall/F1.
- **RAGAS + semantic** — `eval/metrics/ragas.py`: offline deterministic
  faithfulness, answer relevancy, context recall/precision, answer correctness
  (0.5 token F1 + 0.5 cosine); optional native `ragas_context()` when the
  package is installed. `eval/metrics/semantic.py`: cached deterministic
  embedder (dim=64) for cosine relevance.
- **Systems** — `eval/systems.py`: `RetrievalSystem` protocol; HHGR (with
  MockLLM-backed `QueryService`), dense-only, BM25 (k1=1.5, b=0.75, stopword
  filter), graph-only (Module 5 ranker), naive RAG (dense + mock LLM, no
  provenance); `RankedHit` canonicalized; `build_systems()`.
- **Ablation** — `eval/ablation.py`: six arms (full / no_graph / no_hierarchy /
  no_dense / no_multilingual / no_explainability); `run_ablation`,
  `build_ablation_rows`.
- **Reports** — `eval/reports.py`: JSON, CSV, Markdown, PDF (reportlab) with
  `_METRIC_LABELS`.
- **Figures** — `eval/figures.py`: architecture, hierarchy tree, KG example,
  retrieval flow, eval comparison, latency chart, ablation chart, RAGAS radar —
  each saved as SVG + PNG (8 figures per full run).
- **Harness + CLI** — `eval/corpus.py` (`build_corpus`: 11 nodes / 10 edges,
  dim=64), `eval/harness.py` (`benchmark_retrieval`, `benchmark_explainability`,
  `benchmark_ragas`, `run_ablation`, `run_benchmark`, `benchmark_from_config`,
  `item_relevant_ids`), `eval/cli.py` (`python -m eval.cli --quick|--config|
  --out|--dataset|--seed|--no-figures`).
- **Paper package** — `paper/`: IEEEtran `paper.tex` + `abstract.tex`,
  `introduction.tex`, `methodology.tex`, `experiments.tex`, `results.tex`,
  `future-work.tex`, `references.bib`, `poster/poster.tex` (A0),
  `presentation/slides.tex` (beamer), and build `README.md`.
- **Reproducibility** — `scripts/reproduce.sh` (venv → locked deps → benchmark
  → tests) and `requirements-lock.txt` (pinned eval deps).
- **Tests** — `tests/test_eval_dataset.py`, `test_eval_retrieval_metrics.py`,
  `test_eval_explainability_metrics.py`, `test_eval_ragas.py`,
  `test_eval_harness.py` (+ session fixtures in `conftest.py`): 86 new tests,
  none of the existing tests modified.

## Verification
- Backend: `pytest` → 447 passed (361 pre-existing unchanged + 86 new Module 10).
- Frontend:
  - `cd ui && npm install` → clean
  - `npm run build` → type-check + production build OK (code-split chunks)
  - `npm test` → 49 passed
  - `npm run preview` → serves dist with HTTP 200 smoke test
- `ruff check eval/ tests/test_eval_*.py` → clean (new code); repo-wide
  `ruff check .` → 78 pre-existing errors (unrelated baseline).
- Benchmark (`python -X utf8 -m eval.cli --out evaluation`, contract_act_gold,
  10 items, K=5, seed 42, ~0.25 s): retrieval MRR hhgr 0.750 / dense 0.700 /
  bm25 0.758 / graph 0.650 / naive_rag 0.700; R@5 bm25 0.900, others 0.800;
  hhgr mean 2.58 ms (~388 QPS); explainability citation_accuracy 0.95,
  hierarchy_correctness 1.00, graph_path_accuracy 1.00, provenance_completeness
  0.85, evidence_coverage 0.68, CA-F1 1.00; ablation full MRR 0.750 vs
  no_multilingual 0.650 + cite_acc 0.75; RAGAS hhgr faithfulness 1.0, answer
  relevancy 0.783, context recall 0.75, context precision 0.419, answer
  correctness 0.44.
- Outputs: `evaluation/reports/` (benchmark.json/md/pdf + 5 CSVs) and
  `evaluation/figures/*.svg|*.png` + `figures.json`.
- Deployment config: `deploy.config.cli validate` passes for development /
  docker profiles and fails fast for the production template (missing
  `LLM_API_KEY`).
- Compose: all three YAML files parse (services verified); nginx configs pass
  a brace-balance structural check.
- Environment limitation: Docker / nginx are not installed on this machine, so
  `docker compose up` and `nginx -t` could not be executed locally; validation
  is offline and CI is configured to perform the container builds.
