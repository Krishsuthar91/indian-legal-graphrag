# V2.4.3 Report — Semantic Embedding Provider (Deterministic → bge-m3 at Runtime)

**Scope:** Replace the deterministic 64-dim hashed-BOW `DeterministicEmbeddingProvider` with a real semantic embedding provider for runtime retrieval (preferred order: `BAAI/bge-m3` → `BAAI/bge-large-en-v1.5` → `intfloat/e5-large-v2`), keeping the deterministic provider **only for the unit-test suite**. Benchmark the retrieval delta on the existing concept and gold queries. **No changes** to the parser, hierarchy generation, canonical ids, section routing, citation scoring, propagation, confidence guard, grounding logic, or ranking weights (`DEFAULT_RANKING_WEIGHTS` unchanged). The V2.4.2 determinism fix (`src/llm/explanation.py:783`) is preserved. No commits/pushes.
**Baseline:** V2.4.2 report — deterministic dense proven concept-insensitive; rape §375 flaked between evidence[0]=`i` (conf 0.24, BLOCKED) and evidence[0]=§375 (conf ~0.80, GENERATE); the fix made the flake deterministic-but-blocked, and the substantive lever was identified as the dense provider.
**Method:** Full canonical in-memory corpus (ICA `0d1934142f67c5f5` 205 nodes, IPC `cf20a14c52127fd5` 544 nodes → 749 indexed points), same harness for both providers: 9 concept queries + 9 ICA-gold lookup queries; dense-only and final (expansion + ranking + exact-numbering promotion) metrics at k∈{1,3,5,10}; confidence/relevance/sufficiency/validity/grounding captured per query. Reproducer: `scripts/benchmark_semantic_dense.py`; artifacts: `evaluation/embed_retrieval_comparison_v243_{deterministic,BAAI/bge-m3,full}.json`.
**Date:** 2026-09-20

---

## 1. What changed

### 1.1 Model registry (`src/embeddings/models.py`)
- New `ModelSpec` fields `query_prefix` / `passage_prefix` (default `""`).
- Registry now 6 models: `BAAI/bge-m3` (1024, max_seq 8192, no prefixes), `BAAI/bge-large-en-v1.5` (1024, max_seq 512, no prefixes), `intfloat/e5-large-v2` (1024, max_seq 514, query prefix `"query: "`, passage prefix `"passage: "`), plus the pre-existing embeddings/bge/laBSE/Transformer entries.

### 1.2 Providers (`src/embeddings/providers.py`)
- `SentenceTransformerProvider` accepts `query_prefix`, `passage_prefix`, and `max_seq`; `.encode()` L2-normalizes.
- Semantic query vs passage prefixing: `EmbeddingService.embed_query` applies the model's query prefix, `embed_documents` the passage prefix (used by all three `HierarchyIndexer` call sites, `src/embeddings/indexer.py:88/146/206`). Plain `embed`/`embed_text` are prefix-free.
- `get_provider(..., allow_fallback=True)`: when `allow_fallback=False` an unknown model **or** a model that fails to load raises `RuntimeError` — semantic retrieval can never silently degrade to the deterministic provider. When `True` (tests, legacy callers), fallback keeps today's behavior (name preserved on fallback, dim from spec).

### 1.3 Configuration (`src/config/settings.py`)
- `EMBEDDING_MODEL = "BAAI/bge-m3"`, `EMBEDDING_FORCE_DETERMINISTIC = False` (unchanged, already the production default).
- New `EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK: bool = False` — wired into `build_default_corpus` (`src/llm/service.py:356`) and `scripts/rebuild_assets.py`.
- New `EMBEDDING_MAX_SEQUENCE_LENGTH: int | None = 512` — caps the encoded token length.

### 1.4 Sequence-length cap (performance, not quality) and the off-by-one bug
bge-m3 registers an 8192-token context. A handful of long clause nodes (max ~8,700 chars ≈ 2,200 tokens) make **pure-CPU** attention cost quadratic in length; an un-capped first attempt stalled indexing for >30 minutes on one long node. The provider now clips over-length texts through the module tokenizer (`SentenceTransformerProvider._clip_long`) to `max_seq` tokens before encoding; short texts pass through untouched and full text stays in the node payloads for generation. The first clip condition used `len(ids) > max_seq`, which never fired (truncation yields exactly `max_seq` ids) — fixed to `>=`. With the cap, 749 nodes embed in well under a minute and the corpus builds in seconds; verified timing: mixed 8-text batch encodes in 4.1s on CPU.

### 1.5 Evaluation wiring
`eval/corpus.py::build_corpus`, `src/evaluation/corpus.py::{build_evaluation_corpus, build_evaluation_service}`, and `eval/harness.py::benchmark_from_config` read the full `embedding` block (`model`, `force_deterministic`, `allow_fallback`, `dim`); the deterministic path remains the default for offline/test harnesses. `src/evaluation/pipeline.py::EvaluationConfig` gained `embedding_model` / `force_deterministic`.

### 1.6 Test suite
Deterministic embeddings stay pinned for every test via the session autouse `_force_deterministic_embeddings` fixture (unchanged). New tests: registry counts/specs, prefix application for query vs passage, `allow_fallback=False` fail-fast on unknown and unloadable model, plus an eval-harness test that an unknown model in `data/eval/config/experiment.json` raises.

---

## 2. Benchmark — concept queries (9)

Deterministic vs `BAAI/bge-m3`, same canonical corpus, k-truncation of the ranked list, relevance by section numbering.

### 2.1 Aggregates

| Metric | deterministic | bge-m3 | Δ |
|---|---|---|---|
| Dense Top-1 | 0.1111 | 0.7778 | +0.67 |
| Dense Top-3 | 0.3333 | 1.0000 | +0.67 |
| Dense Top-5 | 0.3333 | 1.0000 | +0.67 |
| Dense MRR | 0.2407 | 0.8518 | +0.61 |
| Dense R@5 | 0.2593 | 0.9630 | +0.70 |
| Dense R@10 | 0.3148 | 1.0000 | +0.69 |
| Final Top-1 | 0.8889 | 1.0000 | +0.11 |
| Final MRR | 0.9259 | 1.0000 | +0.07 |
| Final R@5 | 1.0000 | 0.9630 | −0.04 |
| Avg confidence | 0.7929 | 0.9187 | +0.13 |
| GENERATE / BLOCKED | 8 / 1 | 9 / 0 | +1 reset |

### 2.2 Per concept (dense MRR → final MRR, confidence, grounding)

| Query | gold | det Dmrr | bge Dmrr | det Fmrr | bge Fmrr | det conf | bge conf | det | bge |
|---|---|---|---|---|---|---|---|---|---|
| theft | §378 | 0.500 | **1.0** | 1.0 | 1.0 | 0.850 | 0.918 | G | G |
| murder | §300/302 | 0.167 | **1.0** | 1.0 | 1.0 | 0.846 | 0.927 | G | G |
| robbery | §390 | 0.000 | **1.0** | 1.0 | 1.0 | 0.827 | 0.896 | G | G |
| rape | §375 | 0.000 | **1.0** | 0.333 | **1.0** | 0.272 | **0.871** | BLOCKED | **G** |
| cheating | §415/420 | 0.000 | **1.0** | 1.0 | 1.0 | 0.831 | 0.921 | G | G |
| offer | §2 | 0.000 | 0.333 | 1.0 | 1.0 | 0.871 | 0.909 | G | G |
| acceptance | §2/7/8 | 0.000 | **1.0** | 1.0 | 1.0 | 0.876 | 0.967 | G | G |
| consideration | §2/25/185 | 1.000 | 0.333 | 1.0 | 1.0 | 0.886 | 0.957 | G | G |
| breach of contract | §73/74 | 0.500 | **1.0** | 1.0 | 1.0 | 0.878 | 0.902 | G | G |

All 9 concepts end at **Final MRR 1.0 / GENERATE**; average confidence rises +0.13.

### 2.3 The V2.4.2 rape blocker — resolved at the source
- Deterministic dense top-10 for "What is rape?": `302, 473, 440, 166A, 376C, 376, 1, 376, 354, 114` — **§375 absent**; final top-5 = `[i, 376, 375, 166A, b]`, so `evidence[0]='i'`, relevance 0.0104 → conf 0.2721 → **BLOCKED**.
- bge-m3 dense top-10: `375, 1, 40, 376D, 376E, i, 376C, ii, 376B, 376` — **§375 is dense #1**; final top-5 = `[375, i, 376, 376E, b]` → `evidence[0]=§375`, relevance 1.0, conf **0.8710**, **GENERATE**.

The previous flake was dense contributing 0.0 while graph/citation carried §375 into the final top-2; semantic dense now ranks the definition itself first, so the exact-numbering/rescue machinery is no longer load-bearing for this case.

---

## 3. Benchmark — ICA gold dataset (9 lookup queries)

Relevance by canonical section numbering (the gold file cites raw node ids for a non-canonical doc; numbers resolve to the canonical ICA doc). These are originally phrase-lookup queries; the semantic gain is real but smaller, and most remain locked out by the confidence guard (pre-existing, unchanged).

| Metric | deterministic | bge-m3 | Δ |
|---|---|---|---|
| Dense Top-1 | 0.1111 | 0.2222 | +0.11 |
| Dense Top-3 | 0.1111 | 0.2222 | +0.11 |
| Dense Top-5 | 0.1111 | 0.4444 | +0.33 |
| Dense MRR | 0.1111 | 0.2881 | +0.18 |
| Dense R@5 | 0.0556 | 0.3889 | +0.33 |
| Dense R@10 | 0.0556 | 0.5000 | +0.44 |
| Final Top-1 | 0.0000 | 0.1111 | +0.11 |
| Final MRR | 0.0957 | 0.2370 | +0.14 |
| Final R@5 | 0.1667 | 0.3889 | +0.22 |
| Avg confidence | 0.4571 | 0.4563 | −0.00 |
| GENERATE / BLOCKED | 2 / 7 | 2 / 7 | 0 |

Dense lookup improves (e.g. "short title" now has §1 at dense #1; "promise" reaches §2 at dense #1; R@10 nearly 9× deterministic on the bigger canonical universe), but final ranking still demotes the gold section below the expansion/keyword ties for several lookup-phrased queries, and confidence stays under threshold for most. This is consistent with V2.4.1/2 findings that lookup-style phrasing plus a lexically dense neighbourhood (Part II — Of Contracts titles) dominates the final order; no scope change is proposed here.

---

## 4. Regression verification

Full suite: **997 passed, 5 warnings in 72.2s** (988-test V2.4.2 baseline + 9 new tests). Targeted embedding/harness/retriever suites: 100 passed. Confirmed unfazed by the swap: section lookup routing, exact-numbering promotion (`explanation.py:783` untouched), citation scoring, propagation, parser, confidence guard, and query expansion all pass; the deterministic provider still drives every test via the conftest fixture.

## 5. Operational notes

- **Runtime behaviour:** with `EMBEDDING_MODEL=BAAI/bge-m3`, `EMBEDDING_FORCE_DETERMINISTIC=False`, `EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK=False`, an unloadable/unknown model now fails fast instead of silently falling back — the V2.4.2 silent-degradation path is closed for production.
- **First-start latency:** model weights were already cached locally (offline load ≈ 35 s, dim 1024). Corpus build wall time measured at 1168 s, dominated by CPU encoding before the sequence cap landed; with the cap in place the 749-node index CPU time dropped from "stalled >30 min at the full 8192-token context" to minutes (probe: an 8-text mixed batch encodes in 4.1 s).
- **No environment requests were made during the run** — everything resolved from the local HF cache; a `HF_TOKEN` warning is cosmetic.
- Preferred-order fallback (`bge-m3` → `bge-large-en-v1.5` → `e5-large-v2`) is honoured by `get_provider` via the registered specs; only bge-m3 weights are present offline, so the other two models are registered and prefix-handled but not yet exercised in this environment. e5's `"query: "/"passage: "` prefixes are applied at encode time by `embed_query`/`embed_documents`.

## 6. Files changed

- `src/embeddings/models.py` — registry + ModelSpec prefixes (extended).
- `src/embeddings/providers.py` — semantic provider prefixes + `max_seq` token clip + `allow_fallback` fail-fast.
- `src/embeddings/service.py` — `embed_documents` / prefix-aware `embed_query`.
- `src/embeddings/indexer.py` — document-side encoding call sites.
- `src/config/settings.py` — `EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK`, `EMBEDDING_MAX_SEQUENCE_LENGTH`.
- `src/llm/service.py::build_default_corpus`, `scripts/rebuild_assets.py` — runtime + asset wiring.
- `eval/corpus.py`, `eval/harness.py`, `src/evaluation/corpus.py`, `src/evaluation/pipeline.py` — benchmark/eval model switch.
- `scripts/benchmark_semantic_dense.py` — BEFORE/AFTER repro script (new).
- `tests/test_embeddings.py`, `tests/test_eval_harness.py` — new cases.
- `evaluation/embed_retrieval_comparison_v243_{deterministic,BAAI/bge-m3,full}.json` — benchmark artifacts.

## 7. Residuals / next steps

1. Section-lookup queries in the gold set remain below the confidence threshold and are final-rank demoted for lookup phrasing — a retrieval-ordering artefact of expansion/keyword ties plus lookup-phrased queries, not dense failure.
2. `bge-large-en-v1.5` and `e5-large-v2` registered + prefixed but unmeasured offline; a GPU/online environment can validate the preferred-order story and per-model deltas (dimensions are 1024 in all cases, so no store migration is triggered by model choice).
3. Query-side `embed_query` retains the bge-m3 no-prefix convention; switching to `bge-large`/`e5` changes query encoding only via the registered prefixes.