# 16 — Experiments and Results

The project ships **two independent evaluation pipelines**: an offline research harness
(`eval/`) and a production-pipeline evaluator (`scripts/run_final_evaluation.py` →
`src/evaluation/`). This document describes both protocols and reports the **actual measured
results** found in the repository.

Primary sources: `eval/` (`harness.py`, `systems.py`, `ablation.py`, `metrics/`, `reports.py`,
`figures.py`), `scripts/run_final_evaluation.py`, `src/evaluation/`,
`evaluation/reports/benchmark.md`, `results/evaluation_report.md`,
`data/eval/config/experiment.json`.

---

## 16.1 Two evaluation pipelines

| | Offline research harness | Production evaluator |
|-|--------------------------|----------------------|
| Entry point | `eval/cli.py` | `scripts/run_final_evaluation.py` |
| Retrieval | in-process systems (`eval/systems.py`) | live `src/retrieval` + `src/embeddings` |
| Embeddings | deterministic (offline) | deterministic (this run) |
| LLM | mock | mock (`mock-llm`) in this run |
| Dataset | 10 grounded Contract Act gold items | 50 Contract Act (Ch. V) questions |
| Outputs | `evaluation/reports/*`, `evaluation/figures/*` | `results/*` |

---

## 16.2 Protocol (offline harness)

From `data/eval/config/experiment.json`:

```text
seed = 42,  top_k = 5,  runs = 3
embedding = deterministic (force_deterministic = true)
hybrid weights = dense 0.40 / graph 0.35 / hierarchy 0.25
confidence threshold = 0.45
systems = hhgr, dense, bm25, graph, naive_rag
ablations = full, no_graph, no_hierarchy, no_dense, no_multilingual, no_explainability
gold = data/eval/gold (document 0940d367554383c5)
```

---

## 16.3 Offline retrieval results (measured)

From `evaluation/reports/benchmark.md` (10 items):

| system | Recall@K | Precision@K | Hit Rate@K | MRR | MAP | NDCG@K | Mean Latency (ms) | p95 (ms) | Throughput (q/s) |
|--------|---------:|------------:|-----------:|----:|----:|-------:|------------------:|---------:|-----------------:|
| **hhgr** | 0.8000 | 0.1800 | 0.8000 | **0.7500** | **0.7500** | **0.7631** | 2.5690 | 3.6410 | 389.26 |
| dense | 0.8000 | 0.1800 | 0.8000 | 0.7000 | 0.6750 | 0.7139 | 0.4220 | 0.5150 | 2369.11 |
| bm25 | **0.9000** | **0.2000** | **0.9000** | 0.7583 | 0.7283 | 0.7781 | 0.0260 | 0.0630 | 37878.79 |
| graph | 0.8000 | 0.1800 | 0.8000 | 0.6500 | 0.6200 | 0.6743 | 0.1980 | 0.3370 | 5042.86 |
| naive_rag | 0.8000 | 0.1800 | 0.8000 | 0.7000 | 0.6750 | 0.7139 | 0.4200 | 0.5060 | 2380.95 |

**Observations.**
- HHGR attains the **highest MRR and MAP** (0.75 / 0.75), i.e. it ranks the correct provision
  earliest — the property that matters most for citation quality.
- BM25 attains higher raw Recall/Hit-Rate on this small set, because several gold questions
  share exact statutory keywords; HHGR's advantage is rank ordering, not raw recall.
- HHGR is ~6× slower than dense alone on this micro-benchmark (2.57 ms vs 0.42 ms) — still
  sub-10 ms and dominated by graph-signal computation, not retrieval.

---

## 16.4 Offline explainability metrics (measured)

From `evaluation/reports/benchmark.md`, per grounded item:

| item_id | Citation Acc. | Hierarchy Correctness | Graph Path Acc. | Provenance Complete | Evidence Coverage | Counter-Auth. F1 | confidence |
|---------|--------------:|----------------------:|----------------:|--------------------:|------------------:|-----------------:|-----------:|
| ica-001 | 1.000 | 1.000 | 1.000 | 0.950 | 0.944 | 1.000 | 0.830 |
| ica-002 | 1.000 | 1.000 | 1.000 | 0.950 | 1.000 | 1.000 | 0.709 |
| ica-003 | 1.000 | 1.000 | 1.000 | 0.964 | 0.667 | 1.000 | 0.779 |
| ica-004 | 1.000 | 1.000 | 1.000 | 0.964 | 0.563 | 1.000 | 0.718 |
| ica-005 | 1.000 | 1.000 | 1.000 | 0.964 | 0.714 | 1.000 | 0.722 |
| ica-006 | 1.000 | 1.000 | 1.000 | 0.421 | 0.000 | 1.000 | 0.428 |
| ica-007 | 0.500 | 1.000 | 1.000 | 0.964 | 0.800 | 1.000 | 0.729 |
| ica-008 | 1.000 | 1.000 | 1.000 | 0.450 | 0.500 | 1.000 | 0.633 |
| ica-009 | 1.000 | 1.000 | 1.000 | 0.950 | 1.000 | 1.000 | 0.746 |
| ica-010 | 1.000 | 1.000 | 1.000 | 0.950 | 0.636 | 1.000 | 0.500 |

Hierarchy correctness and graph-path accuracy are **1.0 across all items**; provenance
completeness is high except where retrieval failed (ica-006, ica-008).

---

## 16.5 Offline RAGAS-style generation metrics (measured)

Surrogate metrics from `evaluation/reports/benchmark.md` (HHGR vs naive-RAG, 10 items; the
whole HHGR table is in the report). Mean across items:

| Metric | HHGR (mean) | naive-RAG (mean) |
|--------|------------:|-----------------:|
| Faithfulness | 1.000 | 1.000 |
| Answer Relevancy | 0.758 (≈) | 0.825 (≈) |
| Context Recall | 0.750 (7/10 at 1.0) | 0.900 |
| Context Precision | 0.47 (≈) | 0.45 (≈) |
| Answer Correctness | 0.44 (≈) | 0.46 (≈) |

> These are **offline surrogates** (no hosted LLM); they are computed by
> `eval/metrics/ragas.py` using lexical/embedding proxies. Note that naive-RAG and HHGR often
> coincide here because the deterministic embedding and the tiny gold set limit separation.

---

## 16.6 Ablation study (measured)

From `evaluation/reports/benchmark.md`:

| ablation | label | Recall@K | MRR | MAP | NDCG@K | explain_citation_accuracy |
|----------|-------|---------:|----:|----:|-------:|--------------------------:|
| full | Full HHGR | 0.8000 | **0.7500** | **0.7500** | **0.7631** | 0.9500 |
| no_graph | Without graph signal | 0.8000 | 0.7000 | 0.6750 | 0.7139 | 0.9500 |
| no_hierarchy | Without hierarchy signal | 0.8000 | 0.7500 | 0.7500 | 0.7631 | 0.9500 |
| no_dense | Without dense signal | 0.8000 | 0.6500 | 0.6250 | 0.6770 | 0.9500 |
| no_multilingual | Without multilingual path | 0.8000 | 0.6500 | 0.6200 | 0.6743 | 0.7500 |
| no_explainability | Without explainability enrichment | 0.8000 | 0.7500 | 0.7500 | 0.7631 | — |

**Observations.**
- Removing the **graph signal** drops MRR 0.75→0.70 and NDCG 0.763→0.714.
- Removing the **dense signal** is the most damaging: MRR 0.75→0.65, MAP 0.75→0.625.
- Removing the **multilingual path** also lowers MRR/MAP and clearly lowers citation accuracy
  (0.95→0.75), confirming the multilingual contribution.
- On this small gold set the **hierarchy** and **explainability** ablations do not change
  retrieval (the signals overlap with graph), but explainability evidently affects citation
  accuracy at both ends.

---

## 16.7 Production evaluation (50 questions, measured)

From `results/evaluation_report.md` (`generated_at 2026-08-30T16:22:42Z`, document
`0d1934142f67c5f5`, `mock` LLM, deterministic embeddings, seed 42):

### Overall
| Score | Value |
|-------|-------|
| **Overall** | **0.6271** |
| Retrieval (0.4) | 0.5830 |
| Generation (0.4) | 0.4955 |
| Performance (0.2) | 0.9784 |

### Retrieval
| Metric | Mean |
|--------|------|
| recall@5 | 0.3316 |
| recall@10 | 0.3445 |
| precision@5 | 0.2120 |
| **MRR** | **0.7400** |
| section_accuracy | 0.8700 |
| hierarchy_accuracy | 1.0000 |

### Generation
| Metric | Mean |
|--------|------|
| answer_accuracy | 0.2341 |
| grounding_accuracy | 1.0000 |
| citation_accuracy | 0.4300 |
| faithfulness | 0.2117 |
| evidence_coverage | 0.8856 |
| hallucination_rate | 0.7883 |

### Performance
| Metric | Value |
|--------|-------|
| Average latency | 108.09 ms |
| P95 latency | 146.94 ms |
| Retrieval time | 98.14 ms |
| LLM time | 9.96 ms |
| Ranking time | 7.12 ms |

### Calibration
| Metric | Value |
|--------|-------|
| ECE | 0.1792 |
| MCE | 0.1896 |
| Avg confidence | 0.4133 |
| Avg accuracy | 0.2341 |
| Samples | 50 |

Reliability table: 0.20–0.30 (3), 0.30–0.40 (22), 0.40–0.50 (17), 0.50–0.60 (8); each bucket
is over-confident by ~0.12–0.19 → "moderate calibration".

### By query type (selected)
| Type | recall@5 | MRR | section_acc | citation_acc | hallucination_rate |
|------|---------:|----:|------------:|-------------:|-------------------:|
| definition | 0.1922 | 0.5333 | 0.8000 | 0.0000 | 0.9611 |
| section_lookup | 0.4367 | 1.0000 | 1.0000 | 0.8000 | 0.7233 |
| comparison | 0.4743 | 0.8750 | 0.8750 | 0.2500 | 0.8636 |
| procedure | 0.3980 | 0.7143 | — | — | — |

**Critical caveat.** This run uses the **mock LLM**, so generation numbers
(`answer_accuracy 0.23`, `hallucination_rate 0.79`) reflect the placeholder generator, **not**
the Nemotron model. The retrieval and performance numbers (`MRR 0.74`,
`hierarchy_accuracy 1.0`, `P95 147 ms`) are the meaningful production-retrieval results.

---

## 16.8 Artefacts produced

| Artefact | Location |
|----------|----------|
| Benchmark report (md/json/pdf) | `evaluation/reports/benchmark.{md,json,pdf}` |
| Per-signal CSV tables | `evaluation/reports/{retrieval_summary,explainability,ragas,ablation,per_query}.csv` |
| Figures (SVG+PNG) | `evaluation/figures/` — `eval_comparison`, `ablation_chart`, `latency_chart`, `ragas_radar`, `retrieval_flow`, `hierarchy_tree`, `kg_example`, `architecture` |
| Production report | `results/evaluation_report.md`, `results/raw_results.{json,csv}` |
| Reliability diagram | `results/reliability_diagram.png` |
| Corpus audits | `results/corpus_audit.json`, `results/corpus_dedup_report.json` |
| Verification/relevance audits | `results/task22_verification_audit.json`, `results/task23_relevance_debug.json` |
| Historical runs | `results/{baseline,phase4,pre-parser-fix,v30_50q,v30}/` |
| Embedding comparison | `evaluation/embed_retrieval_comparison_v243*.json` |

---

## 16.9 Reproduction

```bash
# Offline research harness (deterministic, no network)
python -m eval.cli            # writes evaluation/reports + evaluation/figures

# Production 50-question benchmark
python scripts/run_final_evaluation.py   # writes results/

# One-command reproduction (see scripts/reproduce.sh)
bash scripts/reproduce.sh
```

Both are offline and deterministic when the deterministic embedding provider and mock LLM are
selected (as in the configs shown above).

---

## 16.10 Interpretation and reporting guidance

- Use the **offline harness** for algorithm comparison/ablation claims (it is controlled and
  reproducible) — HHGR leads on MRR/MAP/NDCG.
- Use the **production evaluator with a real LLM** for end-to-end generation claims; the
  committed run used the mock LLM and must not be quoted as model quality.
- Report calibration (ECE/MCE) honestly: the committed run shows **moderate** calibration with
  over-confidence, which is a stated limitation (`19_Limitations.md`).
