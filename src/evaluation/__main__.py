"""CLI entry point: ``python -m src.evaluation``.

Runs the full evaluation pipeline over the Indian Contract Act, 1872
benchmark and prints a compact summary. Optional ``--max-questions`` limits
the run (useful for smoke tests).
"""

from __future__ import annotations

import argparse
import json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.evaluation",
        description="Run the HHGR research evaluation benchmark.",
    )
    parser.add_argument(
        "--benchmark-csv",
        default=None,
        help="path to the benchmark CSV (default: data/eval/contract_act_1872_benchmark.csv)",
    )
    parser.add_argument(
        "--document-id",
        default=None,
        help="hierarchy document id to evaluate (default: the Contract Act 1872 document)",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="output directory (default: results/)",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="limit the number of questions evaluated (smoke tests)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="random seed for the deterministic corpus (default: 42)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the summary as JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    from src.evaluation.pipeline import EvaluationConfig, run_evaluation

    config = EvaluationConfig(
        benchmark_csv=args.benchmark_csv or "data/eval/contract_act_1872_benchmark.csv",
        document_id=args.document_id or "0d1934142f67c5f5",
        results_dir=args.results_dir or "results",
        seed=args.seed,
        max_questions=args.max_questions,
    )
    output = run_evaluation(config)
    if args.json:
        print(json.dumps(output.to_dict(), indent=2))
    else:
        print(f"evaluated {output.meta['questions']} questions")
        print(f"overall score      {output.scores['overall']:.4f}")
        print(f"retrieval          {output.scores['retrieval']:.4f}")
        print(f"generation         {output.scores['generation']:.4f}")
        print(f"performance        {output.scores['performance']:.4f}")
        print(f"avg latency (ms)   {output.performance['average_latency_ms']:.2f}")
        print(f"raw json           {output.raw_json}")
        print(f"raw csv            {output.raw_csv}")
        print(f"report             {output.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
