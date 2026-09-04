# Task 19 — HHGR Retrieval Ranking Pipeline Audit & Retrieval Improvement Plan

**Scope:** Analysis only. No production code, retrieval/ranking/confidence/verification/grounding-guard, nor API behavior was modified. All findings below were produced with read-only diagnostics over the real canonical corpus through the production `ExplainabilityEngine` and `QueryService` paths.

**Validation suite:** 130 queries (`validation/expected_results.json`), of which 90 are `expected_status == "supported"` cases (categories 1–4). The remaining 40 are the blocked/insufficient-expected categories (5–6), which already pass 20/20 + 20/20.

**Harness criterion (matches `run_manual_validation.py`):** a case passes only when `top_section == expected_section` (top-1 evidence numbering) AND `status == expected_status` AND confidence is inside the case's `[confidence_min, confidence_max]` band.

---

## 1. Clean failure classification (mutually exclusive, sums exactly to 90)

Every supported-expected query was assigned to exactly one bucket. The buckets are non-overlapping and their counts sum to the supported-expected total (90), fixing the earlier counting artifact.

| Bucket | Count | Meaning |
|--------|------:|---------|
| **A** | 29 | Expected section **never retrieved** in any candidate set (dense, graph, hierarchy, hybrid) |
| **B** | 15 | Expected section retrieved in some candidate set but **not in the final top-5** evidence |
| **C** | 16 | Expected section in **top-5 but not top-1** (a wrong section is ranked #1) |
| **D** | 28 | Expected section is **top-1 correct** but **confidence < supported threshold (0.45)** |
| **E** | 2 | Expected section is top-1 correct **and** confidence ≥ threshold, yet validation still fails (status mismatch) |
| **Total** | **90** | All supported-expected queries fail |

Rank of the expected section among the top-5 (0-based): **rank 0 = 30**, rank 1 = 5, rank 2 = 9, rank 3 = 1, rank 4 = 1, **not in top-5 = 44**. Only 30/90 (33%) ever place the correct section at #1; 44/90 (49%) never place it in the top-5 at all.

---

## 2. Cross-document contamination (independent stat)

Both canonical documents (Indian Contract Act `0d1934142f67c5f5` and Indian Penal Code `cf20a14c52127fd5`) share a single Qdrant index, and semantic queries have **no document restriction** (`QA_QUERY_EXPANSION_ENABLED=False`, `document_id` is not derived for these queries).

- **76/90 (84.4%) supported-expected cases** have at least one top-5 evidence node from the non-target document.
- ICA queries routinely retrieve IPC sections (e.g. 376, 376DA, 354B, 434, 31) and IPC sections' illustrations in their top-5.

This is an independent, cross-cutting statistic and is *excluded* from the mutually-exclusive A–E totals.

---

## 3. Candidate-presence analysis (retrieval vs ranking failure)

For each supported-expected query we recorded whether the expected section's **node** appears in each retrieval stage's candidate set:

- **Category A (29)** — the correct section is absent from dense, graph, hierarchy, *and* hybrid candidate sets → a genuine **retrieval failure** (the correct content is never surfaced).
- **Category B (15)** — the correct section is present among candidates but dropped before/pushed below the final top-5 → a **ranking/fusion failure**.
- **Category C (16)** — correct section is in the top-5 but not promoted to #1 → a **ranking-order failure**.
- **Category D (28)** — correct section is top-1, so retrieval+ranking succeeded; the failure is downstream in **confidence/verification**.
- **Category E (2)** — retrieval+ranking+confidence all nominally succeed; failure is a **verification-status mismatch**.

Net: 29 (A) are hard retrieval misses; 31 (B+C) are ranking-order problems; 30 (D+E) are verification/confidence problems on already-correctly-ranked evidence.

---

## 4. Verification status: the dominant proximate cause

For every supported-expected query we captured the verification badge (`validity_status`) and its drivers.

- **Only 3/90 resolve to `supported`.** The other **87/90 resolve to `insufficient`**.
- In **all 87** insufficient cases, the badge was tripped by **`evidence_relevance < 0.30`** (badge rule at `_compute_verification_badge`, relevance threshold 0.30; sufficiency threshold 0.45; entailment threshold 0.35).

Consequences of the `insufficient` badge (see `_score_confidence`):

1. It **fails the `status == expected_status (supported)` validation check** for every affected query — even when the correct section is top-1.
2. It **caps confidence at 0.45** (the `insufficient_cap`), which is why Category D cases (top-1 correct) cannot cross the 0.45 supported threshold.

Category D component breakdown (28 cases, top-1 correct but conf < 0.45):

| Component | Weight (live) | Avg value (D) |
|-----------|--------------:|--------------:|
| retrieval_base | 0.15 (→ redistributed 0.231) | 0.349 |
| evidence_relevance | 0.30 (→ redistributed 0.462) | **0.061** |
| evidence_sufficiency | 0.20 (→ redistributed 0.308) | 0.336 |
| citation_entailment | 0.35 | **0.000 (never evaluated)** |

The two Category E cases (4.004, 4.013) are the narrowest misses: top-1 correct, confidence exactly 0.450 (already capped), but relevance 0.2905 / 0.2975 — **just below** the 0.30 relevance threshold, so the badge still says `insufficient` and the status check fails.

---

## 5. Root-cause chain

```
Poor evidence composition (correct section low / wrong-doc sections pollute top-5)
        |
        v
_compute_evidence_relevance computes text-similarity over the mixed, mostly-irrelevant
top-5 block  ->  relevance systematically low (< 0.30 for 87/90)
        |
        v
Verification badge -> "insufficient"  (relevance < 0.30)
        |
        +----> fails `status == supported` check  (all 87)
        +----> caps confidence at 0.45           (blocks D and E)
```

Contributing factors, in urgency order:

1. **Cross-document contamination (root cause of low relevance).** The shared index + no document restriction + disabled query expansion means ICA queries flood the evidence with IPC sections. Since relevance is scored over the whole evidence block, one wrong-doc section drags the text-similarity (hence relevance) below threshold for the entire query.
2. **Evidence relevance threshold is used as a hard verification gate.** `relevance < 0.30 → insufficient` is the single most common trigger (87/90). Being a text-similarity heuristic over a concatenated evidence block, it is brittle to contamination.
3. **Citation entailment is dead code in production.** `_compute_citation_entailment` is invoked only from unit tests (`tests/test_llm_explanation.py`); neither `ExplainabilityEngine.explain()` nor `QueryService.answer()` ever calls it. The 0.35 entailment weight in `_score_confidence` is silently redistributed to relevance/sufficiency/retrieval-base. No entailment signal can ever rescue or validate the badge.
4. **Retrieval/ranking quality** (A=29 never retrieved; B=15 below top-5; C=16 not promoted) — a substantial but secondary lever relative to the verification gate.

---

## 6. Recommendation for Task 20 (ranked)

The single highest-leverage fix is to stop the verification badge from failing on cross-doc pollution, then improve candidate quality.

1. **Restrict retrieval to the target document.** Drive `document_id` (and/or enable query expansion) from query/intent so ICA queries do not retrieve IPC sections. This directly removes the contamination root cause and should lift `evidence_relevance` above 0.30 for the majority of the 87 insufficient cases (addresses D, E, and reduces noise in B/C).
2. **When entailment is not evaluated, do not let relevance-by-similarity be a hard gate.** Either (a) wire the LLM entailment judge into the live path so the 0.35 entailment term is real, or (b) loosen/restrict the `relevance < 0.30 → insufficient` rule to cases where entailment was actually evaluated, or (c) compute relevance only over the *top-ranked* relevant section instead of the contaminated top-5 block.
3. **Improve ranking so the correct section is promoted to #1** (C=16, B=15): rebalance the 5-signal `_rank` weights (currently dense 0.35 / citation 0.30 / graph 0.25 / keyword 0.15 / hierarchy 0.15) and enforce the canonical-section preference earlier; verify against the expected-section rank distribution.
4. **Recover Category A (29) misses** — correct section absent from all candidate sets — by inspecting the depth/threshold of the dense and hierarchy stages (these are retrieval-recall gaps, not ranking gaps).

### Expected impact
- Contamination removal (Rec #1) is predicted to flip most of the 87 `insufficient`-status cases back toward `supported`, which would alone move ~30 (D+E) of the 90 failures to passing, and materially raise top-5 relevance for the remaining buckets.
- Combined with ranking improvements (Rec #3), the A/B/C buckets (60 total) are the main remaining front.

---

### Reconciliation note
These counts reconcile exactly with the earlier diagnostic pass (not_in_top5 = A+B = 44; top-5-not-top-1 = 16; conf-below-even-top-1 = 28; top-1-conf-ok-fail = 2), which had appeared to "overlap" only because the earlier script double-counted the contamination flag in an informational counter, not in the category totals.
