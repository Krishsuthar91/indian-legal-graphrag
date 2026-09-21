# Issue #13 — Storage Artifacts Investigation

**Status:** Investigation complete (read-only; no code was modified)
**Date:** 2026-09-20
**Scope:** why processed artifacts accumulate under repeated corpus rebuilds/ingests

---

## 1. Findings summary

Storage grows because the pipeline is **create-and-append everywhere and deletes nowhere**:

1. `data/processed/` and `data/hierarchy/` accumulate duplicates because a
   document's identity (`document_id`) is derived from the **on-disk path** of
   the ingested file, not from content identity. Every upload re-ingests the
   same Act as a *new* document, and the test suites write their ephemeral
   samples into the real data dirs. Nothing ever prunes superseded copies.
2. `data/provenance/` grows one JSON file per answered query; nothing ever
   expires records.
3. The upload handler intends to delete its temp file but on Windows the
   unlink can fail while the worker thread still holds the handle, leaving
   orphan files (2 present today).
4. The vector store is clean in the default in-memory mode, but in server
   mode (`QDRANT_URL` set) stale vectors accumulate because the deletion
   paths (`sync_graph`, `delete_collection`) exist but have **no production
   caller**.
5. `evaluation/` is *not* an accumulator: reports/figures use fixed filenames
   and are overwritten each run. (The `v243` comparison JSONs are an
   intentional suffix-per-run benchmark output.)

**Measured inventory (2026-09-20)**

| Directory        | Files | Bytes     | Notes |
|------------------|-------|-----------|-------|
| `data/processed` | 1490  | 4,386,572 | 1487 of 1490 in 6 duplicate-content groups; only 266 have a matching hierarchy |
| `data/hierarchy` | 266   | 3,331,067 | 2 canonical + 264 skipped duplicates; 265-file Contract-Act group + 1 IPC |
| `data/uploads`   | 2     | 1,286,322 | orphaned upload temp files |
| `data/provenance`| 198   | 3,589,965 | 1 JSON per answered query |
| `data/eval`      | 8     | ~small    | gold CSVs/JSONs + `experiment.json` + `manifest.json` (static fixtures) |
| `evaluation/`    | 28    | ~2.9 MB   | fixed-name reports + `figures/`; plus self-suffixed `v243` JSONs |

The 1490 processed files group by first-title as:

| Group title | Count | Kind |
|---|---|---|
| THE INDIAN CONTRACT ACT, 1892 (1-page fragment) | 862 | duplicates of the uploaded Act |
| CIVIL APPELLATE JURISDICTION (1-page) | 244 | ingest test/demo output |
| BENGALURU BENCH (1-page judgment) | 243 | ingest test/demo output |
| Rule 45-A of the Code of Civil Procedure (1-page) | 122 | ingest test/demo output |
| The Indian Contract Act, 1872 (45-page, canonical text) | 18 | duplicates of the good Act upload |
| THE INDIAN PENAL CODE (119-page) | 1 | the one IPC copy |

---

## 2. Execution trace (every writer)

**`data/processed/{document_id}.json`**
- `src/ingestion/pipeline.py:138-140` — `ingest_document()` writes the ingested
  doc via `write_text` (overwrites same id, never deletes).
- `src/ingestion/pipeline.py:31-34` — `_generate_document_id()` =
  `sha256(f"{path.resolve()}:{text[:500]}")[:16]`, i.e. **path-dependent**.

**`data/hierarchy/{document_id}.json`**
- `src/hierarchy/parser.py:386-398` — `parse_and_save()` writes the parsed
  hierarchy (overwrite same id, never deletes stale ones).
- `src/hierarchy/parser.py:400-406` — `parse_all()` iterates **all**
  `data/processed/*.json`; has no production caller today (offline-rebuild
  driver if invoked).

**`data/uploads/{uuid4}_{name}`**
- `src/api/documents.py:50-69` — `_save_upload()` stages the POSTed file;
  handler `finally` unlinking can fail on Windows while the `to_thread`
  worker still holds the file handle (exception swallowed) → orphans.
- `src/api/documents.py:72-103` — `ingest_upload()` = ingest → parse →
  import → index against the shared corpus.

**`data/provenance/{provenance_id}.json`**
- `src/llm/provenance.py:285-293` — `ProvenanceStore.save()` writes one JSON
  per `AnswerResult` (uuid4 provenance id, never cleaned).
- `src/llm/service.py:187` — saves provenance for every `/query`.

**Qdrant vectors**
- `src/embeddings/store.py:27-29` — deterministic `point_id = uuid5(node_id)`
  makes upserts idempotent.
- `src/embeddings/store.py:104-113` — `delete_collection()` exists, called
  **only from tests** (`tests/test_qdrant_store.py`).
- `src/embeddings/indexer.py:221-234` — `sync_graph()` deletes stale points,
  called **only from tests** (`tests/test_indexer.py:220`).
- Default `QA_INDEX_IN_MEMORY=True` (`settings.py:93`) → fresh `:memory:`
  store per build, so vectors are clean in the default path; with
  `QDRANT_URL` set (`settings.py`), `ensure_collections` creates-if-missing
  and upserts accumulate stale points across rebuilds.

**`evaluation/`**
- `src/evaluation/report.py:432-433`, `src/evaluation/plots.py:43,97`,
  `src/evaluation/runner.py:214-236` — fixed output names, overwritten per run.
- `eval/reports.py:47` — per-run `benchmark.json`, fixed name.

---

## 3. Root cause

1. **Identity is path-based, not content-based.** Uploads stage to a unique
   `uuid4` path and tests stage to unique `tmp_path` dirs, so the same Act
   uploaded (or test-ingested) twice produces a different `document_id` and a
   brand-new processed + hierarchy pair. This is what produced thousands of
   near-identical Contract-Act files.
2. **No retention/pruning anywhere.** Canonical selection
   (`src/knowledge_graph/canonical.py`) picks the best duplicate (node count →
   section count → parser format → stable id → mtime) and `import_all`
   imports only the winner, but the losers stay on disk forever. The
   module docstring states "Files are never deleted — only ignored during
   loading."
3. **Provenance is write-once-tomorrow.** Every query appends a file that
   nothing expires.
4. **Server-mode vectors never shrink.** The only deletion code has zero
   production callers.
5. **Tests write to the real data dirs.** `tests/test_pipeline.py` and
   `tests/test_hierarchy_parser.py` call `ingest_document`/`parse_and_save`
   with real `OUTPUT_DIR`/`HIERARCHY_DIR` (the upload/API tests use the
   `isolated_dirs` monkeypatch and are safe). Each full-suite run adds several
   processed + hierarchy files.

`processed(1490) vs hierarchy(266)`: hierarchy holds one file per document
that reached `parse_and_save` (upload API + `test_hierarchy_parser`); the
other 1224 processed files come from ingest runs that never parsed a
hierarchy (`test_pipeline`, earlier demos) and are pure orphans.

---

## 4. Impact

- **Disk:** ~12 MB idle grow unboundedly with every upload, `/query`, and
  pytest run.
- **Startup/perf:** every boot that loads the corpus iterates all 266
  hierarchy files to pick 2 canonical; a full offline rebuild (`parse_all`)
  would read all 1490 processed files. Cost is linear-ish but growing.
- **Correctness risk:** canonical selection prefers newest mtime among
  equals, so re-uploading an Act can silently swap which text is indexed
  (citation/§ numbering) without deleting the loser.
- **Orphan uploads** are untrusted bytes left in the data dir.
- **Provenance** grows 1 file per query with no bound.

---

## 5. Proposed fixes (for consideration — no code changed)

1. **Content-address identity:** hash normalized text (first N chars/pages)
   instead of the resolved path when deriving `document_id`, so identical
   re-uploads collapse to one document and overwrite.
2. **Prune at rebuild time:**
   - `parse_all`/`import_all`: after canonical selection, remove
     non-canonical hierarchy files and processed JSONs not referenced by any
     hierarchy (or move them to an archive dir).
   - `parse_and_save`: when a strictly-better duplicate is stored, delete the
     superseded hierarchy immediately.
3. **Provenance TTL/cap:** keep last N records (or honor an
   `QA_PROVENANCE_MAX_RECORDS`) and expire files on save; `/provenance` still
   answers within the window.
4. **Upload hygiene:** perform the temp-file unlink inside the `to_thread`
   worker (so the handle is closed before unlink) and retry on Windows
   `OSError`; treat `data/uploads` as scratch, not persistent.
5. **Server-mode vectors:** invoke the existing-but-unused `sync_graph()`
   after each import, or document that server mode requires a full
   rebuild-bootstrap per deploy.

---

## 6. Regression risk of the fixes

- Content-addressed ids change `document_id` values → any persisted gold/
  provenance keys drift; tests asserting id stability still pass (same
  file → same id) but snapshot values change. Migration needed for stored
  golds/provenance.
- Pruning non-canonical files flips the "never deleted" contract that
  `tests/test_canonical_corpus.py` and `tests/test_knowledge_graph.py`
  currently assert — those tests must be updated to the new semantics.
- `sync_graph` at startup affects only server mode; in-memory path
  unchanged; needs count-verification tests.
- Provenance TTL affects `tests/test_llm_provenance.py` (expects files on
  disk) and the `GET /provenance` lookup.
- `evaluation/` fixed-name outputs are safe; only the suffix-per-run
  benchmark JSONs grow, by design.

---

## 7. Measurements methodology

- Byte/file counts: `Get-ChildItem -Recurse -File | Measure-Object`.
- Duplicate grouping: read-only python across `data/processed` grouping by
  first title / content signature; `data/hierarchy` grouped by canonical
  selection rules in `src/knowledge_graph/canonical.py`.
- Caller tracing: grep across `src`, `scripts`, `tests`, `eval` for
  `ingest_document|parse_and_save|parse_all|import_all|write_text|unlink|
  delete_collection|sync_graph`.
- No destructive commands were run.