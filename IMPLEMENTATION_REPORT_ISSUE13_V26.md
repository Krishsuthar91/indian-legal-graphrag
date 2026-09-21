# Issue #13 V2.6 Implementation Report — Prune Stale Processed/Hierarchy Artifacts During Corpus Rebuild

**Status:** Implemented, full regression green, no commits/pushes made.
**Date:** 2026-09-20

---

## 1. Root cause

Document identity was historically path-derived (fixed in V2.5), so every
re-upload/test run of identical content created a **new** `document_id` and a
new pair of artifacts. The historical duplicates remain on disk:

- `data/processed/` — ~1,500 files; ~99% collapse into a handful of identical
  content groups (e.g. 862 one-page "THE INDIAN CONTRACT ACT, 1892" files).
- `data/hierarchy/` — ~270 files; 264 are non-canonical duplicates of the two
  bundled Acts.

Every corpus rebuild (`build_default_graph` → `import_all`,
`canonical_doc_ids`) opens **every** JSON in these directories, so obsolete
duplicates keep costing load time and keep polluting canonical selection.
No code path had ever deleted a superseded artifact.

## 2. Files modified

| File | Change |
|---|---|
| `src/ingestion/pruning.py` | **New.** Duplicate detection + selection + deletion for processed/hierarchy artifacts. |
| `scripts/rebuild_assets.py` | Step 0 of the rebuild now calls `prune_all(PROCESSED_DIR, HIERARCHY_DIR)` before building the graph/vector assets. |
| `scripts/prune_stale_artifacts.py` | **New.** Standalone `--dry-run` capable cleanup entry point. |
| `tests/test_pruning.py` | **New.** 12 tests (see §6). |

No parser, hierarchy generation, retrieval, embedding, ranking, confidence,
routing, or canonical-ID behaviour changed.

## 3. Cleanup algorithm

**Duplicate definition** (in `src/ingestion/pruning.py`):
- `processed`: two documents are duplicates when they share a `document_id`
  **OR** an identical content hash (`sha256` of the joined page texts, in
  page order, formfeed-separated).
- `hierarchy`: two files are duplicates when they represent the same
  `document_id` **OR** an identical content fingerprint (`sha256` of a
  deterministic serialisation of the node body — i.e. the document content,
  excluding the identity field).

Grouping is transitive via union-find: a file connects its `document_id`
node with its content-hash node; any shared key merges groups.

**Ordering/privacy guarantees**
1. **Protection:** files whose `document_id ∈ {0d1934142f67c5f5,
   cf20a14c52127fd5}` (from `canonical._STABLE_CANONICAL_IDS`) are never
   deleted. If a protected file is in a duplicate group it becomes the
   survivor and all other members are removed.
2. **Selection when duplicates differ** (highest wins): valid JSON →
   schema/format version → completeness (page count for processed, node
   count for hierarchy) → newest mtime. This satisfies "prefer valid JSON;
   latest schema; highest completeness; newest timestamp."
3. **Corruption:** files that fail to parse (or lack the expected structure)
   are marked invalid and can only be grouped by their filename stem. A
   corrupt file is therefore discarded **only** when a valid duplicate with the
   same document id exists; a lone corrupt file is never deleted.
4. **Idempotency:** after a run, every duplicate group holds exactly one
   survivor, so a second run removes nothing.

**Logging** follows the requested contract (event names via the project
structlog logger and matching plain `stdout` lines):

```
artifact.prune.start
artifact.prune.keep   document_id=... path=...
artifact.prune.remove path=...
artifact.prune.complete removed_processed=X removed_hierarchy=Y
```

## 4. Before vs After artifact counts

Measured by a **read-only `--dry-run`** over the real directories
(no files were actually deleted during this work):

| Directory | Before | Projected removed | Projected after |
|---|---|---|---|
| `data/processed/` | 1,521 | **1,511** | ~10 unique documents |
| `data/hierarchy/` | 272 | **267** | ~5 unique documents |

(Dry-run also exercised the idempotency property: it is purely report-only and
deletes nothing.)

## 5. Runtime verification

Performed on a **temporary copy** (`tempfile.mkdtemp`) seeded with **real**
duplicate artifacts copied from the current `data/processed/` and
`data/hierarchy/` (6 content-duplicates per dir, selected by the pruning
grouping logic itself) plus the real canonical ICA + IPC documents.

```
BEFORE:                 processed=8 hierarchy=8   (6 duplicates + ICA + IPC each)
AFTER FIRST RUN:        removed_processed=5 removed_hierarchy=5
                          processed surviving=3  hierarchy surviving=3
                          canonical ICA/IPC intact=True (both dirs)
AFTER SECOND RUN:       removed_processed=0 removed_hierarchy=0
VERDICT: PASS
```

The second run confirms idempotency — 0 additional removals.

## 6. Test results

`tests/test_pruning.py` (12 new tests):

- duplicate processed removal (same content)
- duplicate processed removal (same `document_id`)
- duplicate hierarchy removal (same `document_id`)
- duplicate hierarchy removal (same content)
- canonical processed never deleted
- canonical ids registered (`{0d1934142f67c5f5, cf20a14c52127fd5}`)
- mixed canonical + duplicate set → exactly the two canonical docs survive
- corrupted duplicate discarded (valid peer kept)
- corrupt non-duplicate survives
- idempotent second run removes nothing
- dry-run removes nothing
- empty directory no-op

Full suite:

```
1021 passed, 5 warnings in 80.21s   (1009 before this change, +12 new)
```

Targeted: `tests/test_pruning.py` + `tests/test_document_identity.py` → 24 passed.

Lint (changed/new files):

```
ruff check   src/ingestion/pruning.py scripts/prune_stale_artifacts.py tests/test_pruning.py → All checks passed!
ruff format --check  (same set) → All files already formatted
```

Note: `scripts/rebuild_assets.py` has 3 **pre-existing** ruff findings
(mid-file `import json`, two >100-char print lines) that predate this change;
they were not introduced by the V2.6 edit and were left untouched to avoid
unrelated churn.

## 7. Risks

- **Deletion is permanent.** Pruning is wired into `rebuild_assets.py`, so a
  production rebuild now removes files. Mitigations: selection is
  conservative (keeps the *best* per identity, never deletes canonical docs,
  never deletes lone corrupt files), idempotent, and a `--dry-run` flag is
  available on the standalone script.
- **Content-hash grouping is byte-exact.** Two documents whose text is
  semantically identical but byte-different (e.g. whitespace/encoding) are
  treated as distinct — no accidental deletion of near-duplicates.
- **Document_id collisions** in the same directory are merged into one
  artifact (best kept). If a caller intentionally stored two different
  documents under one id, one would be removed; identical document_ids are by
  definition the same document, so this is the intended contract.
- Running on the real data dirs (not dry-run) has not been performed; the
  projected counts in §4 are from a read-only dry-run.

## 8. Remaining limitations

- Pruning runs only when a rebuild/cleanup is invoked (`rebuild_assets.py` or
  `prune_stale_artifacts.py`); it does not prune continuously per upload.
- Orphaned artifacts are not touched: a processed JSON with no hierarchy (and
  vice-versa) is not a *duplicate*, so it survives. Orphan handling is a
  separate cleanup concern (noted in `ISSUE13_STORAGE_ARTIFACTS.md`).
- The survivor is not renamed to a canonical filename; the best existing file
  is kept at its current path.
- `data/uploads/` orphanage and provenance growth are fixes 3–4 of Issue #13
  and remain out of scope here.

## 9. Commit/push confirmation

No commits, tags, pushes, or PRs were created. All changes remain in the
working tree: `src/ingestion/pruning.py`, `scripts/rebuild_assets.py`,
`scripts/prune_stale_artifacts.py`, `tests/test_pruning.py`, plus this report.