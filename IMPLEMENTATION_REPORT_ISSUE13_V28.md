# Issue #13 V2.8 Implementation Report — Persistent Qdrant Vector Synchronization

**Status:** Implemented, full regression green, no commits/pushes made.
**Date:** 2026-09-20

---

## 1. Root cause

When `QA_INDEX_IN_MEMORY == False` (server-backed or local-persistent Qdrant),
every corpus rebuild ran `HierarchyIndexer.index_graph()`, which only *adds* or
*overwrites* points. Nothing ever removed vectors that no longer correspond to a
graph node. Over repeated rebuilds after deletions or restructurings, a
persistent Qdrant silently accumulates **stale vectors** (e.g. points left
behind by hierarchy nodes removed by the V2.6 duplicate pruning). The same
`index_graph` path also **failed hard on a dimension change**: upserting after an
embedding-model dimension bump raises a Qdrant dimension-mismatch error,
because the stored collections' vector size no longer matches the new model and
nothing recreated them.

Before this change:

- No production code path ever called `sync_graph` (it existed unused) and
  `QdrantStore` offered no dimension inspection or recreation.
- `index_incremental` computed but discarded per-node *inserted/updated*
  results, so a sync could not report what it did.
- `build_default_corpus` (`src/llm/service.py`) was the only entry point and
  hard-wired `index_graph(canonical_doc_ids=...)`.

## 2. Files modified

| File | Change |
|---|---|
| `src/embeddings/store.py` | `QdrantStore(path=...)` local-persistent mode tracked on-disk. New `collection_dimension(name)` (single size → size; named/multivector or missing → `None`). New `recreate_collection(name)` — delete + create with current dim, with Windows-safe physical cleanup of the embedded collection directory. |
| `src/embeddings/indexer.py` | `index_incremental` returns `inserted`, `updated`, `collections_inserted`, `collections_updated` (old `indexed`/`skipped`/`collections` keys preserved). `sync_graph(node_ids=None, *, recreate_on_dimension_mismatch=False)` rewritten: insert missing, update changed `text_hash`, delete stale, recreate exactly once on dimension change, `vector.sync.*` events (structlog + mirroring stdout). Backward compatible with `test_indexer`. |
| `src/llm/service.py` | `build_default_corpus` branches: `QA_INDEX_IN_MEMORY=True` → unchanged `index_graph(canonical_doc_ids=...)`; `False` → `indexer.sync_graph(recreate_on_dimension_mismatch=True)` wrapped in `qa_service.sync_graph_start/complete` logs. |
| `tests/test_vector_sync.py` | **New.** 9 tests covering the required scenarios. |

No retrieval, generation, ranking, confidence, routing, parser, hierarchy, or
canonical-ID behaviour changed. `scripts/rebuild_assets.py` intentionally still
builds its assets in-memory (`in_memory=True`) and is untouched.

## 3. Sync algorithm

**Scope — the full current graph.** `sync_graph()` enumerates every graph node
from the freshly-rebuilt in-memory graph (`import_all` over `data/hierarchy`,
which includes uploaded documents). It is *not* restricted to canonical
document ids: snapshotting only canonicals would delete every vector belonging
to uploaded documents. Stale is defined as *a point whose `node_id` is not
present anywhere in the current graph* — exactly the vectors orphaned by
deletions and by V2.6-pruned duplicate hierarchies. Canonical ids are therefore
always preserved (unless the document itself is deleted from the corpus).

**Per-node triage** (per collection):

| Current point | `text_hash` equal | Action |
|---|---|---|
| none | — | **insert** |
| exists | yes | leave untouched |
| exists | no | **update** (re-embed, overwrite) |
| graph node gone from all collections | — | **delete** |

**Dimension change — recreate exactly once.** For each collection,
`collection_dimension(name)` reads the stored vector size. If it does not match
the current store dimension and `recreate_on_dimension_mismatch=True`, the
collection is deleted and re-created with the current dimension, logged once as
`vector.sync.recreate` (stored vs expected size + reason), and every node is
re-indexed into the fresh collection. If the flag is `False`, the mismatch is
reported (not raised) and nothing is recreated. Embedded-local mode additionally
clears the collection's on-disk data directory between delete and create
(`gc.collect()` + rmtree): on Windows the client's own `delete_collection`
rmtree can silently fail while the collection's sqlite handle is still open,
which would otherwise "resurrect" the old points — and old vector arrays —
under the re-created name (proven in §5).

**Idempotency.** A sync is fully deterministic: unchanged points are detected
by `text_hash` and skipped, so a second run performs zero writes.

**Logging.** `vector.sync.start`, `vector.sync.recreate`, `vector.sync.insert`
(per collection batch), `vector.sync.update`, `vector.sync.delete`,
`vector.sync.complete` (counts of inserted/updated/deleted/unchanged/recreated)
— structured logger + mirroring stdout, matching the `provenance.cleanup.*`
convention from V2.7.

**Result dict:** `{inserted, updated, deleted, unchanged, recreated, indexed,
skipped, collections_inserted, collections_updated, collections}`.

## 4. Before vs After counts

Verified against a **temporary persistent (embedded on-disk) Qdrant instance**,
exactly as the requirement asks:

```
STEP 1  index a 100-section corpus       100 section vectors + 1 document   = 101 total
STEP 2  delete node s0100, sync          deleted=1 inserted=0 unchanged=100 → 100 total
STEP 3  rerun sync                       deleted=0 inserted=0 updated=0     → 100 total
STEP 4  reopen at dim 16, sync           recreated=4 inserted=100 deleted=0  → 100 total
STEP 4b rerun sync                       recreated=0 inserted=0 updated=0    → 100 total
VERDICT: PASS
```

- Stale removal: **101 → 100** after one node deletion.
- Idempotency: the second run makes **zero** changes.
- Dimension recreation: all **4** collections recreated exactly once
  (documents/chapters/sections/clauses → dim 16), all 100 vectors re-indexed,
  second re-sync recreates **0**.
- In-memory mode (the default deployed behavior): `sync_graph` is never used;
  `index_graph()` behavior and vector counts are unchanged (full suite proofs).

## 5. Runtime verification

`verify_vector_sync_v28.py` (temp, not committed) drove the store + indexer
through the §4 scenario against `QdrantClient(path=...)`. Live events captured
from that run:

```
vector.sync.start    nodes=100 collections=['documents','chapters','sections','clauses']
vector.sync.delete   collection=sections count=1
vector.sync.complete inserted=0 updated=0 deleted=1 unchanged=100 recreated=0
vector.sync.start    nodes=100      (second run)
vector.sync.complete inserted=0 updated=0 deleted=0 unchanged=100 recreated=0
vector.sync.recreate collection=documents stored_dim=32 expected_dim=16 reason=dimension changed
vector.sync.complete inserted=100 updated=0 deleted=0 unchanged=0 recreated=4
vector.sync.complete inserted=0 updated=0 deleted=0 unchanged=100 recreated=0   (re-run)
```

The local-persistent recreate path was hardened against the embedded-mode quirk
(see §3). The `recreate_collection` on-disk cleanup was independently proven
with a focused scratch script: seed 5 points @ dim 32 → client `delete_collection`
leaves the data dir present on Windows → `gc.collect()` + forced rmtree removes
it → `create_collection` @ dim 16 → new collection is genuinely empty → upsert
of a 16-dim vector works and persists across a reopen (count=1, dim=16).

## 6. Test results

`tests/test_vector_sync.py` (9 tests):

- ✓ insert missing vector (`sync_graph` after adding a node → `inserted=1`)
- ✓ delete stale vector (node removed → `deleted=1`, count drops)
- ✓ unchanged vectors preserved byte-for-byte (`unchanged=6`, payloads equal)
- ✓ changed text re-indexed (`updated=1`)
- ✓ second sync idempotent (0/0/0)
- ✓ dimension mismatch → collections recreated once and fully re-indexed;
  re-sync all-zero
- ✓ matching dimension → never recreated
- ✓ sync across a reopened persistent store (100 → 99 → 0, spec scenario)
- ✓ in-memory store ignores a persistence `path` (no directory, no collections)

Full suite:

```
1041 passed, 5 warnings in 74.44s   (1032 before this change, +9 new)
```

Targeted rerun after formatting: `tests/test_vector_sync.py
tests/test_indexer.py tests/test_embeddings.py` → 57 passed.

Lint & format (all changed/new files):

```
ruff check   src/embeddings/store.py src/embeddings/indexer.py
             src/llm/service.py tests/test_vector_sync.py   → All checks passed!
ruff format --check (same set)                              → All files already formatted
```

## 7. Risks

- **Dimension recreation deletes vectors that are still valid.** This is
  inherent: Qdrant collections cannot be resized in place. Mitigations: it
  triggers only on an actual stored-vs-current size mismatch, it is gated on
  `recreate_on_dimension_mismatch=True` (the persistent-rebuild path), the
  mismatch is logged with the reason, and everything is re-indexed from the
  freshly-built graph in the same rebuild — so no data is lost, only re-embedded.
- **Windows embedded-mode `delete_collection` silent rmtree failure.** Needs
  `gc.collect()` + explicit `shutil.rmtree` of the collection data directory to
  avoid "resurrected" points. Server-backed mode is unaffected; the explicit
  cleanup is a no-op there (no directory), and it is defensive (ignore_errors).
- **Scope is full-graph, not canonical.** A canonical document explicitly
  deleted from the corpus will correctly lose its vectors; that is the desired
  "stale removal" semantics.
- Rebuild now reads each collection's points once (delta scan) before
  upserting; at the corpus's scale this is negligible next to the embedding
  cost that dominates a rebuild.

## 8. Remaining limitations

- As before, `scripts/rebuild_assets.py` hard-codes `in_memory=True`, so vector
  sync only activates through `build_default_corpus` when
  `QA_INDEX_IN_MEMORY=false`. Operators who rebuild via the script still get an
  in-memory index.
- Dimension recreation cannot resize an existing collection in place; it is a
  delete + re-create + re-index cycle (the standard Qdrant operation).
- Full-graph sync intentionally treats every uploaded document present in
  `data/hierarchy` as in scope; an upload removed from disk no longer has a
  vector, which is the intended "stale = not in the corpus" definition.
- The runtime verification used the embedded local-persistent store (the
  "temporary persistent Qdrant instance"); a live Qdrant server was not
  available, but the verified code path is identical (`QdrantClient` API),
  minus the Windows-only extra cleanup.

## 9. Commit/push confirmation

No commits, tags, pushes, or PRs were created. All changes remain in the
working tree: `src/embeddings/store.py`, `src/embeddings/indexer.py`,
`src/llm/service.py`, `tests/test_vector_sync.py`, plus this report.