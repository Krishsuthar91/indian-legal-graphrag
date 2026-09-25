# Evaluation

The HHGR evaluation framework provides reproducible benchmarking across retrieval quality, generation faithfulness, and system performance. It operates in two modes: an offline deterministic mode (no API keys required) and a production NVIDIA LLM mode.

## Benchmark Datasets

### Contract Act 1872 Benchmark (`data/eval/contract_act_1872_benchmark.csv`)

- **Questions:** 50
- **Document:** Indian Contract Act, 1872 (`0d1934142f67c5f5`)
- **Query Types:** definition, section_lookup, comparison, procedure, explanation, scenario
- **Difficulty:** Easy, Medium, Hard
- **Columns:** ID, Question, Query_Type, Difficulty, Expected_Section, Expected_Keywords, Expected_Answer_Summary

### Gold Standard Dataset (`data/eval/gold/`)

- **Total Items:** 34
- **Domains:** 5 (Contract Act, BNS, BNSS, BSA, Supreme Court Judgments)
- **Grounded Items:** 10 (Contract Act, with node-level relevance labels)
- **Ungrounded Probes:** 24 (6 per domain, scored via citation matching)

| Domain | Items | Grounded | Scoring Method |
|--------|-------|----------|----------------|
| Contract Act | 10 | Yes | Node-level relevance labels |
| BNS (Bharatiya Nyaya Sanhita) | 6 | No | Citation string matching |
| BNSS (Bharatiya Nagarik Suraksha Sanhita) | 6 | No | Citation string matching |
| BSA (Bharatiya Sakshya Adhiniyam) | 6 | No | Citation string matching |
| Supreme Court Judgments | 6 | No | Citation string matching |

## Evaluation Pipelines

### 1. Production Evaluation (`scripts/run_final_evaluation.py`)

Runs the full 50-question benchmark against the NVIDIA LLM (Llama 3.1 8B Instruct).

```bash
python -m scripts.run_final_evaluation
```

**Output:**
- `results/raw_results.json` — per-query results (465KB)
- `results/raw_results.csv` — CSV format (308KB)
- `results/evaluation_report.md` — comprehensive report with paper-ready tables
- `results/reliability_diagram.png` — calibration plot

**Features:**
- Cached evaluation (skips API calls if results exist)
- Before/After comparison with previous benchmark
- Retrieval failure analysis
- Confidence calibration (ECE, MCE, reliability diagram)
- Paper-ready tables (5 tables)

### 2. Offline Deterministic Evaluation (`eval/cli.py`)

Runs entirely offline with mock LLM and deterministic embeddings. Fully reproducible.

```bash
python -m eval.cli --config data/eval/config/experiment.json --out evaluation
python -m eval.cli --quick --out evaluation  # First 3 items only
```

**Output:**
- `evaluation/reports/benchmark.json` — full JSON results
- `evaluation/reports/benchmark.md` — markdown report
- `evaluation/reports/per_query.csv` — per-query breakdown
- `evaluation/figures/` — SVG + PNG charts

### 3. Reproducibility Script (`scripts/reproduce.sh`)

One-command setup that creates a venv, installs dependencies, runs the benchmark, and executes tests.

```bash
bash scripts/reproduce.sh
```

## Metrics

### Retrieval Metrics (`src/evaluation/metrics/retrieval.py`)

| Metric | Description |
|--------|-------------|
| Recall@K | Proportion of relevant items in top-K results |
| Precision@K | Proportion of top-K results that are relevant |
| MRR | Mean Reciprocal Rank of first relevant result |
| Section Accuracy | Whether the top-1 result matches the expected section |
| Hierarchy Accuracy | Whether results are ancestors/descendants of expected section |

### Generation Metrics (`src/evaluation/metrics/generation.py`)

| Metric | Description |
|--------|-------------|
| Answer Accuracy | Whether the generated answer matches expected answer semantics |
| Grounding Accuracy | Whether all cited sections exist in the knowledge graph |
| Faithfulness | Proportion of answer claims supported by retrieved evidence |
| Evidence Coverage | Proportion of expected evidence actually retrieved |
| Hallucination Rate | Rate of unsupported or fabricated claims |

### Performance Metrics (`src/evaluation/metrics/performance.py`)

| Metric | Description |
|--------|-------------|
| Average Latency | Mean end-to-end response time |
| P95 Latency | 95th percentile response time |
| Retrieval Time | Time spent in retrieval pipeline |
| LLM Time | Time spent in LLM inference |

### Calibration Metrics (`src/evaluation/calibration.py`)

| Metric | Description |
|--------|-------------|
| ECE | Expected Calibration Error — average gap between confidence and accuracy |
| MCE | Maximum Calibration Error — worst-bin gap |
| Average Confidence | Mean predicted confidence across all queries |
| Average Accuracy | Mean empirical accuracy across all queries |

## Results

### Deterministic Benchmark (50 questions, offline, mock LLM)

| Metric | Before Parser Fix | After Parser Fix | Delta |
|--------|-------------------|------------------|-------|
| Overall Score | 0.4185 | **0.6271** | +0.2086 |
| Section Accuracy | 0.1111 | **0.8700** | +0.7589 |
| MRR | 0.0370 | **0.7400** | +0.7030 |
| Recall@5 | 0.0556 | **0.3316** | +0.2760 |
| Hallucination Rate | 0.5008 | **0.7883** | +0.2875 |
| Grounding Accuracy | 1.0000 | **1.0000** | — |
| Avg Latency | 2909ms | **108ms** | -2801ms |

**Key Finding:** The parser fix (hierarchy 46→222 nodes, 16→192 section nodes) was the primary driver of improvement, particularly for section accuracy (+683%) and MRR (+1900%).

> **Note:** This benchmark runs offline with a deterministic embedding provider and mock LLM, so it is fully reproducible. Retrieval and grounding metrics (Section Accuracy, MRR, Grounding Accuracy) are deterministic signals of pipeline quality. Answer-related metrics (Hallucination Rate, Faithfulness, Answer Accuracy) reflect the mock LLM's grounding behaviour only and are not representative of production NVIDIA model answer quality.

### Calibration Results

| Metric | Value | Interpretation |
|--------|-------|----------------|
| ECE | 0.1792 | Moderate calibration gap |
| MCE | 0.1896 | Worst bin gap |
| Avg Confidence | 0.4133 | System is appropriately cautious |
| Avg Accuracy | 0.2341 | Room for improvement (mock LLM) |

## Running Tests

```bash
# All tests (908)
pytest -q

# Evaluation-specific tests
pytest tests/test_evaluation_pipeline.py tests/test_evaluation_runner.py tests/test_evaluation_report.py -v

# Query expansion tests (corpus-dependent)
pytest tests/test_query_expansion.py tests/test_query_expansion_integration.py -v
```

## Configuration

### Evaluation Config (`data/eval/config/experiment.json`)

```json
{
  "experiment": {
    "seed": 42,
    "top_k": 5,
    "runs": 3,
    "embedding": {
      "provider": "deterministic",
      "force_deterministic": true
    },
    "hybrid_weights": {
      "dense": 0.4,
      "graph": 0.35,
      "hierarchy": 0.25
    },
    "confidence_threshold": 0.45
  }
}
```

### Production Config (`deploy/env/.env.development`)

Key evaluation-related settings:
- `LLM_PROVIDER=nvidia`
- `LLM_MODEL=nvidia/nemotron-3-super-120b-a12b`
- `QA_TOP_K=5`
- `QA_CONFIDENCE_THRESHOLD=0.45`
- `QA_INDEX_IN_MEMORY=true`
