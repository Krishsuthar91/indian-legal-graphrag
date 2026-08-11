"""Research evaluation framework for the HHGR QA pipeline.

Offline-only: builds a deterministic corpus, runs every benchmark question
through the exact frontend QA code path (``QueryService.answer``), collects
raw per-question results, computes retrieval / generation / performance
metrics, and writes a markdown report. Nothing in ``src/evaluation`` is used
by the QA runtime — it is a purely additive, backward-compatible package.
"""

from __future__ import annotations

from src.evaluation.dataset import (
    BenchmarkItem,
    load_benchmark_csv,
)
from src.evaluation.pipeline import (
    EvaluationConfig,
    EvaluationOutput,
    default_contract_act_config,
    run_evaluation,
)

__all__ = [
    "BenchmarkItem",
    "EvaluationConfig",
    "EvaluationOutput",
    "default_contract_act_config",
    "load_benchmark_csv",
    "run_evaluation",
]
