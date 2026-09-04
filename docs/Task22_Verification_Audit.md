# Task 22 — Verification Failure Audit

**Scope:** Analysis only. No production, retrieval, ranking, confidence, verification, grounding-guard, prompt, schema, or evaluation changes.
**Harness:** `validation/task22_verification_audit.py` (reuses the manual-validation wiring: real corpus + deterministic mock LLM).
**Data:** `results/task22_verification_audit.json` (90 supported-expected queries, full diagnostics).
**Baseline reference:** `docs/Task19_Retrieval_Analysis.md`.

---

## 1. Executive Summary

Task 21 improved retrieval to **47/90 top-1 correct** and **68/90 top-5 recall**. Yet the manual-validation pass rate for the **supported** cases (Categories 1–4) is **0/90**. Retrieval now works well enough to rank the correct section first for half the cases, but **not one supported query is able to generate an answer**, because the grounding guard blocks *every* supported query before the LLM is ever invoked.

The single highest-impact bottleneck in the Retrieval → Verification → Grounding pipeline is:

> **`evidence_relevance` is pinned to 0.0 for 100% of queries** under the mock-LMM relevance judge. Because the verification badge marks any query with `relevance < 0.30` as `insufficient` (`_compute_verification_badge`, `src/llm/explanation.py:1781`), **every** supported query gets `verification_status == "insufficient"`, and the grounding guard (`src/llm/service.py:293`, `if verification_status != "supported": return False`) blocks generation.

In other words, the relevance gate is a **hard, universal blocker**. While retrieval was improved by Task 21, it cannot translate into any validation PASS because relevance/verification is a total gate that currently never passes.

A secondary, closely-related contributor is **cross-document (ICA ↔ IPC) contamination**: 77/90 supported retrievals (85.6%) have Penal-Code fragments in the top-5 block (or even a Penal-Code section as top-1). This contamination is what keeps both the text-similarity relevance score and the sufficiency score low.

---

## 2. Overall Statistics

| Metric | Value |
|--------|-------|
| Total validation queries | 130 |
| Supported-expected queries (Categories 1–4) | 90 |
| Blocked-expected queries (Categories 5–6) | 40 |
| Overall pass | 40 / 130 (30.8%) |
| **Supported pass** | **0 / 90 (0.0%)** |
| Grounding-guard activations | 130 / 130 (100%) |
| Average confidence (supported) | 0.204 |
| Average latency (supported) | ~170 ms |

The 40 overall PASS are exclusively the 40 blocked-expected cases (Categories 5/6). **Every** supported-expected case fails.

---

## 3. Retrieval Statistics

| Retrieval metric | Count | % of 90 |
|------------------|-------|---------|
| Top-1 section correct | 47 | 52.2% |
| Top-5 section recall | 68 | 75.6% |
| Top-1 is an IPC (Penal Code) section | 29 | 32.2% |
| Top-1 is an ICA (Contract Act) section | 61 | 67.8% |

**Retrieval intent (query classifier):**

| Intent | Count |
|--------|-------|
| section_lookup | 39 |
| explanation | 41 |
| definition | 1 |
| comparison | 9 |

**Retrieval strategy:** `fixed` for all 90 (adaptive top-k did not change the window for these cases).

---

## 4. Verification Statistics

`verification_status` distribution — **`insufficient`: 90 / 90 (100%)**. `supported`: 0.

| Signal | mean | median | min | max | std |
|--------|------|--------|-----|-----|-----|
| evidence_relevance | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| evidence_sufficiency | 0.3554 | 0.3447 | 0.1646 | 0.5647 | 0.0496 |
| citation_entailment | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

**Percentiles (evidence_sufficiency):** p5=0.317, p25=0.335, p50=0.345, p75=0.362, p90=0.394, p95=0.464.

**evidence_sufficiency histogram:**

```
[0,.1)  0   ......
[.1,.2) 1   .
[.2,.3) 1   .
[.3,.4) 80  ........................................
[.4,.5) 6   ......
[.5,.6) 2   ..
```

Only **5 / 90** reach sufficiency ≥ 0.45 (the gate threshold); 83 sit in [0.30, 0.45), 2 below 0.30.

**Key observations:**
- `evidence_relevance` is exactly **0.0 for 100%** of queries → it fails the `relevance < 0.30` badge rule first, before sufficiency is even consulted.
- `citation_entailment` is also 0.0 for all — entailment is a **generation-time** check (`_score_with_citation_entailment`, `service.py:180`) that only runs *after* the guard passes, so it is never reached.

---

## 5. Confidence Statistics

| Metric | Count | % |
|--------|-------|---|
| confidence < 0.45 | 90 | 100% |
| confidence < 0.30 | 90 | 100% |

| Stat | value |
|------|-------|
| mean | 0.204 |
| median | 0.199 |
| min | 0.149 |
| max | 0.330 |

**Label distribution:** `very_low` = 86, `low` = 4.

Confidence is dominated by the low relevance/sufficiency signals and is further **capped at 0.45** by the `insufficient_cap` rule whenever the verification badge says `insufficient` (`explanation.py:1716`). Because the badge is `insufficient` for every query, confidence can never exceed 0.33 in practice here — so it could never cross the 0.45 supported-threshold either, even if the relevance gate were relaxed.

---

## 6. Evidence-Quality Analysis

Classification of the **top-1 evidence chunk** for all 90 supported queries:

| Evidence quality | Count | % of 90 | Notes |
|------------------|-------|--------|-------|
| Block contaminated by IPC fragments | 48 | 53.3% | Top-1 is ICA but top-5 block mixes in Penal-Code chunks |
| IPC (Penal-Code) chunk as top-1 | 29 | 32.2% | Correct section *number* but wrong document (cross-doc ambiguity) |
| Substantive section text | 10 | 11.1% | Clean, complete, relevant ICA section |
| Chapter instead of section | 2 | 2.2% | Chapter node promoted ahead of the section |
| Misaligned / truncated (title is body prose) | 1 | 1.1% | Node title is continuation prose from a sibling section |

**Cross-document contamination total: 77 / 90 (85.6%).**

This is the dominant evidence-quality failure and the direct reason relevance/sufficiency are low: the similarity-based relevance and the sufficiency coverage metrics are computed over the *whole contaminable top-5 block*, so Penal-Code fragments dilute every score. It precisely matches the prediction made in Task 19 (`Rec #1`: restrict retrieval to the target document).

---

## 7. Failure-Category Table

Every blocked query is assigned to **exactly one** non-overlapping category; the totals reconcile exactly to 90.

| Cat | Definition | Count | % of 90 |
|-----|------------|-------|---------|
| A | Correct section never retrieved anywhere | 14 | 15.6% |
| B | Correct section retrieved but below Top-5 | 8 | 8.9% |
| C | Correct section inside Top-5 but not promoted to Top-1 | 21 | 23.3% |
| D | Correct Top-1 but evidence_relevance below threshold | **47** | **52.2%** |
| E | Correct Top-1 but confidence below threshold | 0 | 0.0% |
| F | Correct Top-1 but verification_status != supported | 0 | 0.0% |
| G | Everything correct except grounding guard blocks | 0 | 0.0% |
| **Total** | | **90** | **100%** |

**Reconciliation:** A+B = 22 (outside top-5), C = 21 (in top-5, wrong rank), D = 47 (top-1 correct). 22 + 21 + 47 = 90. ✓ (`top5 = 68 = C + D`; `top1 = 47 = D`.)

E, F and G are empty because the relevance gate (D) fires first: with relevance = 0.0 < 0.30 for 100% of queries, no top-1-correct query passes relevance to reach the confidence/status/guard-only branches. Every one of the 47 top-1-correct cases lands in D.

---

## 8. Retrieval vs Verification Correlation

| Correlation question | Count | % of 90 |
|----------------------|-------|---------|
| Top-1 correct **and** verification failed (status != supported) | 47 | 52.2% |
| Top-5 correct **and** verification failed | 68 | 75.6% |
| Fail because evidence_relevance < 0.30 | 90 | 100% |
| Fail because confidence < 0.45 | 90 | 100% |
| Guard triggered (blocked generation) | 90 | 100% |

Every query fails on relevance *and* confidence *and* the guard. Relevance is the first and decisive gate; the guard then hard-stops generation. There is **no** supported query whose retrieval is correct *and* whose verification succeeds.

---

## 9. Recoverable-Query Estimate

These are estimates of how many additional supported queries would **pass the full validation** (section match + status == supported + confidence in band) under each hypothetical. No production logic was changed.

| Scenario (if …) | Additional PASS | Basis |
|-----------------|-----------------|-------|
| The grounding guard alone were ignored | **0** | `evaluate()` still requires `validity.status == supported`; with relevance = 0.0 the badge still says `insufficient`, so status still fails. Guard is downstream, not the root gate. |
| Relevance raised so the badge passes (relevance ≥ 0.30) **and** the 0.45 sufficiency gate is kept | **2** | Only 2 of the 47 top-1-correct queries also have sufficiency ≥ 0.45 → they alone could become `supported`. |
| Verification **accepted the current evidence** for top-1-correct queries (badge forced `supported`; confidence unchanged) | **23** | 23 of 47 top-1-correct already have confidence inside their case band; 24 still fall below `confidence_min` = 0.2 and would fail the confidence check. Supported pass would move 0 → 23 (0% → 25.6%). |
| Additionally confidence were raised to ≥ 0.45 | **0 extra** | Confidence is not the binding constraint: the 24 failing top-1-correct cases fail on `confidence_min` (0.2), and the 23 that would pass already pass. |

**Bottom line:** the realistic recoverable ceiling is **up to ~23 of 90 supported queries (25.6%)** — and only if verification stops treating the current (contaminated) evidence as irrelevant. Fixing *relevance alone* while keeping the sufficiency gate recovers only **2**. The remaining 24 top-1-correct cases additionally need their confidence to clear the 0.2 floor.

---

## 10. Root-Cause Analysis

**Primary root cause — universal relevance gate failure.**

Under the offline/evaluation pipeline the LLM relevance judge is the `MockLLMClient`, whose response is the canned text:

```
[mock] Based on the retrieved legal evidence, the answer addresses: <query>. Sources cited: ...
```

This contains no JSON, so `_parse_relevance_json` (`explanation.py:174`) returns `{"score": 0.0, ...}` and `_compute_evidence_relevance` returns `relevance = 0.0` **unconditionally**. Every query then hits the badge rule `evidence_relevance < 0.30 → "insufficient"` (`explanation.py:1781`) before the guard, which then blocks generation (`service.py:293`). Net effect: **0/90 supported queries can ever reach the LLM** under the evaluation harness.

This is an evaluation-blue/tooling failure as much as a pipeline failure — with a real LLM the relevance judge could, in principle, return values ≥ 0.30. But as built and validated (deterministic mock), relevance is always 0.0, so the supported pipeline is entirely unobservable through validation.

**Secondary root cause — cross-document contamination.**

77/90 supported retrievals mix ICA and IPC content (or return an IPC section as top-1 by number). Because relevance (similarity over the whole block) and sufficiency (keyword coverage over the whole block) are computed over the contaminable top-5, any Penal-Code fragment drags both scores down. Even for the 47 top-1-correct queries, the block is usually contaminated, keeping sufficiency low (only 2/47 ≥ 0.45).

**Precision note on the cited rule.** The *authoritative* badge (`_compute_verification_badge`, `explanation.py:1781`) skips the entailment branch during `explain()` because `explain()` does not pass `citation_entailment` to `_score_confidence` (`explanation.py:596`), so its sentinel is `-1.0` rather than `0.0` (`explanation.py:1703`). The badge therefore attributes the failure to **`evidence_relevance < 0.30`** (category D). The separate diagnostic `decision_path` (`_build_verification_trace`, `explanation.py:1540`) instead reads the *factor default* `citation_entailment = 0.0` and reports "Citation entailment below threshold (0.0000 < 0.35)". This is an **inconsistency between the status-authoritative badge and the diagnostic trace** — they diverge on which rule they cite, though both conclude `insufficient`. The analysis above (and the 47/90 category-D count) is based on the badge authority; the trace's entailment citation is a cosmetic diagnostic discrepancy, not the true gate.

**Tertiary root cause — evidence-chunk quality.**

A minority of cases serve misaligned/truncated chunks (e.g. `1.001` top-1 title `"be absolute and unqualified. (2) be expressed…"` — body prose used as a node title), or a chapter node instead of the section. This is a data-chunking issue independent of contamination.

**Why Task 21 did not move validation:** Task 21 was deliberately retrieval-only and did not touch relevance, verification, or the guard. So the 30 → 47 top-1 improvement was real but cannot surface as a PASS because relevance/verification is a total gate that never passes.

---

## 11. Ranked Recommendations (by expected impact)

> Analysis only — none applied. Ordered by estimated impact on the supported pass rate (currently 0/90).

1. **Fix the mock relevance judge so it returns a real, parsed score (or gate relevance on entailment availability).** Highest impact. The `relevance < 0.30 → insufficient` hard gate currently sees `relevance = 0.0` for every query. If the missing/real judge value is restored to a text-similarity score, the gate stops being a universal blocker. Alone this could unblock the pipeline, but it would still leave sufficiency (below 0.45 for most) failing — partial alone (~2), meaningful when combined with #2.

2. **Remove cross-document contamination (restrict retrieval to the target document).** Second-highest. Driving ICA queries to not retrieve IPC fragments (77/90 currently contaminated) should lift the similarity-relevance and keyword-sufficiency coverage for the majority of queries, addressing both relevance and sufficiency simultaneously. This is Task 19 `Rec #1` and remains the clearest path to a genuine (not threshold-loosening) recovery.

3. **Compute relevance/sufficiency over the top-1 relevant (in-document) section rather than the whole contaminable top-5 block.** Reduces dilution and makes the scores reflect actual answer quality; complements #2.

4. **Reconcile the confidence floor.** 24 of 47 top-1-correct queries sit just below `confidence_min` 0.2. As contamination is fixed, confidence will rise; the 0.45 supported-threshold relationship should be re-validated (without loosening the guard).

5. **Improve evidence chunking for the handful of misaligned/truncated nodes** (e.g., `1.001`), so the correct section carries its own title/definition rather than a sibling's prose.

**Do NOT** lower relevance/sufficiency/confidence thresholds to force votes through — the guard should keep protecting against fabrication; the fix should make the evidence genuinely richer (Rec #2/#3), not relax the safety net.

---

## Deliverables

1. `validation/task22_verification_audit.py` — audit harness (reuses the manual-validation service wiring).
2. `results/task22_verification_audit.json` — per-query diagnostics (retrieval, ranking, evidence, verification, confidence, guard).
3. `docs/Task22_Verification_Audit.md` — this report.

*All category totals reconcile to 90; all percentages are computed over n=90 supported-expected queries.*
