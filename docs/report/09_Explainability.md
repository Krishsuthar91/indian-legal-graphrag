# 09 — Explainability, Verification, and Provenance

Explainability is a first-class subsystem, not a cosmetic layer. Every answer carries the
evidence it used, the reasoning that produced it, a confidence score, a verification decision,
and a persisted provenance record that can be re-fetched later.

Primary sources: `src/llm/explanation.py` (the largest module), `src/llm/service.py`,
`src/llm/provenance.py`, `src/llm/schemas.py`, `docs/VerificationFramework.md`.

---

## 9.1 What "explainable" means here

An answer is considered explainable when a reviewer can determine:

1. **Which evidence** was used (node ids, section numbers, text spans).
2. **Why it was ranked** above alternatives (per-signal scores).
3. **How the answer was produced** (a step-by-step reasoning chain).
4. **How trustworthy it is** (confidence + verification badge).
5. **Where it came from** (a durable provenance record).

All five are returned by `POST /api/v1/query` and rendered by the frontend; four of them are
also produced by `POST /api/v1/explain` without calling the LLM.

---

## 9.2 The explainability engine (`src/llm/explanation.py`)

Responsibilities:

- Re-fuse retrieval signals into a usefulness ranking (five signals: dense, graph, hierarchy,
  keyword, citation — `explanation.py:62-76`).
- Build the reasoning chain (`explanation.py:567-872`).
- Apply interpretation rules: definition promotion, fragment demotion, chain relevance
  (`explanation.py:1107-1123`).
- Compute confidence factors and the composite confidence score.
- Detect counter-authority markers (`explanation.py:1433-1452`).
- Assemble the verification decision trace (`explanation.py:2021-2061`).

### 9.2.1 Evidence ranking (usefulness, not just similarity)

The engine re-orders evidence by usefulness:

- **Definition promotion** — definitional sections are lifted when the query is definitional.
- **Fragment demotion** — tiny or context-free fragments are pushed down.
- **Chain relevance** — evidence that participates in the reasoning chain is scored higher.
- **Five-signal fusion** — `dense/graph/hierarchy/keyword/citation` weighted scores.

Each retained evidence item exposes the individual signal contributions, which is what makes
the ranking auditable.

---

## 9.3 Reasoning chain

`explanation.py:567-872` emits an ordered list of reasoning steps. Representative steps:

| Step | Description |
|------|-------------|
| Parse | Normalised query, detected Act, extracted references |
| Expand | Corpus-verified expansions (nothing invented) |
| Retrieve | Dense + lexical seeds, counts |
| Graph score | HHGR signal contributions for the top candidates |
| Propagate | Hierarchy context pulled in |
| Rank | Fusion order and threshold decision |
| Verify | Sufficiency, relevance, entailment results |
| Generate | LLM call + grounding guard outcome |
| Answer | Final answer with citations |

The frontend renders this as `ReasoningChain.tsx`.

---

## 9.4 Verification framework

Verified by `src/llm/service.py:275-328` and documented in `docs/VerificationFramework.md`.
Stages, in order:

1. **Sufficiency** — is there enough evidence at all? Measured with a **bigram Dice**
   overlap between the query and retrieved evidence; below threshold → insufficient.
2. **LLM relevance judge (with fallback)** — a model-based judge scores whether each evidence
   unit is relevant to the query; a deterministic fallback applies if the judge is unavailable.
3. **Claim-level entailment** — splits the generated answer into claims and checks each claim
   against its cited evidence (supported / unsupported).
4. **Confidence calibration** — maps raw confidence to a calibrated value using ECE/MCE
   (`src/llm/explanation.py:1857-2017`, `src/evaluation/calibration.py`).
5. **Counter-authority detection** — detects overruled/superseded/repealed/void markers
   (`explanation.py:1433-1452`).
6. **Verification badge** — collapses the above into one of five labels (below).

### 9.4.1 Verification badges

| Badge | Meaning |
|-------|---------|
| `supported` | Answer is grounded in sufficient, relevant, entailed evidence |
| `insufficient_evidence` | Some evidence exists but is not sufficient to support the answer |
| `contradicted` | Evidence contradicts the generated claim (or contains counter-authority) |
| `no_evidence` | Retrieval returned nothing above the confidence threshold |
| `no_answer` | The system declined to answer (grounding guard / LLM refusal) |

The badge is rendered by `VerificationBadge.tsx` with distinct, accessible colours.

---

## 9.5 Grounding guard

`src/llm/service.py:275-328`

Before an answer is returned, the grounding guard compares the generated text against the
retrieved evidence. If the answer makes claims not supported by evidence, or the evidence is
insufficient/contradicted, the guard downgrades the badge and (where appropriate) returns a
grounded refusal rather than an unsupported answer. This is the mechanism that turns "the
model said so" into "the corpus supports this".

---

## 9.6 Confidence

### 9.6.1 Confidence factors

The composite confidence is built from explicit factors (each surfaced to the user):

- retrieval strength (top fused score),
- signal agreement (do dense/graph/hierarchy agree?),
- sufficiency score (bigram Dice),
- entailment support ratio (supported claims / total claims),
- counter-authority penalty (markers present),
- calibration adjustment.

### 9.6.2 Calibration

`src/llm/explanation.py:1857-2017` and `src/evaluation/calibration.py` compute **ECE**
(Expected Calibration Error) and **MCE** (Maximum Calibration Error), with reliability
diagrams produced by the evaluation pipeline (`results/reliability_diagram.png`). Calibration
ensures a stated confidence of, say, 0.8 empirically corresponds to ~80% correctness.

### 9.6.3 Confidence gauge

The frontend visualises composite confidence with a Recharts radial gauge
(`ConfidenceGauge.tsx`), colour-banded by badge.

---

## 9.7 Counter-authority detection

`explanation.py:1433-1452` scans provision text and metadata for markers indicating the
authority is no longer good law:

- "overruled", "superseded", "repealed", "void", "struck down", "held unconstitutional",
  "not in force".

When detected, the provision is flagged, its effective rank is reduced, and the answer's
verification is biased toward caution (potentially `contradicted`). The frontend shows these
markers in `ProvenancePanel.tsx`.

---

## 9.8 Provenance

`src/llm/provenance.py`

Every query persists a provenance record to `data/provenance/<id>.json` (**271 files**
present). The record contains:

| Field | Contents |
|-------|----------|
| `provenance_id` | Stable id used by `GET /api/v1/provenance/{id}` |
| `query` / `parsed_query` | Raw and structured query (act, references, intent, language) |
| `retrieved_nodes` | Node ids, section numbers, titles, snippets |
| `signal_scores` | Per-signal scores for every retained evidence item |
| `hierarchy_paths` | Document→Chapter→Section→Clause paths |
| `citations` | Numbered citations with targets |
| `counter_authority` | Detected markers |
| `verification` | Badge, stage results, decision trace |
| `confidence` | Composite score + factors |
| `model` | Provider/model metadata, prompt version, timestamps |

Provenance is **immutable** once written and re-fetchable, which is essential for audit and for
reproducing a past answer.

---

## 9.9 Explain vs. Query endpoints

| Endpoint | LLM call | Returns |
|----------|----------|---------|
| `POST /api/v1/query` | yes | Answer + evidence + reasoning + verification + provenance id |
| `POST /api/v1/explain` | **no** | Evidence + reasoning + verification (explainability only) |
| `GET /api/v1/provenance/{id}` | no | Full persisted provenance record |

This separation lets clients inspect retrieval/verification (e.g. in Settings or during
debugging) without paying for generation, and it is what the offline evaluation harness relies
on for deterministic explainability metrics.

---

## 9.10 Anti-hallucination measures (summary)

1. Corpus-verified query expansion (`query_expansion.py`) — cannot invent sections.
2. Sufficiency gate before generation (`service.py`).
3. Grounding guard after generation (`service.py:275-328`).
4. Claim-level entailment verification.
5. Counter-authority detection.
6. Verification badge + calibrated confidence shown to the user.
7. Immutable provenance for after-the-fact audit.

---

## 9.11 Key explainability files quick reference

| File | Responsibility |
|------|----------------|
| `src/llm/explanation.py` | Reasoning chain, evidence ranking, confidence, verification trace |
| `src/llm/service.py` | Orchestration + grounding guard |
| `src/llm/provenance.py` | Provenance assembly + persistence |
| `src/llm/schemas.py` | Explanation/verification Pydantic schemas |
| `src/evaluation/calibration.py` | ECE/MCE calibration |
| `docs/VerificationFramework.md` | Human-readable verification spec |
| `docs/Task22_Verification_Audit.md`, `Task23_Relevance_Judge_Investigation.md` | Verification investigations |
