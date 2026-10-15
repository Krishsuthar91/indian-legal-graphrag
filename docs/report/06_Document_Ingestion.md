# 06 — Document Ingestion

Ingestion turns a raw uploaded legal document (PDF/DOCX/TXT, scanned or digital) into clean
text, structured metadata, a parsed hierarchy, graph edges, and vector indices. This document
describes that pipeline stage by stage.

Primary sources: `src/ingestion/` (`pipeline.py`, `identity.py`, `pruning.py`, `loaders/`,
`ocr/`, `cleaning/`, `detection/`, `metadata/`), invoked by `src/api/documents.py` and
`src/hierarchy/parser.py`.

---

## 6.1 Pipeline overview

```text
 upload ─► validate ─► load ─► scan-detect ─► OCR (if needed)
        ─► language detect ─► clean ─► metadata extract
        ─► write processed JSON
        ─► hierarchy parse  ─► graph import ─► vector index ─► ingestion summary
```

Each stage is a pure function over an in-flight document object; the orchestrator is
`src/ingestion/pipeline.py`, and the API handler `src/api/documents.py:165` (`ingest_upload`)
invokes it and returns a summary.

---

## 6.2 Stage 1 — Validation and storage

- Input is `multipart/form-data`; the handler checks the content type against an allow-list
  (PDF, DOCX, TXT) and enforces a maximum size (`src/middleware/security.py` also caps the
  body for uploads).
- The raw file is saved to `data/uploads/` before processing so a failed pipeline can be
  retried without re-upload.

---

## 6.3 Stage 2 — Document loading

`src/ingestion/loaders/` provides format-specific loaders behind a common interface:

| Loader | Library | Behaviour |
|--------|---------|-----------|
| `pdf_loader.py` | `pdfplumber` first, `PyMuPDF` fallback | Extracts per-page text and page count |
| `docx_loader.py` | `python-docx` | Extracts paragraphs + tables |
| `txt_loader.py` | stdlib | Reads plain UTF-8/text |

The loader returns a list of pages/sections preserving reading order, which downstream stages
rely on for legal numbering.

---

## 6.4 Stage 3 — Scanned-document detection

`src/ingestion/detection/scanner_detector.py` decides whether a PDF is **scanned** (image-only,
little or no extractable text) using a text-density heuristic: if the extracted text per page
falls below a threshold, the document is routed to OCR.

---

## 6.5 Stage 4 — OCR

`src/ingestion/ocr/engine.py` implements a two-engine OCR strategy:

1. **PaddleOCR** (primary) — higher accuracy, preferred when installed.
2. **Tesseract** (via `pytesseract`) — fallback when PaddleOCR is unavailable or fails.

OCR renders each page to an image and extracts text with confidence scores; low-confidence
pages are flagged in metadata. OCR is only invoked for scanned pages or image regions, keeping
digital PDFs fast.

---

## 6.6 Stage 5 — Language detection

`src/ingestion/detection/language_detector.py:12-33` detects the document language using
Unicode script range analysis (Devanagari, Bengali, Tamil, Telugu, etc.) combined with
`langdetect`. The detected language is stored on the document and drives multilingual
tokenization and expansion downstream (`src/retrieval/query.py:155-172`).

---

## 6.7 Stage 6 — Text cleaning

`src/ingestion/cleaning/text_cleaner.py` normalises extracted text while preserving legal
structure:

- Removes repeated headers/footers and page numbers.
- Collapses excess whitespace; normalises dashes/quotes and Unicode.
- **Preserves** section numbering, clause markers, and list structure (critical because the
  hierarchy parser depends on these patterns).
- Strips OCR artefacts conservatively.

---

## 6.8 Stage 7 — Metadata extraction

`src/ingestion/metadata/extractor.py` collects:

- **File metadata** — original filename, size, MIME type, upload timestamp.
- **Document metadata** — page count, detected language, whether OCR was applied, OCR
  confidence summary, title/act name heuristics.
- **Provenance metadata** — source path, content hash.

---

## 6.9 Stage 8 — Identity (content-addressed id)

`src/ingestion/identity.py` computes a **16-character content-addressed `document_id`** from
the document's content hash (and stable metadata). Consequences:

- Identical documents map to the same id → **idempotent** ingestion.
- The id is used uniformly as the graph `document_id`, the hierarchy filename, the processed
  filename, and the Qdrant payload key, so all stores stay consistent.

---

## 6.10 Stage 9 — Persist processed document

The cleaned pages, metadata, and id are written to `data/processed/<document_id>.json`
(**1632 files** present). This is the durable, re-processable representation.

---

## 6.11 Stage 10 — Hierarchy parsing

`src/hierarchy/parser.py` (patterns in `src/hierarchy/patterns.py`, tree assembly in
`src/hierarchy/tree_builder.py`, validation in `src/hierarchy/validators.py`, models in
`src/hierarchy/models.py`) converts the cleaned text into the
Document→Chapter→Section→Clause tree:

- Recognises chapters/parts (Roman numerals, "CHAPTER", "PART"), sections ("1.", "2.",
  "Section 3", "Art. 21"), and clauses (a/b/c, (1)(2), provisos, illustrations).
- Assigns monotonically increasing **node ids**.
- Captures titles and section numbers.
- Emits cross-reference placeholders consumed by the citation extractor.

The tree is written to `data/hierarchy/<document_id>.json` (**295 files** present). Validation
guards against malformed trees; duplicates are handled by the canonical corpus
(`src/knowledge_graph/canonical.py`).

---

## 6.12 Stage 11 — Graph import

`src/knowledge_graph/importer.py` loads the hierarchy JSON into Neo4j (production) or the
`InMemoryGraph` (dev/test), creating `Document/Chapter/Section/Clause` nodes and `PART_OF`
edges, then runs `src/knowledge_graph/citation_extractor.py` to add `CITES` edges.

---

## 6.13 Stage 12 — Vector indexing

`src/embeddings/indexer.py` embeds each unit at four granularities and upserts points into the
`documents` / `chapters` / `sections` / `clauses` Qdrant collections, attaching the payload
described in `05_Database_Design.md §5.3.2`. `src/embeddings/service.py` exposes this as a
high-level call used by the upload handler.

---

## 6.14 Stage 13 — Pruning and reporting

`src/ingestion/pruning.py` removes intermediate/temporary artefacts; the upload handler then
returns a summary (document id, counts of nodes per level, indexing status). Maintenance
scripts (`scripts/audit_corpus.py`, `scripts/prune_stale_artifacts.py`) keep the corpus clean.

---

## 6.15 Failure handling

| Failure | Behaviour |
|---------|-----------|
| Unsupported type / oversize | 4xx response before storage |
| Loading yields no text and OCR unavailable | Document flagged; pipeline halts with a clear error |
| OCR low confidence | Text kept, flagged in metadata |
| Hierarchy parse finds no sections | Tree still written; validators record a warning |
| Neo4j unavailable | Falls back to `InMemoryGraph` where configured |
| Qdrant unavailable | Indexing deferred; document remains in processed/hierarchy stores |

---

## 6.16 End-to-end example

```text
Upload "indian_contract_act_1872.pdf"
  ├─ validate: application/pdf, 2.1 MB              OK
  ├─ load: 60 pages of digital text                 OK
  ├─ scan-detect: text density high → no OCR        OK
  ├─ language: en                                   OK
  ├─ clean: headers/footers removed                 OK
  ├─ metadata: pages=60, ocr=false, title detected  OK
  ├─ identity: document_id = 0d1934142f67c5f5       OK
  ├─ persist: data/processed/0d1934142f67c5f5.json  OK
  ├─ hierarchy: 1 doc → 10 chapters → 238 sections  OK
  ├─ graph: 249 nodes + PART_OF + CITES             OK
  └─ index: 4 collections upserted                  OK
```

*(Document ids and counts illustrate the shape of the pipeline; exact values depend on the
file ingested.)*

---

## 6.17 Key ingestion files quick reference

| File | Responsibility |
|------|----------------|
| `src/ingestion/pipeline.py` | Orchestrates all stages |
| `src/ingestion/identity.py` | Content-addressed `document_id` |
| `src/ingestion/pruning.py` | Intermediate artefact cleanup |
| `src/ingestion/loaders/pdf_loader.py` | PDF text extraction |
| `src/ingestion/loaders/docx_loader.py` | DOCX extraction |
| `src/ingestion/loaders/txt_loader.py` | Plain text |
| `src/ingestion/ocr/engine.py` | PaddleOCR + Tesseract |
| `src/ingestion/detection/scanner_detector.py` | Scanned-doc routing |
| `src/ingestion/detection/language_detector.py` | Language/script detection |
| `src/ingestion/cleaning/text_cleaner.py` | Legal-preserving cleaning |
| `src/ingestion/metadata/extractor.py` | File + document metadata |
| `src/hierarchy/parser.py` | Hierarchy parsing entry point |
| `src/knowledge_graph/importer.py` | Graph import |
| `src/embeddings/indexer.py` | Vector indexing |
| `src/api/documents.py` | HTTP upload handler (`ingest_upload`) |
