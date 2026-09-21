# V2.4.2 Investigation Report — Dense-Retrieval Mechanism, Weight Optimality, and the Rape Top-Slot Flake

**Scope:** Investigation-only (Obj 1–4 of the post-V2.4.1 review) + one minimal determinism fix. **No changes** to the parser, hierarchy generation, canonical ids, citation scoring, propagation, confidence guard, grounding logic, embeddings provider, section routing, or ranking weights (`DEFAULT_RANKING_WEIGHTS` unchanged). One code touch: a deterministic sort of the exact-numbering promotion list (`src/llm/explanation.py:783`). No commits/pushes.
**Baseline:** V2.4.1 report — expansion enabled + enlarged lexicon carried theft/murder/robbery/cheating/offer/acceptance/consideration/breach to GENERATE, but (a) dense stayed concept-insensitive, (b) weights were swept under a fixed ON configuration, (c) rape §375 still flaked between evidence[0]=`i` (conf 0.24, blocked) and evidence[0]=§375 (conf 0.80, generated), and (d) ICA queries returned `status="supported"` while `validity.is_valid=false` diverged.
**Method:** deterministic in-memory canonical corpus (ICA `0d1934142f67c5f5` 205 nodes, IPC `cf20a14c52127fd5` 544 nodes, 749 indexed points) under `EMBEDDING_FORCE_DETERMINISTIC` + `QA_INDEX_IN_MEMORY`, `budget = 10`. Three probe scripts (`investigate_dense.py`, `investigate_weights.py`, `investigate_rape.py`) reproduce the exact `explain()` pipeline; verdicts use the actual service guard predicate.
**Date:** 2026-09-19

---

## 1. Dense retrieval is conceptually insensitive — mechanism confirmed in code and empirically (Obj 1)

### 1.1 Provider mechanism (`src/retrieval/providers.py:32–63`)

`DeterministicEmbeddingProvider` computes a **64-dimensional bag-of-words token hash**:

- token stream = lowercase word split + statute `Extractor._SENTINEL_PATTERNS` (section-number sentinels such as `S{'378'}` fired on explicit section queries only); no stopwords, no stemming, **no IDF**; word pieces with length ≥ 3 hashed via `blake2b(token).digest() % 64`, sign trick on byte index, accumulated, L2-normalised.
- Result: embeddings encode *token-shape collisions*, not meaning. Cosine similarity responds to shared words and hash collisions, so long generic sections (portal/chronology clauses) dominate short concept queries.

### 1.2 Empirical invariance (plain dense, expansion off, IPC)

| Query | plain-dense top-10 (num, score) | gold rank |
|---|---|---|
| What is theft? (gold §378) | 84(.6494),85(.6239),41(.6173),23(.6168),63(.6147),114(.6116),CH.I(.6091),77,95,**378** | 378@10 |
| What is murder? (§300,§302) | 84,85,41,23,63,114,CH.I,**300**(.6131),303,77 | 300@8, **302 absent** |
| What is robbery? (gold §390) | 84,85,41,23,63,114,CH.I,77,**390**,116 | 390@9 |
| What is rape? (gold §375) | 376,84,85,41,23,63,114,CH.I,77,95 | **375 absent** |
| What is cheating? (§415,§420) | 84,85,41,23,63,114,CH.I,77,95,146 | **415/420 absent** |

Invariant core across all five concept queries: **§84, §85, §41, §23, §63, §114, CHAPTER I, §77, §95** at cosine 0.60–0.65. Theft's top-10 shares 8/10 with robbery, 8/10 with murder, 9/10 with rape, 9/10 with cheating. Each top-10 contains exactly **one** non-section hit (a chapter/doc header). Dense cannot distinguish concepts at the top of the list.

**Decisive counter-evidence:** §375 node `n_0548` carries **2305 chars of the actual rape definition** yet scores `dense=0.0` for every formulation; meanwhile §84 ("What is an unsound mind…", 219 chars, no crime semantics) sits at #2 for "What is the punishment of rape and seduction?" queried in earlier V2.4 testing and is #1–2 here. Dense ranking is thus *insensitive to criminal-law content*.

### 1.3 Why gold sections rank low/absent

The invariant core (portal/chronology/definitional sections) uses the same high-frequency vocabulary as the queries (`is`, `any`, `person`, `who`, `what` collide in 64 bins); a gold section must be both highly similar *and* survive the genre-heavy candidates. Expansion injection lifts content terms for 6/8 recovered concepts (theft/murder/robbery/cheating move up), but rape §375 still never reaches the dense top-10 under any configuration — dense contributes `0.0` even when graph/citation carry it to the final top-2.

## 2. Ranking weights: no change warranted under the fixed ON configuration (Obj 2)

`src/config/settings.py:43–47` — `RANKING_WEIGHT_DENSE=0.35`, `GRAPH=0.25`, `HIERARCHY=0.15`, `KEYWORD=0.15`, `CITATION=0.30`. Swept 8 configs × 11 queries (8 IPC concepts + 3 ICA), expansion OFF and ON:

| Config | expansion | Top-1 | Top-3 | MRR | R@5 | R@10 |
|---|---|---|---|---|---|---|
| **current** 0.35/0.25/0.15/0.15/0.30 | **ON** | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |
| no_hierarchy 0.35/0.25/0/0.15/0.30 | ON | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |
| no_keyword 0.35/0.25/0.15/0/0.30 | ON | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |
| **no_citation** 0.35/0.25/0.15/0.15/0 | ON | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |
| flat 0.20/0.20/0.20/0.20/0.20 | ON | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |
| keyword_heavy 0.25/0.15/0.20/0.30/0.10 | ON | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |
| dense_heavy 0.50/0.20/0.10/0.10/0.10 | ON | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |
| graph_heavy 0.20/0.40/0.10/0.10/0.20 | ON | 0.5455 | 1.0000 | 0.9091 | 1.0000 | 1.0000 |

**With expansion ON all 8 configs are bit-identical** (identical metrics, identical per-query gold ranks) because the C7 exact-numbering promotion (`explanation.py:781–785`) dominates the final order; the five weighted signals only tie-break inside non-promoted tail. The matching `current` dict, or any config, degenerates to the same output. **With expansion OFF** weights matter: `current` gives Top-1 .1818 / Top-3 .7273 / MRR .5054; `no_citation` is strictly better (Top-1 .4545, MRR .7251) and `flat`/`keyword_heavy` also beat it — but OFF is not a production mode.

**Conclusion:** no weighting change is recommended under the fixed ON configuration; the weights dict is confirmed in sync with `settings.py`. The lever with real headroom is the dense provider (§1), explicitly out of scope.

## 3. Rape top-slot flake: root cause found and fixed (Obj 3)

### 3.1 Symptom

"When someone is raped…" flips cross-process: sometimes `evidence[0]="i"` → relevance 0.0104 → conf 0.2447 → **BLOCKED**; sometimes `evidence[0]=§375` → relevance 1.0 → conf ≈ 0.80 → GENERATE. Reproducible in-process but not cross-process.

### 3.2 Root cause

- Per-node signals are **identical across processes** (dense 375=0.0, graph 375=0.242, keyword 375=0.25, citation 375=1.0, rank 375=0.3317; §376 n_0551 rank 0.4419, n_0235 rank 0.4067). Only the **order of the C7-promoted exact matches** differs: `exact_matches = [nid for nid in candidates if _exact_numbering_match(nid)]` iterated the Python `set` `candidates`, whose iteration order depends on the process's random hash seed (`PYTHONHASHSEED`), then `ranked_ids = exact_matches + rest` prepended it verbatim.
- For rape, C7 promotes three nodes: n_0551 (376, rank 0.4419), n_0235 (376, rank 0.4067), n_0548 (§375, rank 0.3317). **n_0553 (`i`)** is a *sub_clause* (numbering `i`, text_len 3252) — the resolved text-bearing descendant of the §376 wrapper n_0551 (title "Punishment for rape", **text_len 0**). Whenever n_0551 lands first, evidence[0] resolves through the empty wrapper to `i`, relevance 0.010 → blocked. When §375 wins the tie, relevance 1.0 → generated.

### 3.3 Fix applied (`src/llm/explanation.py:783`)

```python
exact_matches.sort(key=lambda nid: (-rank.get(nid, 0.0), nid))
```

before `ranked_ids = exact_matches + rest` (L784–785). Promotion is now deterministic and rank-consistent; the `(nid)` tie-breaker makes byte-stable output across runs and languages. No behavioural predicate changes.

### 3.4 Verification (3 fresh processes post-fix)

All three processes report identical output: `promoted = [376/n_0551, 376/n_0235, 375/n_0548]`, `evidence_first6 = [n_0553('i'), n_0235, n_0548, ...]`, `conf=0.2447`, `rel=0.0104`, `dup=0`. The coin-flip is gone.

**Transparency:** the deterministic outcome is the *conservative* one — rape is now reproducibly BLOCKED (conf 0.24) because §376 rank 0.4419 > §375 rank 0.3317, and §376 wrapper resolves to `i`. This is a reproducibility gain, not a substantive rape fix: the section still needs to reach `evidence[0]`, which only a content-aware dense provider (§1) can reliably achieve — out of scope. The V2.4.1 report's flake is resolved into a stable, documented state.

## 4. `validity.is_valid=false` vs `status="supported"` divergence: explained, no change (Obj 4)

- Downstream consumers of `validity.is_valid` / `has_conflicts` (grep, 26 hits): `eval/harness.py:143`, `src/evaluation/runner.py:61,175`, `scripts/run_final_evaluation.py:424,557`, `src/llm/schemas.py:98,100`, `src/llm/provenance.py:144,146`, the explanation chain `explanation.py:866–869`, and tests. **None gate answer generation** — the guard inspects `status=="supported"`, relevance, sufficiency, confidence; `is_valid` is informational/API/metric-only.
- Trigger: `_detect_counter_authorities` (`explanation.py:1432`) substring-matches evidence text against `_COUNTER_MARKERS` (`explanation.py:324–332`, incl. overruled/superseded/repealed/overridden, "void ab initio", "declared void", "not enforceable", "invalid", "does not apply"; `_STRONG_MARKERS={"overruled","superseded","repealed","overridden"}`). ICA definition text such as *"Agreement without consideration is void"* fires `has_conflicts=True` → `is_valid=False` even though no counter-authority exists. The comment `"preserved from old logic for diagnostics"` (`explanation.py:2070`) marks it intentional.
- **No change recommended:** altering counter-authority semantics is outside the retrieval task and could regress genuine overruled/repealed detection.

## 5. Test results

Full suite post-fix: **988 passed** in 88.5s, no regressions. `tests/test_qa_api.py:351–377` asserts only shape/type of the promoted-exact-matches list, not order — compatible with the sort.

## 6. Files touched

| # | File | Change | Location |
|---|---|---|---|
| 1 | `src/llm/explanation.py` | Deterministic, rank-consistent sort of exact-numbering promotion | L783 |
| 2 | `IMPLEMENTATION_REPORT_ISSUE11_V242.md` | this report | — |

No commits/pushes performed.

## 7. Deliverable summary

- **Root cause dense insensitivity:** §1 (64-dim BOW hash provider; invariant core 84/85/41/23/63/114/CH.I/77/95; §375 dense=0.0 with 2305 chars of content).
- **Weight optimality:** §2 (zero weight sensitivity under ON; `current` matches `settings.py`; no change).
- **Rape flake root cause + fix:** §3 (set-iteration nondeterminism in C7 promotion → deterministic sort; now stable at the conservative blocked state).
- **Validity divergence:** §4 (informational-only conflict marker; no generation gate; no change).
- **Test results:** §5 (988 passed).
- **Remaining limitations:** dense provider still content-blind (rape §375 absent from dense top-10 under every config) — the substantive fix would require embedding-side work, out of scope by constraint.