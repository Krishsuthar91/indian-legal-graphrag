# Issue #13 V2.5 Implementation Report — Content-Based Document IDs

**Status:** Implemented, full regression green, no commits/pushes made.
**Date:** 2026-09-20

---

## 1. Root cause

`document_id` was derived from the **on-disk path** of the ingested file plus
the first 500 characters of text (`src/ingestion/pipeline.py`
`_generate_document_id`):

```python
raw = f"{path.resolve()}:{text_sample[:500]}"
return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

Because identity depended on `path.resolve()`, every upload (staged to a
unique `data/uploads/{uuid4}_{name}` temp path) and every test run (staged
to a unique `tmp_path`) produced a new `document_id` for identical content.
Each re-upload therefore created fresh `data/processed/*.json`,
`data/hierarchy/*.json`, provenance, and (server-mode) vector artifacts —
the duplication quantified in `ISSUE13_STORAGE_ARTIFACTS.md`.

## 2. Files modified

| File | Change |
|---|---|
| `src/ingestion/identity.py` | **New.** Content-based document identity: `content_document_id()`, `resolve_document_id()`, `DOCUMENT_ID_LENGTH=16`, and `CANONICAL_CONTENT_IDS` registry preserving the bundled IPC/ICA ids. |
| `src/ingestion/pipeline.py` | `_generate_document_id(path, text_sample)` → `_generate_document_id(file_bytes)` delegating to `resolve_document_id()`; `ingest_document()` now reads the raw file bytes once and derives the id from them. |
| `tests/test_document_identity.py` | **New.** 12 tests covering all required identity invariants (see §4). |

No parser, hierarchy, embedding, retrieval, confidence, or routing behaviour
changed. Downstream consumers (`_ACT_NAME_TO_DOC_ID`,
`_STABLE_CANONICAL_IDS`, `import_all`, indexer, retriever, qdrant store)
are untouched.

## 3. Before vs After identity generation

| | Before (V2.4) | After (V2.5) |
|---|---|---|
| Input | `path.resolve()` + `text[:500]` | raw file bytes |
| Digest | `sha256(f"{path}:{text[:500]}")[:16]` | `sha256(file_bytes)[:16]` |
| Filename change | new id | **same id** |
| Directory/upload-path change | new id | **same id** |
| Any content byte change | id may stay same | **new id** (path-hash mixes path, so same text at a new path flipped the id) |
| Canonical IPC/ICA re-upload | could create a duplicate id | resolves to `cf20a14c52127fd5` / `0d1934142f67c5f5` via `CANONICAL_CONTENT_IDS` full-digest registry |
| Repeated identical uploads | duplicate processed+hierarchy+vectors | one processed + one hierarchy file, idempotent vector upserts |

Canonical preservation is implemented as an *exact* full-SHA-256 match
registry (values derived from the git-tracked bundled sources in
`data/uploads/`), so arbitrary uploads remain strictly content-addressed while
the built-in Acts keep their established ids.

## 4. Test results

New `tests/test_document_identity.py` (12 tests):
- same content → same id (`content_document_id`/`resolve_document_id` pure functions)
- id length standardised to 16 hex
- **same content, different filename → same document_id** (integration)
- **same content, different temp directory → same document_id** (integration)
- **modified content → different document_id** (integration)
- **repeated uploads do not create a new artifact** (2 uploads → 1 processed JSON)
- **canonical bundled documents unchanged** (registry maps tracked ICA/IPC bytes → `0d1934142f67c5f5` / `cf20a14c52127fd5`; id independent of filename)

Full suite:

```
1009 passed, 5 warnings in 75.75s (was 997 before this change, +12 new tests)
```

Targeted regression: `test_pipeline`, `test_hierarchy_parser`,
`test_documents_api`, `test_canonical_corpus` — 55 passed.

Lint:

```
ruff check src/ingestion/identity.py src/ingestion/pipeline.py tests/test_document_identity.py → All checks passed!
ruff format --check (these files) → clean
```

Note: `ruff check .` and `ruff format --check .` are non-zero at repo level,
but that is **pre-existing**: stashing all work and re-running on the clean
working tree at HEAD still reports 73 check errors / 28 unformatted files.
None originate from the files changed in V2.5.

## 5. Runtime verification

A driver mirroring the exact upload chain (`ingest_document` →
`parse_and_save`, as wired in `src/api/documents.py::ingest_upload`) was run
with the data directories redirected to a temp workspace:

- identical `.txt` uploaded twice (different temp paths/names) →
  **same document_id**, `processed/` = 1 file, `hierarchy/` = 1 file
- same content from a *nested* directory → same document_id
- modified `.txt` → **different document_id** (one new file)
- bundled ICA PDF ingested end-to-end → **`0d1934142f67c5f5`** retained

## 6. Remaining limitations

- Identity is byte-level: two PDFs with identical text but different bytes
  (e.g. produced by different tools, or re-downloaded with new producer
  metadata) still get different ids. This matches the "modified content →
  new id" requirement but is stricter than text-level dedup.
- `_generate_document_id` is a private helper; any external code importing it
  with the old `(path, text_sample)` signature would break (no such caller
  exists in-repo; only `pipeline.py:121` used it).
- The canonical registry hardcodes the two bundled full digests. If a
  bundled source is replaced in `data/uploads/`, the registry must be
  updated to keep re-uploads mapping to the canonical id.
- Upload temp-file orphanage (`data/uploads/`) and provenance growth are
  issue-#13 fixes **2–4** and are intentionally out of scope here.

## 7. Risks

- **Low.** The identity change only affects newly ingested documents;
  existing tracked canonical JSONs and their ids are unchanged; startup
  corpus loading (`build_default_corpus`) reads existing `data/hierarchy`
  files and is untouched.
- Changing only filename/directory no longer changes identity, so two
  documents with identical bytes that were previously distinct now collapse
  to one overwrite — a deliberate behaviour of Fix #1, but a behaviour
  change callers should be aware of.
- Hidden risk if someone re-uploads a bundled Act whose bytes differ from the
  tracked sources: it will get a new id (correct content-addressing), and
  canonical selection still keeps the registered id via
  `_STABLE_CANONICAL_IDS`, so retrieval mappings stay stable.

## 8. Commit/push confirmation

No commits, tags, pushes, or PRs were created. All changes remain in the
working tree: `src/ingestion/identity.py` (new), `src/ingestion/pipeline.py`
(modified), `tests/test_document_identity.py` (new), plus this report.