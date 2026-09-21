# HHGR Research Evaluation Report

| Field | Value |
| --- | --- |
| generated_at | 2026-09-20T08:21:26Z |
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
| Overall | 0.6768 |
| Retrieval (0.4) | 0.6129 |
| Generation (0.4) | 0.5998 |
| Performance (0.2) | 0.9586 |

## Metric Tables

### Retrieval Metrics

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.4006 |
| recall_at_10 | 0.4046 |
| precision_at_5 | 0.2320 |
| mrr | 0.7400 |
| section_accuracy | 0.9000 |
| hierarchy_accuracy | 1.0000 |

### Generation Metrics

| Metric | Mean |
| --- | --- |
| answer_accuracy | 0.2446 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.8000 |
| faithfulness | 0.3242 |
| evidence_coverage | 0.9060 |
| hallucination_rate | 0.6758 |

### Performance Metrics

| Metric | Value |
| --- | --- |
| Average Latency (ms) | 206.9400 |
| P95 Latency (ms) | 312.9450 |
| Average Retrieval Time (ms) | 196.4900 |
| Average LLM Time (ms) | 10.4500 |
| Average Ranking Time (ms) | 13.5670 |
| Memory Usage (MB) | 2.1600 |

## Error Analysis

### By Query Type: definition

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3189 |
| recall_at_10 | 0.3189 |
| precision_at_5 | 0.2133 |
| mrr | 0.7667 |
| section_accuracy | 0.9333 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.1809 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.7333 |
| faithfulness | 0.2268 |
| evidence_coverage | 0.9717 |
| hallucination_rate | 0.7732 |

### By Query Type: section_lookup

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.4950 |
| recall_at_10 | 0.4950 |
| precision_at_5 | 0.2200 |
| mrr | 0.9500 |
| section_accuracy | 1.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2442 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 1.0000 |
| faithfulness | 0.3464 |
| evidence_coverage | 0.9770 |
| hallucination_rate | 0.6536 |

### By Query Type: comparison

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.5827 |
| recall_at_10 | 0.5827 |
| precision_at_5 | 0.3750 |
| mrr | 0.8750 |
| section_accuracy | 1.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.1958 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.8750 |
| faithfulness | 0.3096 |
| evidence_coverage | 0.9084 |
| hallucination_rate | 0.6904 |

### By Query Type: procedure

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3143 |
| recall_at_10 | 0.3429 |
| precision_at_5 | 0.1714 |
| mrr | 0.3571 |
| section_accuracy | 0.5714 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3114 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.5714 |
| faithfulness | 0.4126 |
| evidence_coverage | 0.7090 |
| hallucination_rate | 0.5874 |

### By Query Type: explanation

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.5000 |
| recall_at_10 | 0.5000 |
| precision_at_5 | 0.2400 |
| mrr | 0.9000 |
| section_accuracy | 1.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3427 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.8000 |
| faithfulness | 0.3562 |
| evidence_coverage | 0.8946 |
| hallucination_rate | 0.6438 |

### By Query Type: scenario

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1867 |
| recall_at_10 | 0.1867 |
| precision_at_5 | 0.1600 |
| mrr | 0.4000 |
| section_accuracy | 0.8000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3231 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.8000 |
| faithfulness | 0.4401 |
| evidence_coverage | 0.8501 |
| hallucination_rate | 0.5599 |

### By Difficulty: Easy

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3618 |
| recall_at_10 | 0.3618 |
| precision_at_5 | 0.1882 |
| mrr | 0.7059 |
| section_accuracy | 0.8824 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2195 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.7059 |
| faithfulness | 0.2706 |
| evidence_coverage | 0.9361 |
| hallucination_rate | 0.7294 |

### By Difficulty: Medium

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.4470 |
| recall_at_10 | 0.4554 |
| precision_at_5 | 0.2500 |
| mrr | 0.8229 |
| section_accuracy | 0.9792 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2690 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.9375 |
| faithfulness | 0.3518 |
| evidence_coverage | 0.9289 |
| hallucination_rate | 0.6482 |

### By Difficulty: Hard

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.3500 |
| recall_at_10 | 0.3500 |
| precision_at_5 | 0.2667 |
| mrr | 0.5833 |
| section_accuracy | 0.7222 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2270 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.6111 |
| faithfulness | 0.3519 |
| evidence_coverage | 0.7881 |
| hallucination_rate | 0.6481 |

## Failure Categories

| Category | Count | Description |
| --- | --- | --- |
| insufficient_evidence | 16 | grounding guard triggered (evidence below threshold) |
| no_evidence | 0 | no evidence retrieved for the question |
| section_miss | 6 | at least one expected section not surfaced |
| low_confidence | 0 | aggregate confidence below the 0.45 threshold |
| high_hallucination | 45 | hallucination rate above 0.5 |
| ungrounded_citation | 0 | answer cites a source not in the retrieved evidence |
| slow_query | 0 | latency above the p95 for the run |

## Top Failure Examples

| ID | Question | Failure Score | Section Acc. | MRR | Halluc. | Grounding |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-047 | A pledges goods to B as security for a debt, defaults at the stipulated time, and later te… | 3.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| ICA1872-015 | What is a continuing guarantee under the Act? | 2.7500 | 0.0000 | 0.0000 | 0.7500 | 1.0000 |
| ICA1872-035 | When is the communication of an acceptance complete as against the proposer, and when as a… | 2.6000 | 0.0000 | 0.0000 | 0.6000 | 1.0000 |
| ICA1872-040 | How is a payment applied when a debtor owing several debts does not indicate which debt it… | 2.5263 | 0.0000 | 0.0000 | 0.5263 | 1.0000 |
| ICA1872-036 | How may a continuing guarantee be revoked? | 1.9423 | 0.5000 | 0.2500 | 0.6923 | 1.0000 |

## Retrieval Failure Analysis

### Failure Type Summary

| Failure Type | Count | Percentage | Examples |
| --- | --- | --- | --- |
| missing_section | 4 | 66.7% | What is a continuing guarantee under the Act?; When is the communication of an acceptance … |
| partial_match | 2 | 33.3% | How may a continuing guarantee be revoked?; How is a voidable contract rescinded, and what… |

### Top Recommendations

| Recommendation | Count |
| --- | --- |
| Improve retrieval weighting or query expansion. | 4 |
| Increase top_k or improve ranking so all expected sections surface. | 2 |

## Most Successful Queries

| ID | Question | Success Score | Section Acc. | MRR | Faithfulness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-039 | When a promise is to be performed on a certain day without any application by the promisee… | 5.1000 | 1.0000 | 1.0000 | 0.5500 | 1.0000 |
| ICA1872-019 | What obligation does Section 65 impose on a person who has received an advantage under a v… | 5.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 |
| ICA1872-017 | What does Section 25 say about when an agreement without consideration is not void? | 4.7695 | 1.0000 | 1.0000 | 0.4118 | 0.9459 |
| ICA1872-006 | What is undue influence as defined in the Act? | 4.7692 | 1.0000 | 1.0000 | 0.3846 | 1.0000 |
| ICA1872-010 | How does the Act define a contract of indemnity? | 4.7692 | 1.0000 | 1.0000 | 0.3846 | 1.0000 |

## Recommendations

1. Retrieval recall is low — increase the adaptive evidence budget, add synonym/expansion terms, or index finer-grained nodes so expected sections can be surfaced.
2. Hallucination rate is high — reinforce the prompt's grounding rules or route low-confidence queries through the insufficient-evidence guard.
3. Answer accuracy is low — the offline (mock) LLM only echoes the query; run the evaluation with a real provider to measure answer quality.
