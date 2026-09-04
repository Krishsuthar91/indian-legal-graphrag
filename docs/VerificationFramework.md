# Verification Framework

The HHGR verification framework is a multi-stage pipeline that ensures answers are only reported as "Supported" when backed by actual retrieved evidence. It prevents hallucinated or unsupported answers from receiving high confidence scores.

## Overview

```
Retrieved Evidence ──▶ Evidence Sufficiency ──┐
                                              ├──▶ Verification Badge ──▶ Confidence Score
Generated Answer ──▶ Citation Entailment ─────┤
                                              │
Evidence Chunks ──▶ Evidence Relevance ───────┘
                                              │
                                              ▼
                                    VerificationTrace (Audit Trail)
```

## Components

### 1. Evidence Sufficiency (`src/llm/explanation.py`)

**Purpose:** Measures whether the retrieved evidence contains enough information to answer the query.

**Algorithm:**
- Strips question boilerplate (common phrases like "what is", "explain", "under the act") using regex patterns
- Computes Dice coefficient of character bigrams between the cleaned query and evidence text
- Normalizes to [0.0, 1.0]

**Threshold:** ≥ 0.30 considered sufficient (tuned for short legal text segments)

**Implementation:** `_compute_evidence_sufficiency()` in `src/llm/explanation.py`

### 2. Evidence Relevance (`src/llm/explanation.py`)

**Purpose:** Scores each evidence chunk for relevance to the query using an LLM judge with deterministic fallback.

**Algorithm:**
- **Primary (LLM):** Sends each evidence chunk to the LLM with a structured prompt asking for a 0.0–1.0 relevance score
- **Fallback (Deterministic):** When LLM is unavailable, computes keyword overlap between query and evidence using tokenized intersection / union

**Dataclass:** `EvidenceRelevance` with fields:
- `scores: list[float]` — per-chunk relevance scores
- `mean_score: float` — average relevance
- `min_score: float` — minimum relevance
- `judge_method: str` — "llm" or "deterministic"

**Implementation:** `EvidenceRelevance` dataclass and `_compute_evidence_relevance()` in `src/llm/explanation.py`

### 3. Citation Entailment (`src/llm/explanation.py`)

**Purpose:** Verifies that claims made in the generated answer are actually supported by the retrieved evidence.

**Algorithm:**
- `_extract_claims()` splits the answer into individual sentences (claims)
- For each claim, checks entailment against the evidence using keyword matching and structural overlap
- Returns a `ClaimResult` per claim with `entailed: bool`, `claim: str`, `evidence_ref: str`
- Overall entailment score = proportion of entailed claims

**Dataclass:** `CitationEntailment` with fields:
- `results: list[ClaimResult]` — per-claim results
- `overall: float` — proportion of entailed claims (0.0–1.0)
- `total_claims: int`
- `entailed_claims: int`

**Implementation:** `CitationEntailment`, `ClaimResult` dataclasses and `_compute_citation_entailment()` in `src/llm/explanation.py`

### 4. Verification Badge (`src/llm/explanation.py`)

**Purpose:** Produces a final verification status using 5 priority rules.

**Priority Rules (evaluated in order):**

| Priority | Condition | Badge | Status |
|----------|-----------|-------|--------|
| 1 | No answer generated | `no_answer` | Answer generation failed |
| 2 | No evidence retrieved | `no_evidence` | Zero evidence chunks |
| 3 | Contradiction detected | `contradicted` | Evidence contradicts answer |
| 4 | Insufficient evidence | `insufficient_evidence` | Evidence below sufficiency threshold |
| 5 | All checks pass | `supported` | Answer is grounded in evidence |

**Entanglement Sentinel:** When entailment is not yet computed (e.g., during `explain()` before answer generation), the badge uses `citation_entailment_overall = -1.0` as a sentinel and skips the entailment check.

**Thresholds:**
- Sufficiency threshold: 0.30
- Relevance threshold: 0.30

**Implementation:** `_assess_validity()` in `src/llm/explanation.py`

### 5. Confidence Calibration (`src/llm/explanation.py`)

**Purpose:** Produces a calibrated confidence score that reflects actual answer reliability.

**Formula:**
```
confidence = 0.35 × entailment + 0.30 × relevance + 0.20 × sufficiency + 0.15 × retrieval_base
```

**Weight Redistribution (when entailment unavailable):**
```
relevance  = 0.30 + 0.35 × (0.30 / 0.65)
sufficiency = 0.20 + 0.35 × (0.20 / 0.65)
retrieval_base = 0.15 + 0.35 × (0.15 / 0.65)
```

**Hard Rules (applied after formula):**
1. `contradiction_found` → cap at 0.20
2. `status == insufficient_evidence` → cap at 0.45
3. `status == no_evidence` → set to 0.0
4. `status == no_answer` → set to 0.0

**Labels (5-tier):**
| Range | Label |
|-------|-------|
| 0.80–1.00 | very_high |
| 0.60–0.79 | high |
| 0.40–0.59 | medium |
| 0.20–0.39 | low |
| 0.00–0.19 | very_low |

**Implementation:** `_score_confidence()` (instance method) in `src/llm/explanation.py`

### 6. Verification Trace (`src/llm/schemas.py`)

**Purpose:** Records a structured audit trail of every verification decision.

**Dataclass:** `VerificationTrace` with fields:
- `decision_path: list[dict]` — ordered list of verification steps, each containing:
  - `step: str` — step name (e.g., "evidence_sufficiency", "verification_badge")
  - `passed: bool` — whether the check passed
  - `value: float` — computed metric value
  - `threshold: float` — threshold used for comparison
  - `details: dict` — additional context

**Attachment:** Attached to `ExplanationResult`, `ExplanationResponse`, and `QueryResponse` as an optional field.

**Serialization:** Uses `VerificationTraceSchema` (Pydantic) for API responses.

**Implementation:** `VerificationTrace` in `src/llm/schemas.py`

## Integration Points

### In `ExplainabilityEngine.explain()`

The verification pipeline executes in this order:
1. Evidence sufficiency computed from query + evidence
2. Evidence relevance computed via LLM judge (before confidence)
3. Confidence computed using all signals
4. Verification badge assessed using sufficiency, relevance, and confidence factors
5. Citation entailment computed post-answer-generation
6. Verification trace appended with all step results

### In `_score_confidence()`

Changed from `@staticmethod` to instance method to access verification results. Computation order:
1. Evidence relevance computed BEFORE confidence
2. `_assess_validity()` reads `verification_status` from confidence factors

### Key Confidence Factor Keys

| Key | Description |
|-----|-------------|
| `retrieval_base` | Base score from retrieval quality |
| `evidence_relevance` | Mean relevance score from EvidenceRelevance |
| `evidence_sufficiency` | Sufficiency score from Dice coefficient |
| `citation_entailment` | Entailment proportion from CitationEntailment |
| `verification_status` | Badge status string |
| `contradiction_found` | Boolean flag |
| `final_adjustment` | Post-rule adjustment delta |
| `n_evidence` | Number of evidence chunks |
| `matched_keywords` | Number of matched keywords |

## Test Coverage

Verification framework tests are in `tests/test_confidence_calibration.py`:
- Sufficiency threshold tests
- Relevance judge tests
- Entailment claim extraction tests
- Badge priority rule tests
- Confidence formula tests (with and without entailment)
- Trace serialization tests
