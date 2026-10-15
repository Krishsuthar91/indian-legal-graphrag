# 13 — System Workflow

This document traces the system end-to-end in both directions: the **corpus workflow**
(how documents become searchable) and the **query workflow** (how a question becomes a cited,
verified answer). It then details the lifecycle of a single HTTP request.

Sources: `src/api/`, `src/ingestion/`, `src/hierarchy/`, `src/knowledge_graph/`,
`src/embeddings/`, `src/retrieval/`, `src/llm/`, `ui/src/`.

---

## 13.1 Two workflows

```text
CORPUS WORKFLOW (offline, per document)         QUERY WORKFLOW (online, per question)
──────────────────────────────────────         ──────────────────────────────────────
 1. Upload                                       1. Ask (UI → POST /query)
 2. Load (PDF/DOCX/TXT)                          2. Query parsing + intent
 3. Scan-detect + OCR                            3. Corpus-aware expansion
 4. Language detect                              4. Seed retrieval (dense + lexical)
 5. Clean                                        5. HHGR graph scoring (4 signals)
 6. Metadata extract                             6. Hierarchy propagation
 7. Content-addressed id                         7. Fusion (dense/graph/hierarchy)
 8. Persist processed JSON                       8. Rank + top-k + threshold
 9. Parse hierarchy                              9. Verification (sufficiency→entailment)
10. Import knowledge graph                      10. Grounding guard
11. Build vector indices                        11. LLM generation
12. Prune / report                              12. Persist provenance
                                                13. Render (answer, evidence, KG, provenance)
```

---

## 13.2 Corpus workflow — step by step

1. **Upload.** A user (or script) posts a file to `POST /api/v1/documents/upload`
   (`src/api/documents.py:165`). The handler validates type/size and stores the raw file in
   `data/uploads/`.
2. **Load.** `src/ingestion/loaders/` extracts per-page text (`pdfplumber`/`PyMuPDF` for PDF,
   `python-docx` for DOCX, stdlib for TXT).
3. **Scan-detect + OCR.** `src/ingestion/detection/scanner_detector.py` flags image-only PDFs;
   `src/ingestion/ocr/engine.py` runs PaddleOCR (primary) or Tesseract (fallback).
4. **Language detect.** `src/ingestion/detection/language_detector.py:12-33` detects
   language/script.
5. **Clean.** `src/ingestion/cleaning/text_cleaner.py` strips headers/footers while preserving
   legal numbering.
6. **Metadata.** `src/ingestion/metadata/extractor.py` records file + document metadata.
7. **Identity.** `src/ingestion/identity.py` computes the 16-char content-addressed
   `document_id`.
8. **Persist processed.** Cleaned pages + metadata → `data/processed/<id>.json`.
9. **Parse hierarchy.** `src/hierarchy/parser.py` builds the Document→Chapter→Section→Clause
   tree → `data/hierarchy/<id>.json`.
10. **Import graph.** `src/knowledge_graph/importer.py` creates nodes + `PART_OF`; the citation
    extractor adds `CITES` edges (Neo4j or `InMemoryGraph`).
11. **Index vectors.** `src/embeddings/indexer.py` embeds at four granularities and upserts into
    the Qdrant `documents`/`chapters`/`sections`/`clauses` collections.
12. **Prune/report.** `src/ingestion/pruning.py` cleans intermediates; the handler returns an
    indexing summary.

---

## 13.3 Query workflow — step by step

1. **Ask.** The React SPA (`ui/src/pages/Explain.tsx` → `useQuery`) sends `POST /api/v1/query`.
2. **Parse.** `src/retrieval/query.py` normalises text, detects the Act, extracts references,
   classifies intent (`src/retrieval/intent.py`), and tokenizes multilingually.
3. **Expand.** `src/retrieval/query_expansion.py` adds **corpus-verified** expansions only.
4. **Seed.** `src/embeddings/retriever.py` runs dense Qdrant search + lexical search, merges
   and de-duplicates candidates.
5. **Graph score.** `src/retrieval/scorer.py` computes text/citation/hierarchy/structural
   signals and the HHGR score.
6. **Propagate.** `src/retrieval/context.py` pulls ancestors/descendants/siblings (bounded to
   the document).
7. **Fuse.** `retriever.py` combines dense + graph + hierarchy into a fused score.
8. **Rank.** `src/retrieval/ranker.py` sorts, applies the confidence threshold, selects top-k.
9. **Verify.** `src/llm/service.py` runs sufficiency (bigram Dice) → relevance judge →
   claim-level entailment → counter-authority → confidence calibration.
10. **Guard.** The grounding guard checks the draft against evidence and may downgrade the
    badge / decline to answer.
11. **Generate.** The configured LLM (NVIDIA NIM / mock) produces the cited answer from the
    verified evidence.
12. **Persist.** `src/llm/provenance.py` writes the immutable provenance record.
13. **Render.** The SPA draws the `AnswerCard`, `EvidencePanel`, `ReasoningChain`,
    `KnowledgeGraph`, `HierarchyTree`, `ConfidenceGauge`, and `ProvenancePanel`.

---

## 13.4 Request lifecycle (HTTP)

```text
client
  │  POST /api/v1/query {question, top_k}
  ▼
[uvicorn] ─► [MetricsMiddleware]  start timer
          ─► [SecurityHeadersMiddleware]
          ─► [CORSMiddleware]
          ─► [router /api/v1 → qa.py]
                └─ validate QueryRequest (Pydantic v2)
                └─ ExplanationService.answer(...)
                     ├─ retrieval (steps 2–8)
                     ├─ verification (step 9–10)
                     ├─ LLM call (step 11)
                     └─ provenance write (step 12)
          ◄─ QueryResponse (JSON)
[MetricsMiddleware] stop timer, record metrics
  ▼
client
```

Failure behaviour: validation → `422`; unsupported upload → `4xx`; dependency outage →
degraded badge (`no_evidence`/`no_answer`) rather than a crash; unexpected errors → safe `500`.

---

## 13.5 State and data hand-offs

| From | To | Payload |
|------|----|---------|
| `query.py` | `query_expansion.py` | `ParsedQuery` |
| `query_expansion.py` | `retriever.py` | expanded query + references |
| `retriever.py` | `scorer.py` | seed candidates |
| `scorer.py` | `context.py` | signal scores |
| `context.py` | `ranker.py` | propagated candidates |
| `ranker.py` | `explanation.py` | top-k evidence |
| `explanation.py` | `service.py` | verified evidence + reasoning |
| `service.py` | `provenance.py` | full record |
| `provenance.py` | client | provenance id (then `GET /provenance/{id}`) |

---

## 13.6 Modes of operation

| Mode | Retrieval | LLM | Use |
|------|-----------|-----|-----|
| Production | real embeddings + Qdrant + Neo4j | NVIDIA NIM | live QA |
| Offline evaluation | deterministic embeddings + `InMemoryGraph` | mock | reproducible benchmarks |
| Explain-only | retrieval + verification | none | debug/settings |
| Health/probe | dependency checks | none | ops |

---

## 13.7 Deployment-time workflow

1. `docker compose up` starts `api`, `react`, `nginx`, `neo4j`, `qdrant`, `redis`.
2. The API container entrypoint (`deploy/scripts/entrypoint.sh`) validates production config
   (`deploy/config/cli.py validate`) and launches `uvicorn src.main:app`.
3. nginx routes `/api/*` to the API and everything else to the SPA.
4. Prometheus scrapes `/metrics`; Grafana renders `explaintool_overview.json`.

See `15_Configuration.md` for environment details.
