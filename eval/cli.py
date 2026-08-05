"""Module 10 — evaluation CLI.

Runs the full offline benchmark from the experiment config and writes benchmark
reports (JSON, CSV, Markdown, PDF) plus research figures under ``evaluation/``.

Example::

    python -m eval.cli --config data/eval/config/experiment.json --quick
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eval.figures import run_all_figures
from eval.harness import BenchmarkOutput, benchmark_from_config
from eval.reports import (
    metric_label,
    write_csv,
    write_json,
    write_markdown,
    write_pdf,
)


def _float_cells(row: dict[str, Any], keys: list[str]) -> list[Any]:
    cells: list[Any] = []
    for key in keys:
        value = row.get(key, "")
        cells.append(f"{value:.4f}" if isinstance(value, float) else value)
    return cells


def _retrieval_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "system",
        "items",
        "recall_at_k",
        "precision_at_k",
        "hit_rate_at_k",
        "mrr",
        "map",
        "ndcg_at_k",
        "mean_ms",
        "p50_ms",
        "p95_ms",
        "throughput_qps",
    ]
    return {
        "title": "Retrieval Accuracy & Latency by System",
        "headers": [metric_label(key) for key in keys],
        "rows": [
            [
                row.get(key, "") if key in ("system", "items") else _fmt(row.get(key))
                for key in keys
            ]
            for row in rows
        ],
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _explainability_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "item_id",
        "citation_accuracy",
        "hierarchy_correctness",
        "graph_path_accuracy",
        "provenance_completeness",
        "evidence_coverage",
        "counter_authority_f1",
        "confidence",
    ]
    return {
        "title": "HHGR Explainability Metrics (per query)",
        "headers": [metric_label(key) for key in keys],
        "rows": [
            [
                row.get(key, "") if key == "item_id" else _fmt(row.get(key))
                for key in keys
            ]
            for row in rows
        ],
    }


def _ragas_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "system",
        "item_id",
        "faithfulness",
        "answer_relevancy",
        "context_recall",
        "context_precision",
        "answer_correctness",
    ]
    return {
        "title": "RAGAS-style Generation Metrics (offline surrogate)",
        "headers": [metric_label(key) for key in keys],
        "rows": [
            [
                row.get(key, "") if key in ("system", "item_id") else _fmt(row.get(key))
                for key in keys
            ]
            for row in rows
        ],
    }


def _ablation_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "ablation",
        "label",
        "recall_at_k",
        "mrr",
        "map",
        "ndcg_at_k",
        "explain_citation_accuracy",
    ]
    return {
        "title": "Ablation Study",
        "headers": [metric_label(key) for key in keys],
        "rows": [
            [
                row.get(key, "") if key in ("ablation", "label") else _fmt(row.get(key))
                for key in keys
            ]
            for row in rows
        ],
    }


def write_reports(
    output: BenchmarkOutput,
    reports_dir: str | Path,
    figures_dir: str | Path,
) -> dict[str, str]:
    """Write every benchmark report format and return the created paths."""
    reports_dir = Path(reports_dir)
    figures_dir = Path(figures_dir)

    paths: dict[str, str] = {}
    paths["json"] = str(write_json(output.to_dict(), reports_dir / "benchmark.json"))
    paths["retrieval_csv"] = str(write_csv(output.retrieval, reports_dir / "retrieval_summary.csv"))
    paths["per_query_csv"] = str(write_csv(output.per_query, reports_dir / "per_query.csv"))
    paths["explainability_csv"] = str(
        write_csv(output.explainability, reports_dir / "explainability.csv")
    )
    paths["ragas_csv"] = str(write_csv(output.ragas, reports_dir / "ragas.csv"))
    paths["ablation_csv"] = str(write_csv(output.ablation_rows, reports_dir / "ablation.csv"))

    sections = [_retrieval_table(output.retrieval)]
    if output.explainability:
        sections.append(_explainability_table(output.explainability))
    if output.ragas:
        sections.append(_ragas_table(output.ragas))
    if output.ablation_rows:
        sections.append(_ablation_table(output.ablation_rows))
    paths["markdown"] = str(
        write_markdown(
            sections,
            reports_dir / "benchmark.md",
            title="Explaintool HHGR Evaluation Report",
        )
    )

    figures = []
    for figure_path in sorted((figures_dir / "figures").glob("*.png")):
        figures.append(str(figure_path))
    meta = {
        "dataset": output.meta.get("dataset"),
        "document_id": output.meta.get("document_id"),
        "top_k": output.meta.get("top_k"),
        "items_evaluated": output.meta.get("items_evaluated"),
        "seed": output.meta.get("seed"),
        "elapsed_seconds": output.meta.get("elapsed_seconds"),
        "generated_at": output.meta.get("generated_at"),
    }
    paths["pdf"] = str(
        write_pdf(
            reports_dir / "benchmark.pdf",
            "Explaintool HHGR Evaluation Report",
            sections,
            figures,
            meta,
        )
    )
    return paths


def run(
    config_path: str | Path,
    out_dir: str | Path,
    quick: bool = False,
    dataset_file: str | None = None,
    seed: int | None = None,
    no_figures: bool = False,
) -> dict[str, Any]:
    """Execute a full benchmark run and persist all outputs."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if seed is not None:
        config["experiment"]["seed"] = seed

    output = benchmark_from_config(
        config,
        out_dir=out_dir,
        quick=quick,
        dataset_file=dataset_file,
    )

    out = Path(out_dir)
    reports_dir = out / "reports"
    figures_dir = out
    reports = write_reports(output, reports_dir, figures_dir)

    figures: dict[str, dict[str, str]] = {}
    if not no_figures:
        from eval.corpus import build_corpus

        corpus = build_corpus(
            document_id=config["dataset"]["document_id"],
            hierarchy_file=config["dataset"].get("hierarchy_file"),
            weights=config["experiment"].get("hybrid_weights"),
            seed=config["experiment"].get("seed", 42),
        )
        try:
            figures = run_all_figures(figures_dir / "figures", output, corpus)
        finally:
            corpus.close()
        reports["figures_json"] = str(write_json(figures, figures_dir / "figures" / "figures.json"))

    return {
        "output": output,
        "reports": reports,
        "figures": figures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explaintool HHGR evaluation harness")
    parser.add_argument(
        "--config",
        default="data/eval/config/experiment.json",
        help="path to the experiment config JSON",
    )
    parser.add_argument("--out", default="evaluation", help="output directory")
    parser.add_argument("--quick", action="store_true", help="limit to the first 3 items")
    parser.add_argument("--dataset", default=None, help="specific gold dataset file to run")
    parser.add_argument("--seed", type=int, default=None, help="override the experiment seed")
    parser.add_argument("--no-figures", action="store_true", help="skip figure generation")
    args = parser.parse_args(argv)

    try:
        result = run(
            config_path=args.config,
            out_dir=args.out,
            quick=args.quick,
            dataset_file=args.dataset,
            seed=args.seed,
            no_figures=args.no_figures,
        )
    except Exception as exc:  # pragma: no cover - CLI error surface
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 1

    meta = result["output"].meta
    print(f"evaluation complete: dataset={meta['dataset']} items={meta['items_evaluated']} "
          f"elapsed={meta['elapsed_seconds']}s")
    for key, path in sorted(result["reports"].items()):
        print(f"  {key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
