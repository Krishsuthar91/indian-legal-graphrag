"""Evaluation pipeline — orchestrates the full benchmark run.

``run_evaluation`` loads the benchmark CSV, builds the offline corpus and the
frontend QA service, answers every question through ``QueryService.answer``,
computes all metrics, writes ``results/raw_results.json`` and
``results/raw_results.csv``, and renders ``results/evaluation_report.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.evaluation.corpus import (
    CONTRACT_ACT_1872_DOCUMENT_ID,
    build_evaluation_service,
)
from src.evaluation.dataset import DEFAULT_BENCHMARK_CSV, load_benchmark_csv
from src.evaluation.metrics.aggregate import (
    compute_per_query_metrics,
    overall_score,
    summarize_metrics,
)
from src.evaluation.metrics.performance import measure_peak_traced_memory, performance_metrics
from src.evaluation.report import build_report, write_report
from src.evaluation.runner import RawResult, run_questions, save_raw_csv, save_raw_json
from src.llm.llm import LLMClient

DEFAULT_RESULTS_DIR = Path("results")
RAW_JSON_FILE = "raw_results.json"
RAW_CSV_FILE = "raw_results.csv"
REPORT_FILE = "evaluation_report.md"


@dataclass
class EvaluationConfig:
    """Configuration for one evaluation run."""

    benchmark_csv: str | Path = DEFAULT_BENCHMARK_CSV
    document_id: str = CONTRACT_ACT_1872_DOCUMENT_ID
    hierarchy_file: str | Path | None = None
    results_dir: str | Path = DEFAULT_RESULTS_DIR
    llm: LLMClient | None = None
    top_k: int | None = None
    confidence_threshold: float | None = None
    require_sufficient_evidence: bool | None = None
    seed: int = 42
    embedding_dim: int = 64
    latency_budget_ms: float = 5000.0
    max_questions: int | None = None

    def resolved_benchmark_csv(self) -> Path:
        return Path(self.benchmark_csv)


@dataclass
class EvaluationOutput:
    """Everything produced by one evaluation run."""

    meta: dict[str, Any]
    results: list[RawResult]
    per_query: list[dict[str, float]]
    aggregate: dict[str, float]
    performance: dict[str, float]
    scores: dict[str, float]
    raw_json: Path
    raw_csv: Path
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "aggregate_metrics": self.aggregate,
            "performance_metrics": self.performance,
            "scores": self.scores,
            "raw_json": str(self.raw_json),
            "raw_csv": str(self.raw_csv),
            "report": str(self.report_path),
        }


def default_contract_act_config(**overrides: Any) -> EvaluationConfig:
    """Default config for the Indian Contract Act, 1872 research benchmark."""
    return EvaluationConfig(**overrides)


def run_evaluation(config: EvaluationConfig | None = None) -> EvaluationOutput:
    """Run the complete evaluation pipeline and return its output."""
    config = config or default_contract_act_config()
    items = load_benchmark_csv(config.resolved_benchmark_csv())
    if config.max_questions is not None:
        items = items[: max(1, config.max_questions)]

    from src.evaluation.corpus import resolve_hierarchy_file

    hierarchy_path = resolve_hierarchy_file(config.document_id, config.hierarchy_file)

    service, graph = build_evaluation_service(
        document_id=config.document_id,
        hierarchy_file=config.hierarchy_file,
        llm=config.llm,
        top_k=config.top_k,
        confidence_threshold=config.confidence_threshold,
        require_sufficient_evidence=config.require_sufficient_evidence,
        seed=config.seed,
        embedding_dim=config.embedding_dim,
    )

    results, peak_traced_bytes = measure_peak_traced_memory(
        lambda: run_questions(service, items)
    )

    per_query = compute_per_query_metrics(graph, items, results)
    performance = performance_metrics(results)
    performance["memory_usage_mb"] = round(peak_traced_bytes / (1024 * 1024), 2)
    aggregate = summarize_metrics(per_query)
    scores = overall_score(
        aggregate,
        performance["average_latency_ms"],
        latency_budget_ms=config.latency_budget_ms,
    )

    meta = {
        "document_id": config.document_id,
        "hierarchy_file": str(hierarchy_path),
        "questions": len(items),
        "llm_provider": service.llm.name,
        "model": service.llm.model,
        "embedding_provider": "deterministic",
        "seed": config.seed,
        "confidence_threshold": service.engine.threshold,
        "top_k": service.top_k,
        "adaptive_top_k": service.engine.adaptive,
        "require_sufficient_evidence": service.require_sufficient_evidence,
    }

    results_dir = Path(config.results_dir)
    raw_json = save_raw_json(results, results_dir / RAW_JSON_FILE, meta=meta)
    raw_csv = save_raw_csv(results, results_dir / RAW_CSV_FILE)

    report = build_report(
        meta=meta,
        per_query_rows=per_query,
        performance=performance,
        scores=scores,
        p95_latency_ms=performance["p95_latency_ms"],
        raw_rows=results,
    )
    report_path = write_report(results_dir / REPORT_FILE, report)

    return EvaluationOutput(
        meta=meta,
        results=results,
        per_query=per_query,
        aggregate=aggregate,
        performance=performance,
        scores=scores,
        raw_json=raw_json,
        raw_csv=raw_csv,
        report_path=report_path,
    )
