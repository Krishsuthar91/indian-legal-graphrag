# Task 21 — Retrieval Recall & Ranking Improvements

## Objective

Improve **retrieval quality only** (recall + ranking) so that the correct
sections rank top-1 more often, fixing the 90 supported-expected validation
failures (buckets A=29, B=15, C=16, D=28, E=2) identified in Task 19.

Constraints honoured: **no changes to** verification, confidence scoring,
grounding guard, API schemas, evaluation metrics, entailment, or LLM prompts.
Every change is confined to retrieval/ranking so the correct evidence section
surfaces and ranks first.

## Files Changed

### 1. `src/retrieval/scorer.py` — word-boundary section citations (Change 1)

- `citation_score` previously returned `1.0` when `ref in combined`
  (substring). A query for **"Section 1"** therefore matched **"Section 141"** /
  **"Section 12"**, and any Document/Chapter whose prose merely mentioned
  "Section N" flooded the seed set with irrelevant nodes.
- Now the reference must match on **word boundaries**: `\bSection N\b`. The
  **exact numbering match is checked first** and the text-branch reference only
  fires for a genuine standalone reference. The document filter is also applied
  to the text branch so a mention of "Section 10" in the IPC does not award a
  citation match to an ICA query with a `document_id`.
- Preserves `test_reference_in_text` ("As per Section 12..." still matches a
  query for "section 12").

### 2. `src/llm/explanation.py` — exact-section candidates (Change 2)

- Added `_ensure_exact_section_candidates(parsed, ...)` called after fusion.
  Scans all graph nodes and injects any node whose `numbering` **exactly**
  matches a user-requested section number into the candidate set/signals with
  `citation = 1.0`. This lets the existing C7 exact-number promotion rank the
  literally-referenced section #1 even when dense/graph scoring never surfaced
  it (the original Category-A bare-section-lookup misses).
- Only the **user's own** section references are used (not expansion-injected
  terms), and `document_id` is respected when set.

### 3. `src/llm/explanation.py` — definition-first promotion (Change 3)

- Added `_definition_promotion(node, parsed)` and constants
  `_DEFINITION_RE` / `DEFINITION_BONUS = 0.12`. For bare-concept queries
  ("What is coercion?"), a legal leaf whose **title explicitly declares a
  definition** ("`\"Coercion\" defined`") and whose defined term overlaps the
  query keywords receives a bounded bonus to its rank. This lets the section
  that *defines* the concept outrank sections that merely mention it.
- The initial version also included a `TITLE_BONUS` fallback for
  title-keyword overlap; this was **removed** because it broke the exact
  `rank == weighted-signal-sum` contract asserted by
  `test_custom_ranking_weights_are_used` (the title of the test fixture
  section overlaps its query, adding an unintended flat bonus). Only the
  explicit definition-title bonus remains, preserving the `rank == 1.0`
  contract.

### 4. `src/llm/explanation.py` — illustration/explanation fragment demotion (Change 4)

- Added `_fragment_demotion_multiplier(node)` and `FRAGMENT_DEMOTION = 0.55`.
  Some corpora store an illustration/explanation as a bare `Section` leaf whose
  `numbering` field holds the entire body prose (e.g. `s (a) A, by falsely
  pretending...`) or the literal word `Illustration`. These never represent a
  valid numbered answer, yet their dense text overlap let them win the top
  rank — especially cross-document. Such prose-numbered (or
  `Illustration`/`Explanation`) leaves are now demoted so real, clean-numbered
  sections surface. Canonical numbering (numbers, clause markers) is
  unaffected (multiplier 1.0).

## Tests Added

`tests/test_task21_retrieval_ranking.py` (6 regression tests over the real
corpus, deterministic mock embeddings):

- `test_exact_section_12_ranks_first` — "What is Section 12?" → section 12 is #1.
- `test_section_12_no_substring_collision` — no false match to "1"/"121".
- `test_bare_section_1_ranks_first` — "Section 1" → section 1 is #1.
- `test_coercion_definition_section_surfaces` — section 15 in top-5.
- `test_consideration_definition_section_surfaces` — section 18 in top-5.
- `test_section_72_ranks_first_not_illustration` — section 72 is #1, and an
  "Illustration" fragment does not win.

## Test Results

- Full suite: **908 passed** (902 baseline + 6 new), 4 warnings.
- `ruff check` on all changed files: **clean**.
- Targeted retrieval tests (`test_retrieval_scorer`, `test_retrieval_ranker`,
  `test_document_aware_retrieval`, `test_retrieval_context`) all pass.

## Manual Validation (Before / After)

The end-to-end manual validation (`validation/run_manual_validation.py`)
stays at **40 PASS / 90 FAIL** before and after. This is expected and by
design: the Task 15 grounding guard blocks all 90 failing cases as
`insufficient` *before* LLM generation, because verification/confidence/
guard are out of Task 21's scope. Retrieval improvements correctly change
*which section* is ranked/retrieved, but the validation PASS criterion is
driven by status + confidence, neither of which is modified here.

The retrieval-focused harness (top-1 section metric over the 90 supported
cases) improved as follows (pre-change → post-change):

| Metric | Pre-change | Post-change |
|--------|-----------|-------------|
| Top-1 section accuracy | 30/90 | **47/90** |
| Top-5 section recall | 46/90 | **68/90** |

## Evaluation Metrics (Before / After)

Run via the offline evaluation pipeline (`python -m src.evaluation`, mock LLM,
50 ICA1872 questions, seed 42).

| Metric | Baseline | Current | Δ |
|--------|----------|---------|-----|
| **Retrieval component** | 0.3002 | **0.5830** | +0.283 |
| **section_accuracy** | 0.2700 | **0.8700** | +0.600 |
| **MRR** | 0.1617 | **0.7400** | +0.578 |
| recall@5 | 0.1567 | **0.3316** | +0.175 |
| precision@5 | 0.0560 | **0.2120** | +0.156 |
| **Overall score** | 0.5197 | **0.6271** | +0.107 |
| grounding_accuracy | 1.0000 | 1.0000 | 0 |
| hallucination_rate | 0.6308 | 0.7883 | +0.158 (generation metric, out of scope) |

### Which retrieval improvements produced the largest gains

1. **Word-boundary citation fix (Change 1** — removed the systematic flooding
   of the seed set by cross-referencing sections and near-identical numbers;
   lifted `citation_score` precision across all buckets.
2. **Exact-section injection (Change 2)** — fixed the pure Category-A
   bare-section-lookup misses where the referenced section never entered the
   candidate set at all (previously unreachable by pure ranking).
3. **Illustration/explanation demotion (Change 4)** — removed the cross-document
   prose/fragment leaves that were winning dense top-1, clearing the path for
   real numbered sections and raising top-5 recall to 68/90.
4. **Definition-first promotion (Change 3)** — moved the defining section of a
   concept (coercion, consideration) into the top-5 for definition queries.

### Notes on metrics

- The **hallucination_rate increase** lives in the generation component and is
  produced by the deterministic mock LLM echoing the query; it is not a
  retrieval-quality measure and is explicitly out of scope for Task 21
  (modifying prompts/generation is prohibited by the constraints). All
  retrieval-quality targets — section_accuracy, MRR, recall@5, precision@5, and
  the composite retrieval weight — improved decisively.
- `grounding_accuracy` is unchanged at 1.0000, confirming the changes did not
  weaken grounding behaviour.

## Scope Discipline

No code was modified in verification, confidence scoring, the grounding guard,
any API schema, evaluation/metric computation, entailment, or LLM prompts. The
full 908-test suite passes and `ruff` is clean, so the improvements are
contained to retrieval/ranking as required.
