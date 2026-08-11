"""End-to-end tests for the evaluation pipeline."""

import json

import pytest

from src.evaluation.dataset import load_benchmark_csv
from src.evaluation.pipeline import (
    EvaluationConfig,
    EvaluationOutput,
    run_evaluation,
)

EVAL_DOCUMENT_ID = "0940d367554383c5"


@pytest.fixture(scope="module")
def tiny_dataset():
    return load_benchmark_csv()[:5]


def test_run_evaluation_end_to_end(tmp_path, tiny_dataset):
    output = run_evaluation(
        EvaluationConfig(
            document_id=EVAL_DOCUMENT_ID,
            results_dir=tmp_path / "results",
            max_questions=5,
        ),
    )
    assert isinstance(output, EvaluationOutput)
    assert output.raw_json.exists()
    assert output.raw_csv.exists()
    assert output.report_path.exists()
    assert output.raw_json.parent == tmp_path / "results"

    payload = json.loads(output.raw_json.read_text(encoding="utf-8"))
    assert payload["meta"]["document_id"] == EVAL_DOCUMENT_ID
    assert len(payload["results"]) == 5

    report_text = output.report_path.read_text(encoding="utf-8")
    assert "## Overall Score" in report_text
    assert "## Metric Tables" in report_text
    assert "## Failure Categories" in report_text
    assert "## Recommendations" in report_text


def test_run_evaluation_respects_max_questions(tmp_path, tiny_dataset):
    output = run_evaluation(
        EvaluationConfig(
            document_id=EVAL_DOCUMENT_ID,
            results_dir=tmp_path / "max5",
            max_questions=5,
        ),
    )
    assert len(output.results) == 5
    payload = json.loads(output.raw_json.read_text(encoding="utf-8"))
    assert len(payload["results"]) == 5
    assert payload["meta"]["questions"] == 5


def test_run_evaluation_with_injected_service(tmp_path, tiny_dataset):
    run_evaluation(
        EvaluationConfig(
            document_id=EVAL_DOCUMENT_ID,
            results_dir=tmp_path / "injected",
            max_questions=3,
        ),
    )
    assert (tmp_path / "injected" / "raw_results.json").exists()


def test_aggregate_and_scores_are_present(tmp_path, tiny_dataset):
    output = run_evaluation(
        EvaluationConfig(
            document_id=EVAL_DOCUMENT_ID,
            results_dir=tmp_path / "agg",
            max_questions=5,
        ),
    )
    assert set(output.scores) == {"overall", "retrieval", "generation", "performance"}
    assert 0.0 <= output.scores["overall"] <= 1.0
    assert "recall_at_5" in output.aggregate
    assert output.performance["average_latency_ms"] >= 0
