# 17 — Repository Statistics

All figures below were measured directly against the working tree (git branch `main`, latest
commit `fa892d8`). Counts exclude virtual environments, `node_modules`, and `__pycache__`.

---

## 17.1 Code size summary

| Area | Files | Lines of code |
|------|------:|--------------:|
| Backend (`src/`, `*.py`) | 90 | 12,823 |
| Backend tests (`tests/`, `*.py`) | 68 (65 `test_*.py`) | 10,952 |
| Frontend (`ui/src`, `*.ts`/`*.tsx`) | 50 | 3,125 |
| Offline eval harness (`eval/`, `*.py`) | 10 | 2,494 |
| Scripts (`scripts/`) | 17 | — |
| **Python total** (whole repo, excl. envs) | **200** | — |

Test suite: **1,033 test functions** across the `tests/` package; `UI` tests via Vitest.

---

## 17.2 Backend inventory

| Metric | Value |
|--------|------:|
| Python files under `src/` | 90 |
| Backend packages under `src/` | 14 (+ `main.py`) |
| Sub-directories under `src/` (excl. `__pycache__`) | 19 |
| Lines of code under `src/` | 12,823 |

### 17.2.1 Largest backend modules

| Module | Lines |
|--------|------:|
| `src/llm/explanation.py` | 1,918 |
| `src/llm/llm.py` | 708 |
| `src/retrieval/query_expansion.py` | 489 |
| `src/llm/service.py` | 447 |
| `src/embeddings/store.py` | 444 |
| `src/llm/provenance.py` | 404 |
| `src/evaluation/report.py` | 394 |
| `src/hierarchy/parser.py` | 336 |
| `src/embeddings/indexer.py` | 304 |
| `src/api/qa.py` | 285 |
| `src/knowledge_graph/neo4j_driver.py` | 266 |
| `src/embeddings/retriever.py` | 244 |

The explainability engine alone is ~15% of backend code, reflecting that explainability is the
project's central differentiator.

### 17.2.2 Backend packages

```text
src/
├── api/              # 4 routers (health, qa, documents, router)
├── config/           # settings, logging
├── embeddings/       # models, providers, store, indexer, retriever, service, benchmark
├── evaluation/       # runner, dataset, corpus, pipeline, metrics/, calibration, report, plots, analysis, sections
├── hierarchy/        # parser, patterns, tree_builder, validators, models
├── ingestion/        # pipeline, identity, pruning, loaders/, ocr/, cleaning/, detection/, metadata/
├── knowledge_graph/  # importer, neo4j_driver, schema, traversal, citation_extractor, canonical, entity_resolver, stats
├── llm/              # llm, prompts, explanation, provenance, schemas, service
├── middleware/       # security
├── models/           # shared schemas
├── monitoring/       # metrics, middleware
├── retrieval/        # query, intent, scorer, ranker, context, query_expansion, metrics
├── utils/            # constants, exceptions, helpers
└── main.py
```

---

## 17.3 Frontend inventory

| Metric | Value |
|--------|------:|
| TS/TSX files under `ui/src` | 50 |
| Lines of code under `ui/src` | 3,125 |
| Pages | 5 (Home, Explain, Upload, Provenance, Settings) |
| Components | 14 (`*.tsx`) |
| Hooks | 6 (`useQuery`, `useExplain`, `useProvenance`, `useRecentQuestions`, `useSettings`, `useTheme`) |
| Util modules | 3 (+ tests) |

---

## 17.4 API surface

| Metric | Value |
|--------|------:|
| REST endpoints (incl. root) | 11 |
| — under `/api/v1` | 10 |
| Health/check endpoints | 6 |
| QA endpoints | 3 (`/query`, `/explain`, `/provenance/{id}`) |
| Upload endpoints | 1 |
| Operational endpoints | `/metrics` |
| Interactive docs | `/docs`, `/redoc`, `/openapi.json` |

---

## 17.5 Data & corpus inventory

| Artefact | Count |
|----------|------:|
| Parsed hierarchy files (`data/hierarchy/*.json`) | 295 |
| Processed documents (`data/processed/*.json`) | 1,632 |
| Provenance records (`data/provenance/*.json`) | 271 |
| Uploaded raw files (`data/uploads/`) | 2 |
| Gold datasets (`data/eval/gold/*.json`) | 5 + manifest |
| Gold evaluation items | 34 (10 grounded) |
| Benchmark questions (`contract_act_1872_benchmark.csv`) | 50 |
| Qdrant collections | 4 |
| Neo4j node labels | 5 |
| Neo4j relationship types | 3 (`PART_OF`, `CITES`, `REFERENCES`) |

Canonical Acts resolved include the Indian Contract Act (`0d1934142f67c5f5`) and the Indian
Penal Code (`cf20a14c52127fd5`).

---

## 17.6 Tests inventory

| Suite | Count |
|-------|------:|
| Backend test files (`tests/*.py`) | 68 |
| Backend `test_*.py` files | 65 |
| Backend test functions | 1,033 |
| Frontend test files (Vitest) | utils tests (`format`, `graph`, `highlight`) + component tests |
| Validation cases | 130 manual cases (`validation/manual_test_cases.md`) |

`pytest` config: `asyncio_mode = "auto"`, `testpaths = ["tests"]`.

---

## 17.7 Documentation & publication inventory

| Artefact | Count |
|----------|------:|
| Developer docs (`docs/*.md`) | 18 |
| Generated technical docs (`docs/report/*.md`) | 20 (this package) |
| Paper LaTeX files (`paper/`) | 11 |
| Workflow files (`.github/workflows/`) | 2 |
| Root-level engineering reports | ~15 |
| Release/governance files | ~8 |

---

## 17.8 Evaluation artefacts inventory

| Artefact | Count |
|----------|------:|
| Offline report tables | 5 CSV + md/json/pdf |
| Offline figures | 8 (SVG + PNG each = 16 files) |
| Production result files (top-level `results/`) | ~8 |
| Historical result runs | 5 directories (`baseline`, `phase4`, `pre-parser-fix`, `v30`, `v30_50q`) |
| Validation report | `validation/validation_report.md` |

---

## 17.9 Deployment inventory

| Metric | Value |
|--------|------:|
| Compose services | 6 (api, react, nginx, neo4j, qdrant, redis) |
| Dockerfiles | 2 (backend, frontend) |
| Env profiles | 5 (`development`, `development.local`, `docker`, `production`, root `.env`) |
| nginx configs | 2 |
| Monitoring services | 4 (prometheus, grafana, node-exporter, neo4j-exporter) |
| Prometheus scrape targets | 4 |
| Grafana dashboards | 1 (`explaintool_overview.json`) |

---

## 17.10 Technology count

| Layer | Count |
|-------|------:|
| Python runtime dependencies | 25 (in `requirements.txt`) |
| Frontend runtime dependencies | ~13 |
| Backend subsystems (M1–M9) | 9 |
| Retrieval signals (total across layers) | 4 (HHGR) + 3 (fusion) + 5 (explanation) |
| Verification stages | 6 |
| Verification badges | 5 |

---

## 17.11 Repository top-level entries

Source/functional: `src`, `ui`, `eval`, `evaluation`, `results`, `validation`, `data`,
`scripts`, `deploy`, `monitoring`, `docs`, `paper`, `tests`, `logs`.

Tooling/artefact: `.github`, `.vscode`, `.ruff_cache`, `.pytest_cache`, `.agents`, `.archify`,
`brag-output`, `brag-research-2026-09-27-215736`, `demo-output`, plus root config/report files.

> Note: several directory entries, such as `.agents`, `.archify`, `brag-output`, and
> `demo-output`, are tooling/generated artefacts rather than part of the application runtime.
