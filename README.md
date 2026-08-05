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
are untouched.

- **Pages** — Home (search box, language selector, recent questions), Explain (full query
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
docker-compose up --build
```

## Project Structure

```
explaintool/
├── src/
│   ├── main.py              # FastAPI entry point
│   ├── config/
│   │   ├── settings.py      # Pydantic settings
│   │   └── logging_config.py
│   ├── api/
│   │   ├── router.py        # API router
│   │   ├── health.py        # Health endpoints
│   │   └── qa.py            # QA endpoints (/query, /explain, /provenance/{id})
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── ingestion/
│   │   ├── pipeline.py      # ingest_document() orchestrator
│   │   ├── loaders/         # PDF / DOCX / TXT loaders
│   │   ├── ocr/             # PaddleOCR + Tesseract fallback
│   │   ├── detection/       # scanned-PDF + language detection
│   │   ├── metadata/        # metadata extraction
│   │   └── cleaning/        # text cleaner
│   ├── hierarchy/
│   │   ├── patterns.py      # legal numbering patterns
│   │   ├── tree_builder.py  # parent assignment + nested set
│   │   ├── validators.py    # hierarchy validators
│   │   └── parser.py        # parse_document()
│   ├── knowledge_graph/
│   │   ├── neo4j_driver.py  # InMemoryGraph + Neo4jDriver
│   │   ├── schema.py        # NodeLabel / RelType enums
│   │   ├── citation_extractor.py
│   │   ├── entity_resolver.py
│   │   ├── importer.py      # hierarchy JSON -> graph
│   │   ├── traversal.py     # parent/children/citation/shortest-path APIs
│   │   └── stats.py
│   ├── retrieval/
│   │   ├── query.py         # RetrievalQuery + parse_query()
│   │   ├── context.py       # ancestors/descendants + evidence propagation
│   │   ├── scorer.py        # text/citation/hierarchy/structural signals
│   │   └── ranker.py        # retrieve() orchestrator
│   ├── embeddings/
│   │   ├── models.py        # model registry + collection mapping
│   │   ├── providers.py     # deterministic / sentence-transformers / transformers
│   │   ├── service.py       # batched EmbeddingService
│   │   ├── store.py         # QdrantStore (4 collections)
│   │   ├── indexer.py       # full + incremental + sync indexing
│   │   ├── retriever.py     # dense + hybrid (graph/hierarchy) retrieval
│   │   └── benchmark.py     # latency reports
│   ├── llm/
│   │   ├── llm.py           # LLM abstraction (OpenAI/Llama/Mistral/Qwen + mock)
│   │   ├── prompts.py       # evidence-based prompt builder
│   │   ├── provenance.py    # evidence/reasoning/citations + ProvenanceStore
│   │   ├── explanation.py   # explainability engine (confidence, validity, counter-authority)
│   │   ├── schemas.py       # QA API request/response models
│   │   └── service.py       # QueryService + default corpus wiring
│   └── utils/
│       ├── constants.py
│       ├── exceptions.py
│       └── helpers.py
├── ui/                        # Module 8 — React frontend (Vite + TS)
│   ├── src/
│   │   ├── api/client.ts      # Axios client for /query, /explain, /provenance/{id}
│   │   ├── components/        # QueryInput, AnswerCard, EvidencePanel, HierarchyTree,
│   │   │                      # KnowledgeGraph, ProvenancePanel, ConfidenceGauge,
│   │   │                      # ValidityBadge, CounterAuthorityCard, LoadingOverlay, ...
│   │   ├── pages/             # Home, Explain, Provenance, Settings
│   │   ├── hooks/             # React Query hooks, dark mode, recent questions, settings
│   │   ├── types/             # TS types mirroring the backend schemas
│   │   ├── utils/             # format/score, keyword highlighting, graph builders
│   │   ├── test/              # fixtures + jsdom setup
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig*.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── tests/                     # 343 backend tests + 49 frontend tests
├── logs/
├── data/
├── pyproject.toml
├── requirements.txt
└── docker-compose.yml
```
