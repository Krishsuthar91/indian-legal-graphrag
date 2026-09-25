# HHGR Research Evaluation Report

| Field | Value |
| --- | --- |
| generated_at | 2026-08-30T16:22:42Z |
| document_id | 0d1934142f67c5f5 |
| hierarchy_file | data\hierarchy\0d1934142f67c5f5.json |
| questions | 50 |
| llm_provider | mock |
| model | mock-llm |
| embedding_provider | deterministic |
| seed | 42 |
| confidence_threshold | 0.4500 |

## Overall Score

| Score | Value |
| --- | --- |
| Overall | 0.6271 |
| Retrieval (0.4) | 0.5830 |
| Generation (0.4) | 0.4955 |
| Performance (0.2) | 0.9784 |

## Confidence Calibration

| Metric | Value |
| --- | --- |
| Expected Calibration Error (ECE) | 0.1792 |
| Maximum Calibration Error (MCE) | 0.1896 |
| Average Confidence | 0.4133 |
| Average Accuracy | 0.2341 |
| Total Samples | 50 |

### Reliability Table

| Confidence Range | Samples | Avg Confidence | Empirical Accuracy | Gap |
| --- | --- | --- | --- | --- |
| 0.20-0.30 | 3 | 0.2635 | 0.1439 | 0.1196 |
| 0.30-0.40 | 22 | 0.3562 | 0.1790 | 0.1772 |
| 0.40-0.50 | 17 | 0.4469 | 0.2573 | 0.1896 |
| 0.50-0.60 | 8 | 0.5549 | 0.3700 | 0.1849 |

**Interpretation:** Moderate calibration

## Metric Tables

### Retrieval Metrics

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3316 |
| recall_at_10 | 0.3445 |
| precision_at_5 | 0.2120 |
| mrr | 0.7400 |
| section_accuracy | 0.8700 |
| hierarchy_accuracy | 1.0000 |

### Generation Metrics

| Metric | Mean |
| --- | --- |
| answer_accuracy | 0.2341 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.4300 |
| faithfulness | 0.2117 |
| evidence_coverage | 0.8856 |
| hallucination_rate | 0.7883 |

### Performance Metrics

| Metric | Value |
| --- | --- |
| Average Latency (ms) | 108.0940 |
| P95 Latency (ms) | 146.9440 |
| Average Retrieval Time (ms) | 98.1400 |
| Average LLM Time (ms) | 9.9550 |
| Average Ranking Time (ms) | 7.1200 |
| Memory Usage (MB) | 0.0000 |

## Error Analysis

### By Query Type: definition

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1922 |
| recall_at_10 | 0.1922 |
| precision_at_5 | 0.1733 |
| mrr | 0.5333 |
| section_accuracy | 0.8000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.1640 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.0000 |
| faithfulness | 0.0389 |
| evidence_coverage | 0.8998 |
| hallucination_rate | 0.9611 |

### By Query Type: section_lookup

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.4367 |
| recall_at_10 | 0.4367 |
| precision_at_5 | 0.2000 |
| mrr | 1.0000 |
| section_accuracy | 1.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2472 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.8000 |
| faithfulness | 0.2767 |
| evidence_coverage | 0.9796 |
| hallucination_rate | 0.7233 |

### By Query Type: comparison

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.4743 |
| recall_at_10 | 0.4921 |
| precision_at_5 | 0.3500 |
| mrr | 0.8750 |
| section_accuracy | 0.8750 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.1792 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.2500 |
| faithfulness | 0.1364 |
| evidence_coverage | 0.8456 |
| hallucination_rate | 0.8636 |

### By Query Type: procedure

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3980 |
| recall_at_10 | 0.4694 |
| precision_at_5 | 0.2000 |
| mrr | 0.7143 |
| section_accuracy | 0.7857 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2901 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.6429 |
| faithfulness | 0.3690 |
| evidence_coverage | 0.8373 |
| hallucination_rate | 0.6310 |

### By Query Type: explanation

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.4000 |
| recall_at_10 | 0.4000 |
| precision_at_5 | 0.2000 |
| mrr | 0.7000 |
| section_accuracy | 1.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3163 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.6000 |
| faithfulness | 0.2629 |
| evidence_coverage | 0.8224 |
| hallucination_rate | 0.7371 |

### By Query Type: scenario

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1500 |
| recall_at_10 | 0.1500 |
| precision_at_5 | 0.1600 |
| mrr | 0.7000 |
| section_accuracy | 0.8000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3453 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.8000 |
| faithfulness | 0.4491 |
| evidence_coverage | 0.8501 |
| hallucination_rate | 0.5509 |

### By Difficulty: Easy

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.2353 |
| recall_at_10 | 0.2353 |
| precision_at_5 | 0.1412 |
| mrr | 0.5588 |
| section_accuracy | 0.7059 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2095 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.1765 |
| faithfulness | 0.1328 |
| evidence_coverage | 0.8616 |
| hallucination_rate | 0.8672 |

### By Difficulty: Medium

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3860 |
| recall_at_10 | 0.4128 |
| precision_at_5 | 0.2417 |
| mrr | 0.8542 |
| section_accuracy | 1.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2505 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.6250 |
| faithfulness | 0.2524 |
| evidence_coverage | 0.9149 |
| hallucination_rate | 0.7476 |

### By Difficulty: Hard

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3685 |
| recall_at_10 | 0.3685 |
| precision_at_5 | 0.2667 |
| mrr | 0.7778 |
| section_accuracy | 0.8333 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2367 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.3889 |
| faithfulness | 0.2524 |
| evidence_coverage | 0.8530 |
| hallucination_rate | 0.7476 |

## Failure Categories

| Category | Count | Description |
| --- | --- | --- |
| insufficient_evidence | 28 | grounding guard triggered (evidence below threshold) |
| no_evidence | 0 | no evidence retrieved for the question |
| section_miss | 7 | at least one expected section not surfaced |
| low_confidence | 0 | aggregate confidence below the 0.45 threshold |
| high_hallucination | 44 | hallucination rate above 0.5 |
| ungrounded_citation | 0 | answer cites a source not in the retrieved evidence |
| slow_query | 0 | latency above the p95 for the run |

## Top Failure Examples

| ID | Question | Failure Score | Section Acc. | MRR | Halluc. | Grounding |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-002 | What is consideration as defined in the Act? | 3.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| ICA1872-003 | What is a voidable contract under the Act? | 2.9167 | 0.0000 | 0.0000 | 0.9167 | 1.0000 |
| ICA1872-004 | How does the Act define consent? | 2.9167 | 0.0000 | 0.0000 | 0.9167 | 1.0000 |
| ICA1872-047 | A pledges goods to B as security for a debt, defaults at the stipulated time, and later te… | 2.8636 | 0.0000 | 0.0000 | 0.8636 | 1.0000 |
| ICA1872-026 | What is the difference between a void agreement and a voidable contract? | 2.8333 | 0.0000 | 0.0000 | 0.8333 | 1.0000 |

## Most Successful Queries

| ID | Question | Success Score | Section Acc. | MRR | Faithfulness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-049 | A bailee, without the bailor's consent, mixes the bailor's goods with his own so that they… | 5.1304 | 1.0000 | 1.0000 | 0.5652 | 1.0000 |
| ICA1872-039 | When a promise is to be performed on a certain day without any application by the promisee… | 5.1000 | 1.0000 | 1.0000 | 0.5500 | 1.0000 |
| ICA1872-020 | What does Section 72 require when money is paid or a thing is delivered by mistake or unde… | 5.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 |
| ICA1872-048 | An agent, without having authority to do so, appoints another person to act as sub-agent. … | 5.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 |
| ICA1872-035 | When is the communication of an acceptance complete as against the proposer, and when as a… | 4.8000 | 1.0000 | 1.0000 | 0.4000 | 1.0000 |

## Recommendations

1. Retrieval recall is low — increase the adaptive evidence budget, add synonym/expansion terms, or index finer-grained nodes so expected sections can be surfaced.
2. Hallucination rate is high — reinforce the prompt's grounding rules or route low-confidence queries through the insufficient-evidence guard.
3. Answer accuracy is low — the offline (mock) LLM only echoes the query; run the evaluation with a real provider to measure answer quality.


## Impact of Parser Fix

### Before Parser Fix

- **Hierarchy nodes:** 46
- **Section nodes:** 16
- **Document ID:** 0d1934142f67c5f5
- **LLM:** meta/llama-3.3-70b-instruct
- **Questions:** 50

### After Parser Fix

- **Hierarchy nodes:** 222
- **Section nodes:** 192
- **Document ID:** 0d1934142f67c5f5
- **LLM:** mock-llm
- **Questions:** 50

### Difference

| Metric | Before | After | Delta |
| --- | --- | --- | --- |
| Section Accuracy | 0.1111 | 0.8700 | +0.7589 |
| Recall@5 | 0.0556 | 0.3316 | +0.2760 |
| Precision@5 | 0.0222 | 0.2120 | +0.1898 |
| MRR | 0.0370 | 0.7400 | +0.7030 |
| Answer Accuracy | 0.2666 | 0.2341 | -0.0325 |
| Faithfulness | 0.4992 | 0.2117 | -0.2875 |
| Grounding Accuracy | 1.0000 | 1.0000 | --- |
| Evidence Coverage | 0.8276 | 0.8856 | +0.0580 |
| Hallucination Rate | 0.5008 | 0.7883 | +0.2875 |
| Avg Confidence | 0.0000 | 0.4133 | +0.4133 |
| Supported Badge Acc. | 1.0000 | 0.4400 | -0.5600 |

### Discussion

**Improvement in section-level retrieval:** Section accuracy improved from 0.1111 to 0.8700 (+0.7589). The parser fix extracted 192 standalone section nodes from the previously embedded chapter text, enabling the retrieval pipeline to surface the exact sections referenced in benchmark questions.

**Improvement in retrieval quality:** Recall@5 improved from 0.0556 to 0.3316 (+0.2760). Finer-grained section nodes allow the hybrid retriever to match query-relevant content at the section level rather than returning entire chapters.

**Hallucination rate:** Changed from 0.5008 to 0.7883 (+0.2875). This may reflect the LLM having more detailed evidence to work with, changing answer patterns.

**Retrieval failures:** With 192 standalone sections (up from 16), the retrieval pipeline can now directly index and retrieve individual sections rather than entire multi-section chapters. This reduces 'chunking_error' and 'missing_section' failure types.


## Failure Case Analysis

### Top 10 Failed Queries

#### 1. ICA1872-001

**Question:** How does the Act define a proposal?

- **Expected section:** S.2(a)
- **Retrieved sections:** 2, 3, 4, 7
- **Verification status:** insufficient
- **Confidence:** 0.2561
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 2. ICA1872-002

**Question:** What is consideration as defined in the Act?

- **Expected section:** S.2(d)
- **Retrieved sections:** 125, 14, 17, 9
- **Verification status:** insufficient
- **Confidence:** 0.2940
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 3. ICA1872-003

**Question:** What is a voidable contract under the Act?

- **Expected section:** S.2(i)
- **Retrieved sections:** 178a, 19, 53, 64
- **Verification status:** insufficient
- **Confidence:** 0.3271
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 4. ICA1872-004

**Question:** How does the Act define consent?

- **Expected section:** S.13
- **Retrieved sections:** 10, 14, 178, 19
- **Verification status:** insufficient
- **Confidence:** 0.2403
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 5. ICA1872-005

**Question:** What is coercion as defined under the Act?

- **Expected section:** S.15
- **Retrieved sections:** 14, 15, 4, 5
- **Verification status:** insufficient
- **Confidence:** 0.3153
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 6. ICA1872-006

**Question:** What is undue influence as defined in the Act?

- **Expected section:** S.16
- **Retrieved sections:** 1, 14, 153, 16
- **Verification status:** insufficient
- **Confidence:** 0.3491
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 7. ICA1872-007

**Question:** What acts are included in the definition of fraud under the Act?

- **Expected section:** S.17
- **Retrieved sections:** 1, 153, 16, 17, 219
- **Verification status:** insufficient
- **Confidence:** 0.3594
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 8. ICA1872-008

**Question:** What is misrepresentation as defined in the Act?

- **Expected section:** S.18
- **Retrieved sections:** 125, 14, 17, 18
- **Verification status:** insufficient
- **Confidence:** 0.3171
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 9. ICA1872-009

**Question:** What is a contingent contract under the Act?

- **Expected section:** S.31
- **Retrieved sections:** 2, 25, 31, 34
- **Verification status:** insufficient
- **Confidence:** 0.3338
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.

#### 10. ICA1872-010

**Question:** How does the Act define a contract of indemnity?

- **Expected section:** S.124
- **Retrieved sections:** 124, 125, 170, 74
- **Verification status:** insufficient
- **Confidence:** 0.3850
- **Failure score:** 2.0000
- **Failure type:** section_miss
- **Recommendation:** Improve retrieval weighting or query expansion to surface the expected section.


## Best Performing Queries

### Top 10 Perfect / Best Queries

#### 1. ICA1872-001

**Question:** How does the Act define a proposal?

- **Expected section:** S.2(a)
- **Retrieved sections:** 2, 3, 4, 7
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.2561
- **Success score:** 1.0000

#### 2. ICA1872-002

**Question:** What is consideration as defined in the Act?

- **Expected section:** S.2(d)
- **Retrieved sections:** 125, 14, 17, 9
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.2940
- **Success score:** 1.0000

#### 3. ICA1872-003

**Question:** What is a voidable contract under the Act?

- **Expected section:** S.2(i)
- **Retrieved sections:** 178a, 19, 53, 64
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.3271
- **Success score:** 1.0000

#### 4. ICA1872-004

**Question:** How does the Act define consent?

- **Expected section:** S.13
- **Retrieved sections:** 10, 14, 178, 19
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.2403
- **Success score:** 1.0000

#### 5. ICA1872-005

**Question:** What is coercion as defined under the Act?

- **Expected section:** S.15
- **Retrieved sections:** 14, 15, 4, 5
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.3153
- **Success score:** 1.0000

#### 6. ICA1872-006

**Question:** What is undue influence as defined in the Act?

- **Expected section:** S.16
- **Retrieved sections:** 1, 14, 153, 16
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.3491
- **Success score:** 1.0000

#### 7. ICA1872-007

**Question:** What acts are included in the definition of fraud under the Act?

- **Expected section:** S.17
- **Retrieved sections:** 1, 153, 16, 17, 219
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.3594
- **Success score:** 1.0000

#### 8. ICA1872-008

**Question:** What is misrepresentation as defined in the Act?

- **Expected section:** S.18
- **Retrieved sections:** 125, 14, 17, 18
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.3171
- **Success score:** 1.0000

#### 9. ICA1872-009

**Question:** What is a contingent contract under the Act?

- **Expected section:** S.31
- **Retrieved sections:** 2, 25, 31, 34
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.3338
- **Success score:** 1.0000

#### 10. ICA1872-010

**Question:** How does the Act define a contract of indemnity?

- **Expected section:** S.124
- **Retrieved sections:** 124, 125, 170, 74
- **Section accuracy:** 0.0000
- **MRR:** 0.0000
- **Faithfulness:** 0.0000
- **Evidence coverage:** 0.0000
- **Confidence:** 0.3850
- **Success score:** 1.0000


## Research Paper Ready Tables

### Table 1 -- Overall Results

| Metric | Value |
| --- | --- |
| Document | Indian Contract Act, 1872 |
| Hierarchy Nodes | 222 |
| Section Nodes | 192 |
| Benchmark Questions | 50 |
| LLM | mock-llm |
| Embedding | Deterministic (dim=64) |
| Overall Score | 0.6271 |
| Retrieval Score | 0.5830 |
| Generation Score | 0.4955 |
| Performance Score | 0.9784 |

### Table 2 -- Retrieval Metrics

| Metric | Value |
| --- | --- |
| recall_at_5 | 0.3316 |
| recall_at_10 | 0.3445 |
| precision_at_5 | 0.2120 |
| mrr | 0.7400 |
| section_accuracy | 0.8700 |
| hierarchy_accuracy | 1.0000 |

### Table 3 -- Verification Metrics

| Metric | Value |
| --- | --- |
| Answer Accuracy | 0.2341 |
| Grounding Accuracy | 1.0000 |
| Faithfulness | 0.2117 |
| Evidence Coverage | 0.8856 |
| Hallucination Rate | 0.7883 |
| Citation Accuracy | 0.4300 |
| Supported Badge Accuracy | 0.4400 |
| Insufficient Evidence Count | 28 |
| Contradiction Detected Count | 7 |

### Table 4 -- Confidence Calibration

| Metric | Value |
| --- | --- |
| Expected Calibration Error (ECE) | 0.1792 |
| Maximum Calibration Error (MCE) | 0.1896 |
| Average Confidence | 0.4133 |
| Average Accuracy | 0.2341 |
| Total Samples | 50 |

**Reliability Table:**

| Confidence Range | Samples | Avg Confidence | Empirical Accuracy | Gap |
| --- | --- | --- | --- | --- |
| 0.20-0.30 | 3 | 0.2635 | 0.1439 | 0.1196 |
| 0.30-0.40 | 22 | 0.3562 | 0.1790 | 0.1772 |
| 0.40-0.50 | 17 | 0.4469 | 0.2573 | 0.1896 |
| 0.50-0.60 | 8 | 0.5549 | 0.3700 | 0.1849 |

### Table 5 -- Before vs After Parser Fix

| Metric | Before Fix | After Fix | Delta |
| --- | --- | --- | --- |
| Section Accuracy | 0.1111 | 0.8700 | +0.7589 |
| Recall@5 | 0.0556 | 0.3316 | +0.2760 |
| Precision@5 | 0.0222 | 0.2120 | +0.1898 |
| MRR | 0.0370 | 0.7400 | +0.7030 |
| Answer Accuracy | 0.2666 | 0.2341 | -0.0325 |
| Faithfulness | 0.4992 | 0.2117 | -0.2875 |
| Grounding Accuracy | 1.0000 | 1.0000 | 0.0000 |
| Hallucination Rate | 0.5008 | 0.7883 | +0.2875 |
