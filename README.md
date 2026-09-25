# HHGR — Hybrid Hierarchical Graph Retrieval for Indian Legal Document Intelligence

An explainable, multilingual question-answering system for Indian legal documents. Combines hierarchical graph retrieval with LLM-generated cited answers and a multi-stage verification framework.

## Motivation

Indian legal documents — statutes, codes, and judgments — are deeply hierarchical and densely cross-referenced. A single question about "breach of contract remedies" may require navigating from Section 73 to Section 74, cross-referencing illustrations, and distinguishing overruled precedents. Traditional flat retrieval systems miss these structural relationships, producing incomplete or hallucinated answers.

HHGR addresses this by building a **hierarchical knowledge graph** from parsed legal documents and fusing four complementary retrieval signals — lexical, citation, hierarchy, and structural — to produce grounded, cited answers with full provenance.

## Key Contributions

- **Hybrid Hierarchical Graph Retrieval (HHGR):** A four-signal retrieval engine that combines text matching, citation matching, hierarchy propagation, and structural importance scoring over a legal knowledge graph.
- **Legal Hierarchy Parser:** A stack-based parser with 20+ numbering patterns that extracts Document → Chapter → Section → Clause trees from Indian legal PDFs, building Nested Set Indices for fast subtree queries.
- **Multi-Stage Verification Framework:** A 12-component verification pipeline (evidence sufficiency, evidence relevance, citation entailment, verification badge, confidence calibration) that ensures answers are only flagged "Supported" when backed by actual evidence.
- **Explainable Answers:** Every response includes source citations, a 6-step reasoning chain, counter-authority detection (overruled/superseded/repealed/void), and full retrieval provenance.
- **Reproducible Evaluation:** A complete benchmark suite with 50 questions across the Indian Contract Act 1872, NVIDIA LLM evaluation, calibration metrics, and reliability diagrams.

## System Architecture

```
Legal PDF/DOCX/TXT
       │
       ▼
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Ingestion   │───▶│ Hierarchy Parser  │───▶│ Knowledge Graph  │
│  (OCR, Lang) │    │ (20+ patterns)   │    │ (PART_OF/CITES)  │
└─────────────┘    └──────────────────┘    └─────────────────┘
                                                 │    │
Question ──▶ Query Analysis ──▶ HHGR Retrieval ◄─┘    │
                                    │                   │
                                    ▼                   │
                          Vector Store (Qdrant) ◄───────┘
                                    │
                                    ▼
                     ┌──────────────────────────┐
                     │  Verification Framework   │
                     │  (Sufficiency, Relevance, │
                     │   Entailment, Badge)      │
                     └──────────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────┐
                     │  LLM Answer Generation    │
                     │  (Cited, Explainable)     │
                     └──────────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────┐
                     │  React Dashboard (UI)     │
                     │  (Evidence, KG, Provenance)│
                     └──────────────────────────┘
```

## Hybrid Retrieval Pipeline

The HHGR retrieval engine fuses four weighted signals:

| Signal | Description | Default Weight |
|--------|-------------|----------------|
| **Text** | Lexical overlap between query keywords and node content (multilingual tokenization) | 0.30 |
| **Citation** | Query legal references (e.g. "Section 4") matching node numbering or text | 0.20 |
| **Hierarchy** | Evidence propagated from seed matches to ancestors/descendants along PART_OF edges | 0.30 |
| **Structural** | Node importance (degree + subtree size), normalized per query | 0.20 |

The vector layer adds multilingual dense search over Qdrant (4 collections: documents/chapters/sections/clauses) and fuses dense/graph/hierarchy signals with configurable weights (default: dense 0.40 / graph 0.35 / hierarchy 0.25).

## Verification Framework

A multi-stage verification pipeline ensures answer reliability:

1. **Evidence Sufficiency** — Dice coefficient of character bigrams between query and evidence, with question boilerplate stripped.
2. **Evidence Relevance** — LLM judge with deterministic fallback scoring each evidence chunk (0.0–1.0).
3. **Citation Entailment** — Claim-level entailment check between generated answer and retrieved evidence.
4. **Verification Badge** — 5-priority rule engine producing: `supported`, `insufficient_evidence`, `contradicted`, `no_evidence`, `no_answer`.
5. **Confidence Calibration** — Formula: `0.35×entailment + 0.30×relevance + 0.20×sufficiency + 0.15×retrieval_base` with hard rules (contradiction → 0.20 cap, insufficient → 0.45 cap).
6. **VerificationTrace** — Structured audit trail recording every decision step.

## Installation

### Prerequisites

- Python 3.11+
- Node.js 20+ (for the frontend)
- Docker and Docker Compose (for full-stack deployment)
- NVIDIA API key (for LLM-powered evaluation; optional for offline testing)

### Backend

```bash
# Clone the repository
git clone https://github.com/Krishsuthar91/indian-legal-graphrag.git
cd indian-legal-graphrag

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your settings (LLM provider, API keys, etc.)
```

### Frontend

```bash
cd ui
npm install
npm run dev      # Development server at http://localhost:5173
```

### Docker (Full Stack)

```bash
docker compose up --build    # Full 6-service stack at http://localhost
```

## Running Locally

```bash
# Start the backend
uvicorn src.main:app --reload          # http://localhost:8000

# Run the step-by-step demos
python demo_ingest.py       # Ingest a sample legal PDF
python demo_hierarchy.py    # Parse document into hierarchy tree
python demo_kg.py           # Build knowledge graph
python demo_retrieval.py    # Run HHGR retrieval
python demo_embeddings.py   # Vector store + hybrid search

# Run backend tests
pytest -q                   # 1047 tests

# Run frontend tests
cd ui && npm test            # 49 Vitest + Testing Library tests
```

## Evaluation

### LLM Configuration

The active LLM provider is `nvidia` (defined in `deploy/env/.env.development`). `NVIDIA_MODEL` is the **single source of truth** for the NVIDIA model name — the generic `LLM_MODEL` never overrides it. Generic `LLM_*` settings still take precedence for the API key and base URL when both are set.

- Put your real key in `deploy/env/.env.development.local` (git-ignored); the tracked env templates keep empty/placeholder secrets.
- Runtime load order: code defaults ← `.env.development` ← `.env.development.local` ← OS environment.
- Retired model ids are rejected by NVIDIA NIM with `HTTP 410` (e.g. `meta/llama-3.3-70b-instruct` reached EOL on 2026-08-26). The repo defaults to `nvidia/nemotron-3-super-120b-a12b`. See `final_report_llm_model_config.md` for the full precedence breakdown.

### Benchmark Evaluation (50 questions, deterministic)

The committed benchmark runs offline with a deterministic embedding provider and
mock LLM, making it fully reproducible from the canonical corpus. Retrieval and
verification metrics are measured deterministically. Answer-related metrics
(Answer Accuracy, Hallucination Rate, Faithfulness) reflect the mock LLM and
should be interpreted as the offline pipeline's grounding behaviour rather than
the production NVIDIA model's answer quality.

```bash
# Regenerate the benchmark report from the committed raw results
python -m scripts.run_final_evaluation

# Report generated at results/evaluation_report.md
```

### Results Summary (Contract Act 1872)

| Metric | Before Parser Fix | After Parser Fix | Delta |
|--------|-------------------|------------------|-------|
| Overall Score | 0.4185 | **0.6271** | +0.2086 |
| Section Accuracy | 0.1111 | **0.8700** | +0.7589 |
| MRR | 0.0370 | **0.7400** | +0.7030 |
| Recall@5 | 0.0556 | **0.3316** | +0.2760 |
| Hallucination Rate | 0.5008 | **0.7883** | +0.2875 |
| Grounding Accuracy | 1.0000 | **1.0000** | — |
| Avg Latency | 2909ms | **108ms** | -2801ms |

The full metric breakdown (including confidence calibration ECE 0.1792) is in
`results/evaluation_report.md`.

### Offline Deterministic Evaluation

```bash
# Full benchmark (reports + figures)
python -m eval.cli --config data/eval/config/experiment.json --out evaluation

# Quick smoke test (3 items)
python -m eval.cli --quick --out evaluation

# One-command reproducibility
bash scripts/reproduce.sh
```

## Project Structure

```
explaintool/
├── src/                          # Backend source (10,088 lines)
│   ├── main.py                   # FastAPI entry point
│   ├── api/                      # REST endpoints (11 routes)
│   ├── config/                   # Settings, logging
│   ├── ingestion/                # PDF/DOCX/TXT loaders, OCR, cleaning
│   ├── hierarchy/                # Legal hierarchy parser (222 nodes)
│   ├── knowledge_graph/          # Graph builder, traversal, citations
│   ├── retrieval/                # HHGR engine (4-signal fusion)
│   ├── embeddings/               # Vector store (Qdrant), indexing
│   ├── llm/                      # LLM abstraction, prompts, provenance
│   ├── evaluation/               # Benchmark pipeline, metrics, plots
│   ├── middleware/                # Security (API key, rate limiting)
│   ├── monitoring/               # Prometheus metrics, /metrics endpoint
│   └── utils/                    # Constants, exceptions, helpers
├── ui/                           # React 18 + TypeScript frontend
├── eval/                         # Module 10 evaluation package
├── tests/                        # 1047 backend tests
├── data/                         # Hierarchy JSONs, eval datasets, uploads
├── results/                      # Evaluation results & reports
├── deploy/                       # Docker, nginx, env profiles
├── monitoring/                   # Prometheus + Grafana overlay
├── paper/                        # IEEE paper, poster, slides
├── scripts/                      # Evaluation & reproducibility scripts
├── docs/                         # Architecture, deployment, developer docs
└── pyproject.toml                # Project metadata & dependencies
```

## Technologies Used

| Category | Technologies |
|----------|-------------|
| **Backend** | Python 3.11, FastAPI, Pydantic, uvicorn |
| **LLM** | NVIDIA NIM (`nvidia/nemotron-3-super-120b-a12b`), OpenAI-compatible API |
| **Vector Store** | Qdrant (cosine similarity, 4 collections) |
| **Knowledge Graph** | InMemoryGraph, Neo4j (production) |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS |
| **Visualization** | Cytoscape.js (KG), React Flow (hierarchy), Recharts (confidence) |
| **Embeddings** | bge-m3, LaBSE, MuRIL, IndicBERT (multilingual), deterministic (testing) |
| **OCR** | PaddleOCR, Tesseract (fallback) |
| **Infrastructure** | Docker, Docker Compose, nginx, Prometheus, Grafana |
| **CI/CD** | GitHub Actions (ruff, pytest, vitest, Docker builds) |
| **Testing** | pytest (1047 tests), Vitest + Testing Library (49 tests) |

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System architecture and deployment topology |
| [Verification Framework](docs/VerificationFramework.md) | Multi-stage verification pipeline details |
| [Evaluation](docs/Evaluation.md) | Benchmark methodology and results |
| [Dataset](docs/Dataset.md) | Evaluation datasets and gold standards |
| [API Reference](docs/API.md) | REST API endpoint documentation |
| [Deployment](docs/DEPLOYMENT.md) | Docker and production deployment guide |
| [Developer Guide](docs/DEVELOPER.md) | Local setup, testing, code conventions |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Startup Hang Root Cause](ROOT_CAUSE_STARTUP_HANG.md) | Cold-start snapshot + deferred prewarm fix |
| [LLM Config Report](final_report_llm_model_config.md) | NVIDIA model precedence, EOL analysis, before/after evidence |

## Future Work

- **Multilingual Expansion:** Evaluate Hindi, Tamil, and Bengali legal documents using MuRIL/IndicBERT embeddings.
- **Live Neo4j Integration:** Persistent graph storage with real-time document ingestion.
- **LLM Query Expansion:** Phase 4 query expansion for complex multi-part legal questions.
- **Citation Graph Analysis:** Precedent tracking across judgment hierarchies via deeper citation chain analysis.
- **User Feedback Loop:** Active learning from user corrections to improve retrieval ranking over time.
- **Mobile Interface:** Responsive redesign for field lawyers and legal aid workers.

## Acknowledgements

Built with [FastAPI](https://fastapi.tiangolo.com/), [Qdrant](https://qdrant.tech/), [Neo4j](https://neo4j.com/), [React](https://react.dev/), and [NVIDIA NIM](https://build.nvidia.com/). Legal corpus sourced from publicly available Indian statute texts.

## Citation

```bibtex
@inproceedings{hhgr2026,
  title={HHGR: Hybrid Hierarchical Graph Retrieval for Explainable Indian Legal Document Intelligence},
  author={Project Contributors},
  booktitle={Proceedings of the International Conference on Legal Information Systems},
  year={2026}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.
