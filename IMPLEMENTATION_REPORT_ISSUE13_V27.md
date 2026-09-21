# Issue #13 V2.7 Implementation Report — Provenance Retention & Automatic Cleanup

**Status:** Implemented, full regression green, no commits/pushes made.
**Date:** 2026-09-20

---

## 1. Root cause

Every `/query` (and every ingestion event) persists a provenance record via
`ProvenanceStore.save()` into `data/provenance/`. Nothing ever expires or
removes these files, so long-running deployments accumulate thousands of
provenance files with no bound on age or count:

- `src/llm/service.py:187` writes a record per answer.
- The store only offers `save` / `get` / `list_ids` — no retention.

Since V2.5 and V2.6 removed the duplicate-*ingest* leak, provenance is the last
unbounded storage sink in Issue #13.

## 2. Files modified

| File | Change |
|---|---|
| `src/config/settings.py` | New settings (policy + master switch + startup opt-in). |
| `src/llm/provenance.py` | New `ProvenanceCleanup` result type, `_is_provenance_record`, `_retention_survivors`, `ProvenanceStore.cleanup()`, and module-level `cleanup_provenance()`. |
| `src/main.py` | Optional, non-fatal startup cleanup hook (`PROVENANCE_CLEANUP_AT_STARTUP`). |
| `scripts/rebuild_assets.py` | New step [0b] runs provenance retention before building graph/vector assets. |
| `scripts/cleanup_provenance.py` | **New.** Standalone CLI with `--directory`, `--retention-days`, `--max-files`, `--dry-run`. |
| `tests/test_provenance_cleanup.py` | **New.** 11 tests covering the required scenarios. |

No retrieval, generation, embedding, ranking, confidence, routing, parser,
hierarchy, or canonical-ID behaviour changed. Pre-existing lint in
`scripts/rebuild_assets.py` (mid-file `import json`, two over-long print
lines) was cleaned as the file was being touched.

## 3. Cleanup algorithm

**Policy** (`src/llm/provenance.py`, defaults from settings):

- `PROVENANCE_RETENTION_DAYS = 30`
- `PROVENANCE_MAX_FILES = 5000`
- `PROVENANCE_CLEANUP_ENABLED = True` (master switch; rebuild + script honor it)
- `PROVENANCE_CLEANUP_AT_STARTUP = False` (app-startup cleanup is opt-in)

**Scope guard — only provenance artifacts.** Cleanup operates exclusively on a
provenance directory and considers only files that are genuine persisted
records: valid JSON whose top level contains a `provenance_id`. Anything else
— processed/hierarchy/canonical JSON, evaluation outputs, corrupt or
unrelated files — is never a candidate, even if it lives in the same
directory or carries an old mtime.

**Selection — newest always survive.** For the candidate set
`_retention_survivors(...)` returns the union of:

1. records whose mtime is inside the retention window (age rule), **or**
2. the `max_files` newest records (count rule).

A record is removed when it is older than the window **and** ranks outside the
newest `max_files`. Each rule is disabled when its setting is `<= 0`; if both
are disabled nothing is ever removed. Un-stat-able records are always kept.

**Idempotency.** The survivor set is a deterministic function of the on-disk
records, so after a run the survivors are exactly the retained set and a
second run removes zero files (verified, §5).

**Logging.** Uses the structured `provenance` logger and mirroring stdout
lines, exactly as specified:

```
provenance.cleanup.start
provenance.cleanup.remove   per removed record
provenance.cleanup.remove_failed (on unlink error)
provenance.cleanup.complete removed=X remaining=Y
```

`cleanup(..., dry_run=True)` reports removals without deleting anything.

## 4. Before vs After counts

- **Real deployment (read-only dry-run, current settings):** `data/provenance`
  holds **201** records; default policy (30 days / 5000 files) removes **0**
  and keeps **201** — non-destructive under the shipped defaults, and the
  count rule engages once a deployment crosses 5,000 records.
  - 80 of the 201 records are already older than 30 days, so limiting
    `PROVENANCE_MAX_FILES=100` (for example) would project: remove **80**,
    remaining **121** (the 121 records younger than 30 days).
- **100-file synthetic benchmark (§5):** `100 → 55 removed, 45 remaining`.

Other directories are unaffected: `data/processed` and `data/hierarchy`
artifact counts are unchanged by this feature (cleanup never touches them).

## 5. Runtime verification

Synthetic scenario matching the spec — 100 provenance records: 60 older than
the 30-day window (40–49 days) and 40 fresh (1–10 days), cleaned with
`retention_days=30, max_files=45` on a temp directory:

```
BEFORE:                  files = 100
AFTER FIRST RUN:         removed = 55   remaining = 45
  all 40 fresh records preserved        = True
  newest 5 old records preserved        = True (count rule)
  old removed immediately               = True
AFTER SECOND RUN:        removed = 0    remaining = 45
VERDICT: PASS
```

Second-run zero removals confirms idempotency. The standalone CLI smoke test
(`python scripts/cleanup_provenance.py --dry-run`) executed the full
start/remove/complete sequence against `data/provenance` and reported
`removed=0 remaining=201 dry_run=True`. `py_compile` passes for all touched
scripts, and the app module imports cleanly under the default flags
(`enabled=True, days=30, max=5000, startup=False`).

## 6. Test results

`tests/test_provenance_cleanup.py` (11 tests):

- ✓ retention by age — old records removed, fresh kept
- ✓ retention by count — only the newest `max_files` survive
- ✓ mixed old/new provenance — age + count rules combined, newest always kept
- ✓ disabled cleanup — `enabled=False` removes nothing
- ✓ canonical artifacts untouched — canonical/hierarchy/eval-shaped JSON (old
  mtimes, no `provenance_id`) inside the same directory survive byte-for-byte
- ✓ only its own directory — records in an unrelated dir are never considered
- ✓ non-provenance files never deleted — random JSON, corrupt JSON, `.txt`
- ✓ idempotent rerun — second run removes 0
- ✓ dry-run — reports removals without deleting
- ✓ empty directory — 0/0
- ✓ store without a directory — 0/0, no crash

Full suite:

```
1032 passed, 5 warnings in 83.30s   (1021 before this change, +11 new)
```

Lint & format (all changed/new files):

```
ruff check   src/config/settings.py src/llm/provenance.py src/main.py
             scripts/rebuild_assets.py scripts/cleanup_provenance.py
             tests/test_provenance_cleanup.py        → All checks passed!
ruff format --check (same set)                       → All files already formatted
```

## 7. Risks

- **Deletion is permanent.** The count rule can remove records once a
  deployment exceeds `PROVENANCE_MAX_FILES`. Mitigations: retention age ties
  into record mtime; the newest files and every record in the window always
  survive; `--dry-run` lets operators preview; a single master switch
  (`PROVENANCE_CLEANUP_ENABLED=False`) completely disables cleanup.
- **Blocking-sync startup cleanup** is served by the opt-in flag; when left
  off there is no behaviour change at boot. When enabled it runs once,
  wrapped in try/except so a failure can never prevent the app from starting.
- **mtime as the age clock.** Records with manipulated/restored mtimes get
  non-deterministic treatment; this is inherent to the "last modified"
  retention model requested.
- Rebuild now spends a little extra time scanning `data/provenance` (JSON
  parse per record). At thousands of records this is sub-second to a few
  seconds of wall time during an explicit rebuild — acceptable for a manual
  operation.

## 8. Remaining limitations

- Startup cleanup is deliberately opt-in; automation teams must set
  `PROVENANCE_CLEANUP_AT_STARTUP=true` to activate it.
- The retention clock is mtime, not the query timestamp embedded in the
  record — an explicitly-restored old file counts as aged.
- Age-based removal is bounded by `PROVENANCE_MAX_FILES` regardless: the code
  can never remove a record that ranks inside the newest `max_files`, so "keep
  latest" always wins over "older than N days."
- The `PROVENANCE_MAX_FILES` default (5000) keeps the current corpus intact
  (201 records); growth beyond that is where the count rule begins to work.
- Orphan uploads and provenance-per-query volume are fixes 3–4 of Issue #13
  and remain out of this change's scope.

## 9. Commit/push confirmation

No commits, tags, pushes, or PRs were created. All changes remain in the
working tree: `src/config/settings.py`, `src/llm/provenance.py`,
`src/main.py`, `scripts/rebuild_assets.py`, `scripts/cleanup_provenance.py`,
`tests/test_provenance_cleanup.py`, plus this report.