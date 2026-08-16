# HHGR Research Evaluation Report

| Field | Value |
| --- | --- |
| generated_at | 2026-08-15T15:19:00Z |
| document_id | 0d1934142f67c5f5 |
| hierarchy_file | data\hierarchy\0d1934142f67c5f5.json |
| questions | 50 |
| llm_provider | nvidia |
| model | meta/llama-3.1-8b-instruct |
| embedding_provider | deterministic |
| seed | 42 |
| confidence_threshold | 0.4500 |

## Overall Score

| Score | Value |
| --- | --- |
| Overall | 0.4185 |
| Retrieval (0.4) | 0.3002 |
| Generation (0.4) | 0.5369 |
| Performance (0.2) | 0.4182 |

## Metric Tables

### Retrieval Metrics

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1567 |
| recall_at_10 | 0.1567 |
| precision_at_5 | 0.0560 |
| mrr | 0.1617 |
| section_accuracy | 0.2700 |
| hierarchy_accuracy | 1.0000 |

### Generation Metrics

| Metric | Mean |
| --- | --- |
| answer_accuracy | 0.2468 |
| grounding_accuracy | 0.9600 |
| citation_accuracy | 0.2100 |
| faithfulness | 0.4987 |
| evidence_coverage | 0.8071 |
| hallucination_rate | 0.5013 |

### Performance Metrics

| Metric | Value |
| --- | --- |
| Average Latency (ms) | 2909.0110 |
| P95 Latency (ms) | 3370.7900 |
| Average Retrieval Time (ms) | 154.4090 |
| Average LLM Time (ms) | 2754.6020 |
| Average Ranking Time (ms) | 45.9250 |
| Memory Usage (MB) | 1.9200 |

## Error Analysis

### By Query Type: definition

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.2667 |
| recall_at_10 | 0.2667 |
| precision_at_5 | 0.1200 |
| mrr | 0.3222 |
| section_accuracy | 0.6000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2079 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.4667 |
| faithfulness | 0.4636 |
| evidence_coverage | 0.7282 |
| hallucination_rate | 0.5364 |

### By Query Type: section_lookup

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1000 |
| recall_at_10 | 0.1000 |
| precision_at_5 | 0.0200 |
| mrr | 0.1000 |
| section_accuracy | 0.1000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2577 |
| grounding_accuracy | 0.9000 |
| citation_accuracy | 0.1000 |
| faithfulness | 0.4702 |
| evidence_coverage | 0.8069 |
| hallucination_rate | 0.5298 |

### By Query Type: comparison

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0417 |
| recall_at_10 | 0.0417 |
| precision_at_5 | 0.0250 |
| mrr | 0.0625 |
| section_accuracy | 0.0625 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2484 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.0625 |
| faithfulness | 0.5323 |
| evidence_coverage | 0.8419 |
| hallucination_rate | 0.4677 |

### By Query Type: procedure

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0000 |
| recall_at_10 | 0.0000 |
| precision_at_5 | 0.0000 |
| mrr | 0.0000 |
| section_accuracy | 0.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2668 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.0000 |
| faithfulness | 0.5351 |
| evidence_coverage | 0.8377 |
| hallucination_rate | 0.4649 |

### By Query Type: explanation

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.5000 |
| recall_at_10 | 0.5000 |
| precision_at_5 | 0.1200 |
| mrr | 0.3500 |
| section_accuracy | 0.6000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.3104 |
| grounding_accuracy | 0.8000 |
| citation_accuracy | 0.4000 |
| faithfulness | 0.5474 |
| evidence_coverage | 0.8614 |
| hallucination_rate | 0.4526 |

### By Query Type: scenario

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0000 |
| recall_at_10 | 0.0000 |
| precision_at_5 | 0.0000 |
| mrr | 0.0000 |
| section_accuracy | 0.0000 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2475 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.0000 |
| faithfulness | 0.5079 |
| evidence_coverage | 0.8913 |
| hallucination_rate | 0.4921 |

### By Difficulty: Easy

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.2059 |
| recall_at_10 | 0.2059 |
| precision_at_5 | 0.0824 |
| mrr | 0.2843 |
| section_accuracy | 0.4118 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2275 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.4118 |
| faithfulness | 0.4927 |
| evidence_coverage | 0.8286 |
| hallucination_rate | 0.5073 |

### By Difficulty: Medium

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.1597 |
| recall_at_10 | 0.1597 |
| precision_at_5 | 0.0500 |
| mrr | 0.1215 |
| section_accuracy | 0.2292 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2530 |
| grounding_accuracy | 0.9167 |
| citation_accuracy | 0.1042 |
| faithfulness | 0.5029 |
| evidence_coverage | 0.7842 |
| hallucination_rate | 0.4971 |

### By Difficulty: Hard

| Metric | Mean |
| --- | --- |
| recall_at_5 | 0.0556 |
| recall_at_10 | 0.0556 |
| precision_at_5 | 0.0222 |
| mrr | 0.0370 |
| section_accuracy | 0.1111 |
| hierarchy_accuracy | 1.0000 |
| answer_accuracy | 0.2666 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.1111 |
| faithfulness | 0.4992 |
| evidence_coverage | 0.8276 |
| hallucination_rate | 0.5008 |

## Failure Categories

| Category | Count | Description |
| --- | --- | --- |
| insufficient_evidence | 0 | grounding guard triggered (evidence below threshold) |
| no_evidence | 0 | no evidence retrieved for the question |
| section_miss | 37 | at least one expected section not surfaced |
| low_confidence | 0 | aggregate confidence below the 0.45 threshold |
| high_hallucination | 23 | hallucination rate above 0.5 |
| ungrounded_citation | 2 | answer cites a source not in the retrieved evidence |
| slow_query | 0 | latency above the p95 for the run |

## Top Failure Examples

| ID | Question | Failure Score | Section Acc. | MRR | Halluc. | Grounding |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-024 | What does Section 27 declare regarding agreements in restraint of trade? | 3.7541 | 0.0000 | 0.0000 | 0.7541 | 0.0000 |
| ICA1872-045 | What is the legal effect when both parties to an agreement are under a mistake as to a mat… | 3.4605 | 0.0000 | 0.0000 | 0.4605 | 0.0000 |
| ICA1872-015 | What is a continuing guarantee under the Act? | 2.7593 | 0.0000 | 0.0000 | 0.7593 | 1.0000 |
| ICA1872-028 | How does fraud under Section 17 differ from misrepresentation under Section 18? | 2.6176 | 0.0000 | 0.0000 | 0.6176 | 1.0000 |
| ICA1872-016 | According to Section 10, what must be present for an agreement to be a contract? | 2.5970 | 0.0000 | 0.0000 | 0.5970 | 1.0000 |

## Most Successful Queries

| ID | Question | Success Score | Section Acc. | MRR | Faithfulness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| ICA1872-044 | What happens when one party to a contract prevents the other from performing reciprocal pr… | 5.2272 | 1.0000 | 1.0000 | 0.6136 | 1.0000 |
| ICA1872-014 | How does the Act define an agent and a principal? | 5.2184 | 1.0000 | 1.0000 | 0.6092 | 1.0000 |
| ICA1872-010 | How does the Act define a contract of indemnity? | 5.1086 | 1.0000 | 1.0000 | 0.5543 | 1.0000 |
| ICA1872-012 | How does the Act define bailment, and who are the bailor and bailee? | 5.0834 | 1.0000 | 1.0000 | 0.5417 | 1.0000 |
| ICA1872-019 | What obligation does Section 65 impose on a person who has received an advantage under a v… | 4.8732 | 1.0000 | 1.0000 | 0.4366 | 1.0000 |

## Recommendations

1. Retrieval recall is low — increase the adaptive evidence budget, add synonym/expansion terms, or index finer-grained nodes so expected sections can be surfaced.
2. Section accuracy is low — the parsed hierarchy does not expose many of the benchmark sections; improving document parsing granularity would directly raise section accuracy.
3. Hallucination rate is high — reinforce the prompt's grounding rules or route low-confidence queries through the insufficient-evidence guard.
4. Answer accuracy is low — the offline (mock) LLM only echoes the query; run the evaluation with a real provider to measure answer quality.
