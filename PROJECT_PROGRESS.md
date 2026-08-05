# Project Progress — Explainable Multilingual Hierarchical Graph-RAG with HHGR

Status tracker for the staged build. All modules are complete. Backend: 343 pytest
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

## Verification
- Backend: `pytest` → 343 passed (unchanged — no backend modules modified).
- Frontend:
  - `cd ui && npm install` → clean
  - `npm run build` → type-check + production build OK (code-split chunks)
  - `npm test` → 49 passed
  - `npm run preview` → serves dist with HTTP 200 smoke test
- `ruff check src tests` → clean for Modules 7–8 code (pre-existing hints unrelated
  to these modules remain).

## Next
- Module 9 — not started (per scope).
