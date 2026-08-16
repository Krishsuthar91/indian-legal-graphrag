# HHGR Research Evaluation Report

| Field | Value |
| --- | --- |
| generated_at | 2026-08-13T15:59:29Z |
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
| Overall | 0.5099 |
| Retrieval (0.4) | 0.2827 |
| Generation (0.4) | 0.5032 |
| Performance (0.2) | 0.9777 |

## Metric Tables

### Retrieval Metrics

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1367 |
| recall_at_10 | 0.1367 |
| precision_at_5 | 0.0480 |
| mrr | 0.1450 |
| section_accuracy | 0.2300 |
| hierarchy_accuracy | 1.0000 |

### Generation Metrics

| Metric | Mean |
| --- | --- |
| answer_accuracy | 0.2514 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.2300 |
| faithfulness | 0.3689 |
| evidence_coverage | 0.8001 |
| hallucination_rate | 0.6311 |

### Performance Metrics

| Metric | Value |
| --- | --- |
| Average Latency (ms) | 111.5220 |
| P95 Latency (ms) | 238.1020 |
| Average Retrieval Time (ms) | 108.4930 |
| Average LLM Time (ms) | 3.0290 |
| Average Ranking Time (ms) | 35.9170 |
| Memory Usage (MB) | 1.7300 |

## Error Analysis

### By Query Type: definition

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.2000 |
| recall_at_10 | 0.2000 |
| precision_at_5 | 0.0933 |
| mrr | 0.2778 |
| section_accuracy | 0.4667 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.1803 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.4667 |
| faithfulness | 0.2879 |
| evidence_coverage | 0.7030 |
| hallucination_rate | 0.7121 |

### By Query Type: section_lookup

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1000 |
| recall_at_10 | 0.1000 |
| precision_at_5 | 0.0200 |
| mrr | 0.1000 |
| section_accuracy | 0.1000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2452 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.1000 |
| faithfulness | 0.3167 |
| evidence_coverage | 0.8069 |
| hallucination_rate | 0.6833 |

### By Query Type: comparison

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0417 |
| recall_at_10 | 0.0417 |
| precision_at_5 | 0.0250 |
| mrr | 0.0625 |
| section_accuracy | 0.0625 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2039 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.0625 |
| faithfulness | 0.4025 |
| evidence_coverage | 0.8419 |
| hallucination_rate | 0.5975 |

### By Query Type: procedure

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0000 |
| recall_at_10 | 0.0000 |
| precision_at_5 | 0.0000 |
| mrr | 0.0000 |
| section_accuracy | 0.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3114 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.0000 |
| faithfulness | 0.4362 |
| evidence_coverage | 0.8377 |
| hallucination_rate | 0.5638 |

### By Query Type: explanation

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.5000 |
| recall_at_10 | 0.5000 |
| precision_at_5 | 0.1200 |
| mrr | 0.3167 |
| section_accuracy | 0.6000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3751 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.6000 |
| faithfulness | 0.4401 |
| evidence_coverage | 0.8670 |
| hallucination_rate | 0.5599 |

### By Query Type: scenario

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0000 |
| recall_at_10 | 0.0000 |
| precision_at_5 | 0.0000 |
| mrr | 0.0000 |
| section_accuracy | 0.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3453 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.0000 |
| faithfulness | 0.4972 |
| evidence_coverage | 0.8913 |
| hallucination_rate | 0.5028 |

### By Difficulty: Easy

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.2059 |
| recall_at_10 | 0.2059 |
| precision_at_5 | 0.0824 |
| mrr | 0.2843 |
| section_accuracy | 0.4118 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2294 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.4118 |
| faithfulness | 0.3548 |
| evidence_coverage | 0.8036 |
| hallucination_rate | 0.6452 |

### By Difficulty: Medium

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1181 |
| recall_at_10 | 0.1181 |
| precision_at_5 | 0.0333 |
| mrr | 0.0868 |
| section_accuracy | 0.1458 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2762 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.1458 |
| faithfulness | 0.3646 |
| evidence_coverage | 0.7873 |
| hallucination_rate | 0.6354 |

### By Difficulty: Hard

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0556 |
| recall_at_10 | 0.0556 |
| precision_at_5 | 0.0222 |
| mrr | 0.0370 |
| section_accuracy | 0.1111 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2267 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.1111 |
| faithfulness | 0.4072 |
| evidence_coverage | 0.8276 |
| hallucination_rate | 0.5928 |

## Failure Categories

| Category | Count | Description |
| --- | --- | --- |
| insufficient_evidence | 0 | grounding guard triggered (evidence below threshold) |
| no_evidence | 0 | no evidence retrieved for the question |
| section_miss | 39 | at least one expected section not surfaced |
| low_confidence | 0 | aggregate confidence below the 0.45 threshold |
| high_hallucination | 42 | hallucination rate above 0.5 |
| ungrounded_citation | 0 | answer cites a source not in the retrieved evidence |
| slow_query | 0 | latency above the p95 for the run |

## Top Failure Examples

| ID | Question | Failure Score | Section Acc. | MRR | Halluc. | Grounding |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-005 | What is coercion as defined under the Act? | 2.9167 | 0.0000 | 0.0000 | 0.9167 | 1.0000 |
| ICA1872-024 | What does Section 27 declare regarding agreements in restraint of trade? | 2.8750 | 0.0000 | 0.0000 | 0.8750 | 1.0000 |
| ICA1872-036 | How may a continuing guarantee be revoked? | 2.8462 | 0.0000 | 0.0000 | 0.8462 | 1.0000 |
| ICA1872-015 | What is a continuing guarantee under the Act? | 2.8333 | 0.0000 | 0.0000 | 0.8333 | 1.0000 |
| ICA1872-016 | According to Section 10, what must be present for an agreement to be a contract? | 2.8125 | 0.0000 | 0.0000 | 0.8125 | 1.0000 |

## Most Successful Queries

| ID | Question | Success Score | Section Acc. | MRR | Faithfulness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-019 | What obligation does Section 65 impose on a person who has received an advantage under a v… | 4.8888 | 1.0000 | 1.0000 | 0.4444 | 1.0000 |
| ICA1872-044 | What happens when one party to a contract prevents the other from performing reciprocal pr… | 4.8888 | 1.0000 | 1.0000 | 0.4444 | 1.0000 |
| ICA1872-014 | How does the Act define an agent and a principal? | 4.7692 | 1.0000 | 1.0000 | 0.3846 | 1.0000 |
| ICA1872-012 | How does the Act define bailment, and who are the bailor and bailee? | 4.7142 | 1.0000 | 1.0000 | 0.3571 | 1.0000 |
| ICA1872-010 | How does the Act define a contract of indemnity? | 4.6154 | 1.0000 | 1.0000 | 0.3077 | 1.0000 |

## Recommendations

1. Retrieval recall is low — increase the adaptive evidence budget, add synonym/expansion terms, or index finer-grained nodes so expected sections can be surfaced.
2. Section accuracy is low — the parsed hierarchy does not expose many of the benchmark sections; improving document parsing granularity would directly raise section accuracy.
3. Hallucination rate is high — reinforce the prompt's grounding rules or route low-confidence queries through the insufficient-evidence guard.
4. Answer accuracy is low — the offline (mock) LLM only echoes the query; run the evaluation with a real provider to measure answer quality.
