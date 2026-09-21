# V2.4 Investigation Report — Why Open-Ended Legal Concept Queries Are Still Blocked / Weak

**Scope:** Investigation only. No code was changed, committed, or pushed.
**Method:** Full 10-stage pipeline trace + dense/graph/hierarchy/fusion scoring for ten concept queries, run with a deterministic in-memory canonical corpus (ICA `0d1934142f67c5f5`, 205 nodes; IPC `cf20a14c52127fd5`, 544 nodes; 749 indexed points; 1213 edges) under `EMBEDDING_FORCE_DETERMINISTIC` + `QA_INDEX_IN_MEMORY`.
**Date:** 2026-09-18

---

## 1. Root cause (short answer)

Two independent defects combine to make every open-ended concept query **both blocked and weakly ranked**:

1. **Confidence block (primary — affects 10/10 queries).** The relevance component of the confidence formula uses a **character‑bigram Dice similarity between the stripped trigger phrase of the query and the entire concatenated evidence block** (`_relevance_fallback` → `_text_similarity`). For short concept queries this score is structurally ~0.01–0.2 (measured 0.015 for "What is theft?" even when section 378 is rank‑1). The badge rule `relevance < 0.30 → status "insufficient"` then marks every result invalid, so the grounding guard refuses to generate an answer **even when the correct section was retrieved first**. → Stages **F (confidence scoring)** + **G (grounding guard)**.

2. **Ranking weakness (secondary — affects gold-section position).** The dense stage (A) returns near-identical, concept‑insensitive hits (the same sections 84/85/41/23/63/114 top the list for theft, murder, cheating, robbery and rape); the graph stage (D) is the only reliable recoverer but is **keyword‑exact** (misses "offer"→"proposal", so §2 is never even retrieved for "What is an offer?"), and query expansion (H) is **disabled by default** and, when considered, lacks offer/acceptance and IPC synonym terms. Where gold sections survive only as graph keyword hits they carry dense≈0, so the ranking weights (B: dense 0.35 dominant, citation 0.30 next) push definition sections below punishment/citation‑heavy sections (murder §300@3 behind §79; rape §375@7; robbery §390@2; coercion §15@2; consideration §2@5).

Stages **C (hierarchy propagation), E (evidence filtering), and the parser/dedup path are NOT implicated**: every gold node that entered the candidate set survived to evidence, hierarchy propagation helped dense‑seeded golds (hier=0.25), and no gold evidence was dropped by filtering.

---

## 2. Measurements (supporting evidence)

### 2.1 Aggregate metrics (budget = 10)
| Metric | Value |
|---|---|
| Top‑1 accuracy | 0.300 (3/10) |
| Top‑3 accuracy | 0.800 |
| Top‑5 accuracy | 0.800 |
| Top‑10 accuracy | 0.900 |
| MRR | 0.5143 |
| Recall@5 | 0.6667 |
| Recall@10 | 0.8167 |
| **Answerable (validity=supported)** | **0/10 — all blocked** |

### 2.2 Per-query gold verdicts
| Query | Gold (§) | Evidence rank | Gold dense rank | Gold graph rank | confidence |
|---|---|---|---|---|---|
| What is theft? | IPC 378 | **1** | 22/40 | 2 | 0.3002 → blocked |
| What is murder? | 300 / 302 | 3 / **absent** | 14 / 23 | 5 / 19 | 0.2920 → blocked |
| What is cheating? | 415 / 420 | 3 / 6 | absent / absent | 3 / 6 | 0.2754 → blocked |
| What is consideration? | 185, 23, 25, 2 | 1 / 2 / 4 / 5 | 1 / 2 / 12 / 24 | in top‑10 | 0.3946 → blocked |
| What is an offer? | ICA 2 | **absent from top‑10** | absent (top‑40) | absent | 0.3432 → blocked |
| What is acceptance? | 2, 7, 8 | absent / 4 / 3 | absent / 13 / 12 | absent / 1 / 7 | 0.3702 → blocked |
| What is coercion? | ICA 15 | 2 | absent (top‑40) | 5 | 0.2870 → blocked |
| Criminal breach of trust | 405 / 406 | 1 / 4 | absent / 1 | 1 / 5 | 0.3317 → blocked |
| What is robbery? | IPC 390 | 2 | 16/40 | 5 | 0.3172 → blocked |
| What is rape? | IPC 375 | 7 | absent (top‑40) | 8 | 0.2916 → blocked |

Top‑10 recall is high (0.8167) because the graph stage rescues most gold sections; **the pipeline retrieves, then strangles itself on relevance + ranking**.

### 2.3 Stage-by-stage trace evidence
- **[3] Query expansion: disabled.** `expansion.active=False`, `reason="expansion disabled"` for all 10. Default `QA_QUERY_EXPANSION_ENABLED=False` (`settings.py:105`).
- **[5] Dense is concept‑insensitive.** The top‑7 dense hits for *theft/murder/cheating/robbery/rape* are identical: §84 (0.6496), §85, §41, §23, §63, §114, CHAPTER I. §84 (“Act of a person of unsound mind…”) enumerates offences and wins every query. Gold ranks: theft §378 @22, murder §300 @14 / §302 @23, robbery §390 @16; cheating §415/420, coercion §15, rape §375, offer/acceptance §2 never in dense top‑40.
- **[6] Graph keyword is the only recoverer.** It rescues gold when the token appears verbatim in the section text (378 "Theft", 300 "Murder", 415 "Cheating", 23/25/2 "consideration", 15 "Coercion", 405/406, 390, 375 "rape"→@8). It **fails on synonyms**: §2(a) uses “proposal”, never “offer”/“acceptance”, so **“What is an offer?” returns only §37–38 and “What is acceptance?” skips §2 entirely**. It is also a hard top‑k gate: murder §302 ranks ~19 in the keyword list → cut before candidates.
- **[8] Fusion candidates** miss every gold that both dense (≥ top‑10) and graph (top‑10) miss: offer §2, acceptance §2, murder §302. No gold was ever dropped later (all `cand_in=True` nodes appear in evidence — stage E clean).
- **[9] Ranking weights dominate.** Graph-only gold sections tie at `kw=1.0, dense=0, cite=0` → `rank≈0.1798`, losing to sections carrying citation bumps (`cite=1.0`): murder §79 (0.4303) outranks §300 (0.2859); robbery §216A (0.4305) outranks §390 (0.3210); rape §1/§376AA/§376D (0.4441/0.3802/0.3301) outrank §375 (0.1798); cheating §416 (0.4300, cite=1.0) outranks §415 (0.1798).
- **[9/10] Confidence + guard block everything.** Worst case: “What is theft?” retrieves IPC §378 at rank‑1 (`final=0.7538`, dense+graph+hierarchy+keyword+citation all present) yet `evidence_relevance=0.015`, sufficiency≈0.65, `confidence=0.3002` → badge `"insufficient"` → `validity=False` → guard returns the canned blocked answer. **Grounding guard did not once allow a concept answer.**

### 2.4 The math of the block
`_text_similarity` (char‑bigram Dice) between cleaned query `"theft"` (4 bigrams) and the full concatenated evidence text (thousands of distinct bigrams) ≈ 0.015. Badge rule (`explanation.py:2047`): `relevance < 0.30 → "insufficient"`; guard (`service.py:289`): relevance < `GUARD_MIN_RELEVANCE=0.30` → don’t generate. Even with an LLM entailment wired in, the *pre‑answer* relevance would cap `confidence` at a redistributed ≤ (0.65·relevance + …) ≈ 0.30–0.35, still under `QA_CONFIDENCE_THRESHOLD=0.45`.

---

## 3. Exact files/functions responsible

| Stage | File | Symbol(s) |
|---|---|---|
| F — relevance that blocks | `src/llm/explanation.py` | `_compute_evidence_relevance` (L1515), `_relevance_fallback` (L1561–1584), `_text_similarity` (L277–294) |
| F — badge/confidence | `src/llm/explanation.py` | `_compute_verification_badge` (L2020, rule at L2047), `_score_confidence` (L1856, redistribution at L1953–1960, insufficient cap L1981–1986) |
| G — guard gate | `src/llm/service.py` | `_should_generate_answer` (L275–298, gates at L289/292/295), `GUARD_MIN_RELEVANCE=0.30` (L49) |
| H — expansion off/gaps | `src/config/settings.py` (`QA_QUERY_EXPANSION_ENABLED=False`, L105), `src/retrieval/query_expansion.py` (`CONCEPT_TERMS`, `VERIFIED_SECTION_MAPPING`, `SURFACE_PHRASES` — ICA‑civil only; no offer→proposal, no IPC concepts) |
| A — dense | `src/embeddings/retriever.py` (`dense_search`/`hybrid_retrieve`), `src/embeddings/service.py` (deterministic provider) |
| D — graph wiring | `src/retrieval/ranker.py` (`retrieve`, keyword seeding + top‑k gate L76), `src/retrieval/scorer.py` (keyword/text signals) |
| B — ranking weights | `src/llm/explanation.py` — `DEFAULT_RANKING_WEIGHTS` (L70; dense 0.35, citation 0.30, graph 0.25, keyword 0.15, hierarchy 0.15), `_fill_ranking_signals` (L1005+) |
| C, E — not implicated | `src/retrieval/context.py` (`propagate_hierarchy`), evidence dedup/filter |

## 4. Independence from previous fixes

**Independent.** V2.3 (Issue #11, parser fragment suppression) touched only `src/hierarchy/parser.py` and regenerated hierarchy JSONs; it did not modify retrieval, fusion, confidence, or the guard. None of the traced defects involve the parser or fragments:
- The identical-top-7 dense phenomenon, keyword-exact graph seeding, expansion-off default, citation-heavy ranking, and the char-bigram relevance fallback all pre-date and are orthogonal to fragment suppression.
- Evidence node counts are slightly lower post‑V2.3 (fragments removed), which marginally *lowers* the irrelevant-token mass in the concatenated evidence string, but not enough to move `_text_similarity` off ~0.02 (the dominant terms come from legitimate section text, not fragments).
V2.4 therefore depends on **no** prior fix; conversely, fixing V2.4 does not undo V2.3 (parser and guard are disjoint). The `_relevance_fallback`/guard path is effectively the same one that gates section-lookup queries; those pass only because `_is_exact_provision_match` short-circuits relevance to 1.0 (Issue #12’s exact-provision exception, `explanation.py:1530`), which requires a *cited section number* — concept queries never trigger it.

## 5. Minimal fix surface (for a later V3 V2.5; not applied here)

Ranked by impact-to-effort:

1. **Make relevance task-aware (F, fixes the 10/10 block).**
   - Either mirror Issue #12’s exact-provision exception: when intent is `explanation` and the top evidence’s section is the concept’s canonical definition (via `VERIFIED_SECTION_MAPPING` or a concept→section table), score relevance as direct (1.0) regardless of lexical overlap; or
   - Replace the char-bigram-Dice fallback with a semantic measure already computed in the pipeline: rank-weighted mean of the *evidence nodes’* dense similarity over the top evidence (see `Evidence.dense_score`/raw hit scores), which keeps section-lookup behaviour and concept behaviour on the same legitimate signal; or
   - Set `QA_QUERY_EXPANSION_ENABLED=True` **and** make the fallback judge use the *expanded search text* (so “proposal/consideration” terms raise `_text_similarity`) — the smallest one-line setting change with a real effect.

2. **Close the synonym/finding gap (H + D).** Add to expansion vocabulary: `offer → proposal (ICA §2)`, `acceptance → ICA §7/§8/§2`, and IPC concept → section terms (theft §378, murder §300/302, cheating §415/420, robbery §390, rape §375) as `VERIFIED_SECTION_MAPPING` entries; and raise the graph keyword `top_k` feed for `explanation` intent so synonym/adjacent sections (murder §302 @19) enter candidates.

3. **Rebalance ranking for definition sections (B).** Give a small definition-title or concept/law-term match bonus (e.g. keyword credit for the query token present in the section title, or reuse `DEFINITION_BONUS=0.12` on `"…defined"`/numbered-definition sections) and cap citation dominance so punishment/citation-heavy sections (§79, §216A, §376AA) stop outranking the actual definition.

Not needed: hierarchy propagation (C) and evidence filtering (E) already behave; dense (A) is best addressed indirectly by (1)/(2) rather than a rerank/embedding replacement.