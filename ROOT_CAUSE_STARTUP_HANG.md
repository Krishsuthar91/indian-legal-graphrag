# ROOT CAUSE — Startup Hang After the Semantic-Embedding Migration (V3.0)

**Date:** 2026-09-21 · **Component:** backend boot (`build_default_corpus` + `main._prewarm_*`)
**Reproducer:** `uvicorn src.main:app` → server binds *late*, frontend gets `ECONNREFUSED`/500,
QA unable to answer "What is murder?"; cold boot took ~17 minutes (pure-CPU `fp32` encode).

> Scope of this fix is deliberately minimal: **startup time + boot reliability only**. Retrieval,
> dense/graph/hierarchy ranking, confidence/sufficiency verification, citations, routing, and
> deterministic-test behavior are untouched by design (verified: 1041→1046 tests pass, 0 regressions).

---

## 1. What the hang actually was

The *measured* root cause is **not a lock, not a Qdrant/Neo4j/LLM problem, and not a deadlock** —
it is catastrophic single-core-bound CPU throughput of the migration's default model
(`BAAI/bge-m3`, fp32, no GPU discovered). The corpus finished, but only after ~17 minutes, and
the app was designed to pay that cost **at startup, every boot** (in-memory Qdrant is the default
`QA_INDEX_IN_MEMORY=true`), with frontend probes timing out long before.

Audit measurements of the unmodified `build_default_corpus` (CPU, torch 2.14):
before fix: full inline encode **1025.8 s**; sections collection (696 texts) alone **925.5 s**.

Levers measured on this box (AMD Ryzen 7, 6 core / 12 thread, no AVX-512):
- threads=1 → **0.3 texts/s**; threads=6 → **0.8–0.9 texts/s** (torch spawns 6 helper threads; cores saturate ~800%).
- batch_size 16 ≈ 32 (throughput flat); length-*stratification* is the only real lever.
- `bf16` never benchmarked (timed out at ~17 min + model load); report limitation below.

The **second failure amplifying the hang**: `main._prewarm_corpus` awaits an
`asyncio.to_thread(...)` with a `wait_for(_PREWARM_TIMEOUT_SECONDS=300)`; when the 300 s deadline fires on a
17-minute build, **`to_thread` cannot cancel the worker**. The orphan thread keeps holding the corpus
build (`RLock`), so `_prewarm_service` then blocks *another* 300 s on the same lock, port binding lands
late, and any concurrent query blocks on the same lock → frontend sees `ECONNREFUSED`/500. Together:
a cold boot that *must* spend ~17 min re-embedding, further wedged by double 300 s waits and a
non-cancellable orphan thread.

```
before fix (cold, in-memory corpus, CPU bge-m3):
  embedding.generate.complete   elapsed_s=925.5   texts=696        (sections, the >90% cost)
  full encode (all node kinds)  elapsed_s=1025.8
  wallclock (incl. model load + graph build)       ~17 min         → /health late, /query 500/refused
```

---

## 2. Files changed

| File | Change | Why |
|---|---|---|
| `src/config/settings.py` | `EMBEDDING_SNAPSHOT_ENABLED`, `EMBEDDING_SNAPSHOT_DIR` | Gated, configurable snapshot storage |
| `src/embeddings/service.py` | **length-stratified encoding** (longest-first within batch order, order-restored) + `embedding.batch.progress` logs + stratified flag/elapsed on start/completed | Closes the padding blowup; progress visibility so a warmup is never "looks dead" |
| `src/embeddings/indexer.py` | `index_graph`/`_index_nodes` accept `existing` map; skip nodes whose `text_hash` already exists in the store (per collection) | **Incremental re-indexing** — second run embeds nothing fresh |
| `src/embeddings/store.py` | gzip-JSON `save_snapshot`/`load_snapshot` (atomic tmp + `os.replace`), `_snapshot_path` anchored to repo root, scroll `with_vectors=True`, `indexed_payloads`/`count` helpers | On-disk embedding snapshot for instant warm boots |
| `src/llm/service.py` | `_embedding_cache_key`; warm-from-snapshot in `build_default_corpus` (load → `index_graph` incremental → save); `_build_in_progress` flag + `is_default_corpus_ready`/`corpus_build_in_progress` | The actual boot fix (see §3) |
| `src/main.py` | `_prewarm_service` early-returns `service.prewarm.deferred` when corpus still warming | No *second* 300 s block; the orphan `to_thread` no longer wedges prewarm |
| `src/api/qa.py`, `src/api/documents.py` | Readiness gate `_await_corpus_ready` → **503 JSON "warming"** while corpus builds (grace ~3 s), only when `service_factory is get_default_service` and a build is in progress | No more 500/`ECONNREFUSED`/refused for the frontend during cold boot |
| `.gitignore` | ignore `data/embeddings/`, `data/indexing/` | Keep the generated DB artifacts out of git |
| `tests/conftest.py` | session fixture pins deterministic + snapshot-off during tests; `client` fixture permission-correct | Hermetic suite |
| `tests/test_startup_repair.py` | **5 new regression tests** (snapshot round-trip, stale-key skip, second-index embeds nothing, QA 503-warming gate, 503 not triggered when not building) | Locks in the fix |

---

## 3. The fix, end-to-end

`build_default_corpus` now:
1. computes an embedding **cache key** from (provider, dim) — exactly the run-time identity of vectors.
2. **loads the snapshot** (if enabled) — near-instant on warm boot.
3. calls `index_graph(canonical_doc_ids=…)`, which now **skips any node whose `text_hash`
   already exists** in the collection — so after a snapshot restore nothing is re-embedded.
4. saves the snapshot back after indexing, so even boot-after-crash work is persisted incrementally.

And the server prewarm path: `_prewarm_service` returns immediately with `service.prewarm.deferred`
when the corpus is still being built (cold start), and QA/document endpoints answer with a **clean
503 JSON** (not a 500 / connection-refused) while the corpus warms.

---

## 4. Before / After timing (same machine, same torch 2.14 CPU stack)

**Cold build (no snapshot) — stratification is the lever:**
```
                     before fix        after fix       Δ
sections (696)       925.5 s           558.49 s        1.66× faster
full encode          1025.8 s          669.6 s         1.53× faster
build_default_corpus ~17 min           ~11.9 min       —5 min
```
Stratification: 696 section texts → **22 batches of 32** (last batch 8); longest texts embedded
first; ~1.2–1.5 s/text for the longest, sub-second for short clauses. Vector **order restored**
after encode, so downstream dense ordering is unaffected.

**Warm boot (snapshot exists) — the actual fix:**
```
  snapshot_restored    key=BAAI_bge-m3_1024d_512 points=749
  index_graph          embeds NOTHING (collections={} elapsed_s=0.02)
  build_default_corpus DONE  wallclock_total≈21.6 s   (was ~17 min)
  /api/v1/health       200 @ ~18 s boot
  /api/v1/query        "What is murder?" → 200, full retrieval+verification+citations JSON
```
Snapshot: `data/embeddings/snapshot_BAAI_bge-m3_1024d_512.json.gz`, 749 points (7.3 MB), restored
per-point on warm boot. Second+ starts now complete in well under a minute (cold: ~17 min).

---

## 5. Verification

- `pytest` **1046 passed, 0 failed** (baseline 1041 → +5 new repair tests; the pre-existing
  qdrant-client version-check warning is unrelated).
- Cold run seeds snapshot: 749 points saved, `index_graph_complete elapsed_s=669.64`.
- Warm run: `snapshot_restored points=749`, `index_graph collections={} elapsed_s=0.02`.
- Real server: `/api/v1/health` → 200; `/api/v1/query {"query":"What is murder?"}` → 200 JSON with
  `section_refs`, `citations`, `hierarchy_paths`, `confidence` + verification reasoning chain.
- `tests/test_documents_api.py::test_startup_prewarms_corpus_once_and_first_upload_reuses_cache`
  (warm path) and the lazy `get_default_service` no-uploads test (always-200 when not building) still pass.

---

## 6. Risks / notes

- **Cold first run is still slow**: with no snapshot, expect ~11–17 min (CPU bge-m3 is the physics
  floor; not solvable in software without a GPU / quantized provider). During that window the API
  answers **503 "still indexing" JSON** — deliberate, so the frontend can poll and never sees a 500.
  Ship a seeded snapshot (or run one build before deploy) to make every boot warm/near-instant.
- **Snapshot invalidation**: the cache key includes provider + dim + max-sequence, so a model/dim/
  `EMBEDDING_MAX_SEQUENCE_LENGTH` change produces a different key/file automatically. Changing a
  provider but keeping the same key/dim on purpose is the only manual-clear risk.
- **Snapshot storage uses stdlib gzip+json** (not numpy) — the env has no numpy; deterministic
  test provider writes through the same path. Large real-model snapshots take ~4 s to save and a
  couple of seconds to restore.
- **Environment**: torch 2.14.0+cpu, torchaudio 2.11.0+cpu, sentence-transformers 5.6.1,
  transformers (4.57 pinned — transformers 5.x hard-imports torchaudio and its cu128 wheel doesn't
  load on this CPU-only box; 4.57 satisfies sentence-transformers' `>=4.41,<6` constraint with no
  audio hard-dependency).
- **Limitations**: memory measurement via `ctypes` returned 0 (module_getloadavg fails on Windows)
  — no peak-RSS numbers; `bf16` untested (full run exceeded the benchmark timeout); batching at
  `bs=32` with `threads=6` is the empirical sweet spot, but only ~1.25–2.2× of a single-thread run,
  so **do not expect CPU fp32 to ever become "fast"** — snapshot seeding is what makes boot fast.

---

## 7. Summary

The hang was **CPU-bound embedding throughput** (bge-m3 fp32, ~1 min per 32-text batch) paid at
every startup because the in-memory Qdrant index is rebuilt from scratch each boot, aggravated by a
**non-cancellable `asyncio.to_thread`** worker that orphaned the corpus-build `RLock` and added a
second 300 s prewarm block. The fix makes cold builds ~5 min faster (length stratification proves
~1.66× on the dominant collection) and, crucially, makes **every later boot warm** via an on-disk
embedding snapshot + incremental text-hash indexing (17 min → ~20 s), with clean 503 "warming"
responses instead of 500/refused during any cold start. No retrieval/ranking/confidence/citation
behavior changed.
