# 01 — Project Overview

> Project codename: **explaintool** (`pyproject.toml:6`)
> Public title: **HHGR — Hybrid Hierarchical Graph Retrieval for Indian Legal Document Intelligence**
> Version: **1.0.0** (`src/config/settings.py:15`, `pyproject.toml:7`)

This document is the entry point of the technical documentation package. It explains the
problem, users, objectives, innovations, workflow, features, technology stack, and the
high-level architecture. All facts are derived from the repository source, not from the
README alone.

---

## 1. What problem does this project solve?

Indian legal documents — statutes (e.g. the Indian Contract Act 1872, the Indian Penal
Code 1860) and judgments — are **deeply hierarchical and densely cross-referenced**. A
single question about a legal concept ("What is theft?") can require navigating from a
general definition, to its illustrations, to a penalty section, and to related provisions
through cross-references (`src/retrieval/scorer.py:1-8`, `docs/API.md`, `README.md:7-9`).

The repository's own problem statement identifies three dominant failure modes of current
retrieval-augmented systems for law (`README.md:20-28`):

1. **Flat retrieval loses legal structure.** Sections reference other sections; definitions
   recur across Acts; ambiguous phrases ("steals", "dishonestly", "movable property") carry
   legal force that a bag-of-words model is blind to.
2. **Answers are not grounded.** Generic LLM assistants generate fluent but unsupported
   text, fabricating provisions or conflating repealed law.
3. **Claims cannot be audited.** Legal professionals need to know *which section supported a
   claim*, whether the law is still in force, and *why* the system ranked one provision over
   another.

HHGR addresses all three simultaneously via a hierarchical legal knowledge graph, a
multi-signal hybrid retrieval stage, and a verification-gated generation pipeline
(`README.md:11-16`, `src/llm/explanation.py`, `src/llm/service.py`).

---

## 2. Who are the users?

The repository defines the target users implicitly through its feature set and the
`ui/` application. They are:

| User | Need | Evidence in repository |
|------|------|------------------------|
| Legal professionals / lawyers | Precise, cited answers they can audit | `README.md:20-28`, `paper/introduction.tex:1-22` |
| Litigants / citizens | Understand statutory provisions in plain terms | `ui/src/pages/Home.tsx`, example queries `README.md:274-285` |
| Legal researchers | Traceable provenance and cross-references | `ui/src/pages/Provenance.tsx`, provenance store (`src/llm/provenance.py`) |
| Multilingual users | Ask in Hindi/Tamil/Bengali and get grounded answers | `src/ingestion/detection/language_detector.py:12-33`, `README.md:43` |
| System administrators / integrators | Upload and index new documents; secure deployment | `ui/src/pages/Upload.tsx`, `src/api/documents.py`, `deploy/` |
| Researchers / reviewers | Reproduce benchmarks and ablations | `eval/`, `scripts/run_final_evaluation.py`, `paper/` |

---

## 3. Main objective

Build an **explainable, multilingual question-answering platform** for Indian legal
documents that fuses dense vector search, lexical matching, citation analysis, hierarchy
propagation, and structural-importance scoring over a legal knowledge graph, and grounds
every answer in **cited, verified evidence with full provenance** (`README.md:3`).
The research goal is stated as **Hybrid Hierarchical Graph Retrieval (HHGR)**: the
systematic fusion of structural legal signals with semantic retrieval so that ranking is
informed by both *meaning* and *structure* (`src/retrieval/scorer.py:1-8`,
`src/embeddings/retriever.py:1-8`).

---

## 4. Key innovations

1. **Hybrid Hierarchical Graph Retrieval (HHGR).** A four-signal graph scoring function
   combining *text*, *citation*, *hierarchy*, and *structural* importance, with configurable
   weights (`src/retrieval/scorer.py:18-24`, `src/retrieval/ranker.py`).
2. **Two nested fusion layers.** The HHGR four-signal score becomes the *graph* signal of a
   dense/graph/hierarchy fusion layer (`src/embeddings/retriever.py:23-27`), which is in turn
   re-ordered by a five-signal ranking weight set (dense/graph/hierarchy/keyword/citation)
   (`src/llm/explanation.py:62-76`).
3. **Hierarchy-aware evidence propagation.** Seed matches propagate to ancestors and
   descendants along `PART_OF` edges, bounded to a single document, so a Section surfaces its
   Chapter and related Clauses automatically (`src/retrieval/context.py:89-149`).
4. **Verification-gated generation.** A multi-stage verification framework (sufficiency,
   relevance, claim-level citation entailment, confidence calibration, verification badge)
   gates the answer before the LLM is called (`src/llm/service.py:275-328`,
   `docs/VerificationFramework.md`).
5. **Full provenance and explainability.** Each answer returns a reasoning chain, per-signal
   ranking scores, hierarchy paths, numbered citations, counter-authority markers, confidence
   factors, and a verification decision trace; provenance is persisted and re-fetchable by id
   (`src/llm/provenance.py`, `src/api/qa.py:305-324`).
6. **Deterministic, corpus-aware legal query expansion.** Surface phrases are expanded to
   verified section numbers only when those sections exist in the corpus, keeping expansion
   auditable and preventing hallucinated references (`src/retrieval/query_expansion.py:453-532`).
7. **Canonical corpus management.** Hundreds of duplicate hierarchy artifacts are grouped by
   normalized Act title and reduced to one canonical file per Act for deterministic imports
   and evaluations (`src/knowledge_graph/canonical.py`).
8. **Counter-authority detection.** Overruled/superseded/repealed/void markers are detected
   per provision (`src/llm/explanation.py:1433-1452`).

---

## 5. Main workflow

The end-to-end workflow (detailed in `13_System_Workflow.md`) is:

```text
Document Upload            User Question
      │                          │
      ▼                          ▼
 Ingestion pipeline        React SPA (ui/)
 (load→OCR→clean→           POST /api/v1/query
  metadata)                      │
      │                          ▼
      ▼                    FastAPI backend (src/main.py)
 Hierarchy parser         Query parsing + Act detection
 (src/hierarchy/)         (src/retrieval/query.py)
      │                          │
      ▼                          ▼
 Knowledge graph           HHGR retrieval
 import (PART_OF/CITES)   dense + graph + hierarchy
 (src/knowledge_graph/)   (src/retrieval/, src/embeddings/)
      │                          │
      ▼                          ▼
 Qdrant vector index       Verification framework
 (4 collections)          (sufficiency/relevance/entailment)
 (src/embeddings/)              │
      │                          ▼
      └──────────────► Grounded LLM generation (NVIDIA Nemotron / mock)
                                 │
                                 ▼
                    Cited answer + provenance + explanations
                                 │
                                 ▼
                          React SPA renders answer,
                          evidence, KG, hierarchy, provenance
```

---

## 6. Features

Feature list, each grounded in code:

- **Hybrid Hierarchical Graph Retrieval (HHGR)** — text/citation/hierarchy/structural fusion
  (`src/retrieval/scorer.py`, `src/retrieval/ranker.py`).
- **Dense multilingual retrieval** — bge-m3 / MuRIL / LaBSE / IndicBERT over Qdrant
  (`src/embeddings/models.py:37-82`, `src/embeddings/store.py`).
- **Hierarchy-aware retrieval** — propagation along `PART_OF` edges
  (`src/retrieval/context.py`).
- **Explainability chain** — reasoning steps emitted per query
  (`src/llm/explanation.py:567-872`).
- **Full provenance** — node ids, section numbering, per-signal scores, re-fetch by id
  (`src/llm/provenance.py`, `src/api/qa.py`).
- **Knowledge graph** — `PART_OF` / `CITES` / `REFERENCES` edges over InMemoryGraph or Neo4j
  (`src/knowledge_graph/importer.py`, `src/knowledge_graph/schema.py`).
- **Confidence scoring & calibration** — composite confidence plus ECE/MCE calibration
  (`src/llm/explanation.py:1857-2017`, `src/evaluation/calibration.py`).
- **Evidence ranking** — ranking for usefulness (chain relevance, definition promotion,
  fragment demotion) not merely relevance (`src/llm/explanation.py:1107-1123`).
- **Hallucination prevention** — grounding guard, counter-authority markers, badges
  (`src/llm/service.py:275-328`, `src/llm/explanation.py:2021-2061`).
- **Multilingual** — script detection and multilingual tokenization
  (`src/ingestion/detection/language_detector.py`, `src/retrieval/query.py:155-172`).
- **Document upload & indexing** — PDF/DOCX/TXT with OCR (`src/api/documents.py`, `src/ingestion/`).
- **NVIDIA Nemotron integration** — production generation via NVIDIA NIM
  (`src/llm/llm.py:589-616`).
- **Web dashboard** — React SPA with knowledge-graph, hierarchy, and confidence views
  (`ui/src/`).
- **Monitoring & deployment** — Prometheus, Grafana, Docker Compose, nginx (`deploy/`,
  `monitoring/`).

---

## 7. Technology stack

| Category | Technologies | Evidence |
|----------|--------------|----------|
| **Backend** | Python 3.11+, FastAPI ≥0.115, Pydantic v2, uvicorn, structlog | `pyproject.toml:12-37`, `src/main.py` |
| **LLM** | NVIDIA NIM `nvidia/nemotron-3-super-120b-a12b` (OpenAI-compatible); Gemini; mock | `src/llm/llm.py:563-616`, `src/config/settings.py:66-91` |
| **Vector store** | Qdrant (cosine, 4 collections) | `src/embeddings/store.py`, `src/embeddings/models.py:92-101` |
| **Knowledge graph** | InMemoryGraph (dev/tests), Neo4j 5 (production) | `src/knowledge_graph/neo4j_driver.py`, `src/knowledge_graph/schema.py` |
| **Embeddings** | bge-m3 (1024d), bge-large-en-v1.5, e5-large-v2, LaBSE (768d), MuRIL, IndicBERT; deterministic for tests | `src/embeddings/models.py:37-84` |
| **Frontend** | React 18, TypeScript 5.6, Vite 5, Tailwind CSS 3 | `ui/package.json`, `ui/vite.config.ts` |
| **Visualization** | Cytoscape.js (KG), React Flow (hierarchy), Recharts (confidence), framer-motion | `ui/src/components/KnowledgeGraph.tsx`, `HierarchyTree.tsx`, `ConfidenceGauge.tsx` |
| **OCR / ingestion** | PaddleOCR (primary), Tesseract (fallback); pdfplumber / PyMuPDF / python-docx | `src/ingestion/ocr/engine.py`, `src/ingestion/loaders/` |
| **Infrastructure** | Docker, Docker Compose, nginx, Prometheus, Grafana | `docker-compose.yml`, `deploy/`, `monitoring/` |
| **CI/CD** | GitHub Actions — ruff, pytest, Vitest, Docker builds | `.github/workflows/ci.yml`, `docker.yml` |
| **Evaluation** | Custom metric suite; RAGAS-style surrogate metrics | `eval/`, `src/evaluation/` |

---

## 8. High-level architecture

The repository implements a **9-module architecture (M1–M9)** documented in
`docs/ARCHITECTURE.md:22-25`:

| Module | Name | Primary code |
|--------|------|--------------|
| M1 | Configuration & utilities | `src/config/`, `src/utils/` |
| M2 | Document ingestion | `src/ingestion/` |
| M3 | Hierarchy parser | `src/hierarchy/` |
| M4 | Knowledge graph | `src/knowledge_graph/` |
| M5 | Retrieval (HHGR) | `src/retrieval/` |
| M6 | Embeddings / vector store | `src/embeddings/` |
| M7 | Explainable LLM answer generation | `src/llm/` |
| M8 | Frontend (React SPA) | `ui/` |
| M9 | Deployment / monitoring / security / CI | `deploy/`, `monitoring/`, `.github/` |

```text
                          ┌───────────────────────────────┐
                          │        React SPA (M8)          │
                          │  Home · Explain · Upload ·     │
                          │  Provenance · Settings         │
                          └───────────────┬───────────────┘
                                          │ POST /api/v1/query
                                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (src/main.py)                 │
│  Middleware: Metrics → Security → CORS                            │
│  Routers: health · qa · documents                                 │
└───────────────┬──────────────────────────────────────────────────┘
                │
      ┌─────────┴──────────┐
      ▼                    ▼
┌───────────────┐   ┌─────────────────────────────────────────────┐
│ Query parsing │   │        HHGR Retrieval (M5 + M6)             │
│ intent +      │   │  Dense (Qdrant) + Graph (4 signals) +       │
│ expansion     │   │  Hierarchy propagation → fusion → ranking   │
└───────────────┘   └───────────────┬─────────────────────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │  Explainability Engine (M7)    │
                    │  Verification · Confidence ·   │
                    │  Reasoning chain · Provenance  │
                    └───────────────┬───────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │ Grounding guard → LLM (NVIDIA) │
                    │  Cited answer + provenance     │
                    └───────────────────────────────┘

Corpus side:  Ingestion (M2) → Hierarchy parser (M3) → Knowledge graph (M4)
              → Qdrant index (M6) → canonical corpus (M4)
```

---

## 9. Document map

| File | Subject |
|------|---------|
| `02_Folder_Structure.md` | Every folder's purpose, files, dependencies |
| `03_Backend_Architecture.md` | FastAPI, routes, services, middleware, config |
| `04_Frontend_Architecture.md` | React structure, components, hooks, state |
| `05_Database_Design.md` | Neo4j schema, Qdrant collections, embeddings |
| `06_Document_Ingestion.md` | Upload → OCR → clean → parse → store |
| `07_Retrieval_Pipeline.md` | Every retrieval stage |
| `08_HHGR_Algorithm.md` | HHGR formal specification + pseudo-code |
| `09_Explainability.md` | Evidence, provenance, verification, confidence |
| `10_AI_Models.md` | Every model used |
| `11_Dataset.md` | Corpus and gold evaluation data |
| `12_API_Documentation.md` | Every endpoint with examples |
| `13_System_Workflow.md` | End-to-end step-by-step |
| `14_Project_Features.md` | Feature-by-feature explanation |
| `15_Configuration.md` | Environment, Docker, dependencies |
| `16_Experiments.md` | Evaluation pipelines and results |
| `17_Repository_Statistics.md` | Counts and inventory |
| `18_Research_Contributions.md` | Novelty vs. prior art |
| `19_Limitations.md` | Limitations and future work |
| `20_Report_Mapping.md` | Mapping to report/paper sections |
