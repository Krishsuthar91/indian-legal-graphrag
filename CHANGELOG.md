# Changelog

All notable changes to the HHGR project are documented in this file.

## [1.0.0] - 2026-08-26

### Final Release — Evaluation Complete

- Full 50-question benchmark (offline deterministic, mock LLM + deterministic embeddings, seed 42)
- Overall score: 0.6271
- Section accuracy: 0.8700 (+0.7589 from pre-parser-fix baseline)
- MRR: 0.7400 (+0.7030)
- Hallucination rate: 0.7883 (mock-LLM grounding behaviour; not production answer quality)
- Grounding accuracy: 1.0000
- Reliability diagram and calibration metrics generated (ECE: 0.1792)
- Complete documentation suite (architecture, verification, evaluation, dataset, API)
- Research paper-ready tables and comparison analysis
- Version bumped to 1.0.0; ruff clean; full test suite passing

## [0.9.0] - 2026-08-25

### Task 11 — Final Evaluation

- Created `scripts/run_final_evaluation.py` with cached evaluation mode
- Ran full 50-question benchmark against NVIDIA production model
- Generated comparison tables (Before/After parser fix)
- Produced `results/evaluation_report.md` with 5 paper-ready tables
- Generated reliability diagram (`results/reliability_diagram.png`)
- Backed up pre-parser-fix results to `results/pre-parser-fix/`

## [0.8.0] - 2026-08-25

### Task 10 — Corpus Regeneration

- Fixed `text_cleaner.py` regex to preserve section headings during cleaning
- Added `_split_embedded_sections()` to `parser.py` for embedded section detection
- Regenerated full hierarchy corpus (161 documents)
- Primary corpus expanded from 46→222 nodes, 16→192 section nodes
- Rebuilt knowledge graph, embeddings, and vector store
- Updated query expansion tests for new corpus (8 tests, all passing)

## [0.7.0] - 2026-08-25

### Task 9 — Root Cause Analysis

- Identified root cause: `text_cleaner.py` regex `r"\n(\d+[A-Za-z]*\.)"` was stripping section heading markers
- Corpus coverage analysis confirmed "phantom sections" (14, 15, 16, 17, 18, 25)
- Documented the parser→cleaner entanglement issue

## [0.6.0] - 2026-08-25

### Tasks 5-8 — Verification Framework & Calibration

- **Task 5:** Redesigned confidence scoring formula (0.35×entailment + 0.30×relevance + 0.20×sufficiency + 0.15×retrieval_base)
- Added 5-tier confidence labels (very_high/high/medium/low/very_low)
- Implemented hard rules (contradiction→0.20 cap, insufficient→0.45 cap)
- **Task 6:** Created `VerificationTrace` dataclass for structured audit trails
- Attached to `ExplanationResult`, `ExplanationResponse`, `QueryResponse`
- **Task 7:** Created `RetrievalFailureAnalysis` in `src/evaluation/analysis.py`
- Integrated failure classification into evaluation pipeline
- **Task 8:** Implemented calibration metrics (ECE, MCE) in `src/evaluation/calibration.py`
- Added reliability diagram generation in `src/evaluation/plots.py`
- Integrated calibration into evaluation pipeline and report

## [0.5.0] - 2026-08-24

### Tasks 1-4 — Multi-Stage Verification

- **Task 1:** Implemented query-aware evidence sufficiency using Dice coefficient
- Question boilerplate stripping before similarity computation
- **Task 2:** Created `EvidenceRelevance` dataclass with LLM judge and deterministic fallback
- Added `llm_client` parameter to `ExplainabilityEngine`
- **Task 3:** Implemented `CitationEntailment` with claim-level entailment checking
- `_extract_claims()` splits answers into sentences for individual verification
- **Task 4:** Rewrote verification badge with 5-priority rules
- Extended `Validity` with status, reason, support_score, relevance_score, sufficiency_score
- Implemented entanglement sentinel (`citation_entailment_overall = -1.0`)
- Lowered relevance threshold from 0.40 to 0.30 for short legal texts

## [0.4.0] - 2026-08-20

### Module 10 — Research Evaluation Package

- Gold dataset: 34 items across 5 legal domains (Contract Act, BNS, BNSS, BSA, SC Judgments)
- Evaluation harness with deterministic mock LLM
- Metrics: retrieval (Recall@K, MRR, MAP, NDCG), generation (faithfulness, grounding), explainability (citation accuracy, provenance completeness)
- 5 system implementations: HHGR, dense-only, BM25, graph-only, naive RAG
- Ablation study: 6 arms (full / no_graph / no_hierarchy / no_dense / no_multilingual / no_explainability)
- CLI: `python -m eval.cli` with JSON/CSV/Markdown/PDF output
- IEEE paper draft (abstract, introduction, methodology, experiments, results, future work)
- A0 poster and beamer slides
- Reproducibility script (`scripts/reproduce.sh`)

## [0.3.0] - 2026-08-15

### Module 9 — Production Deployment & Enterprise Infrastructure

- Multi-stage Docker builds (Python 3.11-slim backend, Node 20 build → nginx frontend)
- Six-service Docker Compose stack (api, react, nginx, neo4j, qdrant, redis)
- nginx reverse proxy with TLS readiness, gzip, security headers
- Environment profiles (production, development, docker) with fail-fast validation
- Security middleware (API key auth, per-IP rate limiting, request size limits)
- Health probes (/live, /check/database, /check/vector, /check/llm)
- Prometheus + Grafana monitoring overlay
- Per-channel rotating log files
- CI pipeline (GitHub Actions: ruff, pytest, vitest, Docker builds)

## [0.2.0] - 2026-08-10

### Modules 5-8 — Retrieval, Embeddings, LLM, Frontend

- **Module 5:** HHGR retrieval engine (4-signal fusion: text, citation, hierarchy, structural)
- Query expansion with legal synonyms
- Adaptive top-K based on query complexity
- **Module 6:** Embedding providers (bge-m3, LaBSE, MuRIL, IndicBERT, deterministic)
- Qdrant vector store (4 collections, incremental indexing, language filtering)
- Hybrid retrieval (dense + graph + hierarchy fusion)
- **Module 7:** LLM abstraction (OpenAI-compatible, mock provider for testing)
- Explainability engine with 6-step reasoning chain
- Counter-authority detection (overruled/superseded/repealed/void)
- Confidence scoring and validity flags
- Provenance store (in-memory + JSON persistence)
- **Module 8:** React 18 + TypeScript + Vite frontend
- Query flow with evidence panel, confidence gauge, validity badge
- Hierarchy viewer (React Flow), knowledge graph explorer (Cytoscape.js)
- Provenance browser, dark mode, responsive layout
- 49 unit tests (Vitest + Testing Library)

## [0.1.0] - 2026-08-01

### Modules 1-4 — Foundation, Ingestion, Hierarchy, Knowledge Graph

- **Module 1:** Project skeleton, FastAPI server, Pydantic settings, structlog logging, utilities
- **Module 2:** Legal document ingestion (PDF/DOCX/TXT), OCR (PaddleOCR + Tesseract), language detection (7 languages), metadata extraction, text cleaning
- **Module 3:** Legal hierarchy parser (20+ numbering patterns), stack-based parent assignment, Nested Set Index (left/right/depth), subtree queries
- **Module 4:** Knowledge graph (InMemoryGraph + Neo4j), citation extraction (Sections, Rules, Articles, Orders, AIR/SCC cases), entity resolution, PART_OF/CITES/REFERENCES edges, graph traversal APIs
- 361 initial tests
