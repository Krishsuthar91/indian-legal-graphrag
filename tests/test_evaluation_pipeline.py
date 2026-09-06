"""End-to-end tests for the evaluation pipeline."""

import json

import pytest

from src.evaluation.calibration import CalibrationMetrics
from src.evaluation.corpus import build_evaluation_service
from src.evaluation.dataset import load_benchmark_csv
from src.evaluation.pipeline import (
    EvaluationConfig,
    EvaluationOutput,
    run_evaluation,
)
from src.evaluation.runner import (
    compute_row_calibration,
    run_questions,
)

EVAL_DOCUMENT_ID = "0940d367554383c5"


@pytest.fixture(scope="module")
def tiny_dataset():
    return load_benchmark_csv()[:5]


@pytest.fixture(scope="module")
def eval_service():
    service, graph = build_evaluation_service(document_id=EVAL_DOCUMENT_ID)
    return service, graph


@pytest.fixture(scope="module")
def sample_items():
    return load_benchmark_csv()[:3]


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


# ---------------------------------------------------------------------------
# Calibration integration tests (Task 8 -- Step 3)
# ---------------------------------------------------------------------------


class TestCalibrationIntegration:
    """Verify calibration is computed and attached to EvaluationOutput."""

    def test_calibration_is_computed(self, tmp_path, tiny_dataset):
        output = run_evaluation(
            EvaluationConfig(
                document_id=EVAL_DOCUMENT_ID,
                results_dir=tmp_path / "cal",
                max_questions=5,
            ),
        )
        assert output.calibration is not None
        assert isinstance(output.calibration, CalibrationMetrics)
        assert output.calibration.total_samples == 5
        assert output.calibration.expected_calibration_error >= 0.0
        assert output.calibration.maximum_calibration_error >= 0.0
        assert 0.0 <= output.calibration.average_confidence <= 1.0
        assert 0.0 <= output.calibration.average_accuracy <= 1.0

    def test_empty_evaluation_still_works(self):
        cal = compute_row_calibration([], [])
        assert cal.total_samples == 0
        assert cal.expected_calibration_error == 0.0
        assert cal.maximum_calibration_error == 0.0
        assert cal.confidence_bins == []

    def test_pipeline_passes_calibration_to_output(self, tmp_path, tiny_dataset):
        output = run_evaluation(
            EvaluationConfig(
                document_id=EVAL_DOCUMENT_ID,
                results_dir=tmp_path / "pipe_cal",
                max_questions=3,
            ),
        )
        assert hasattr(output, "calibration")
        assert output.calibration is not None
        assert output.calibration.total_samples == 3

    def test_backward_compatibility(self):
        """EvaluationOutput without calibration defaults to None."""
        out = EvaluationOutput(
            meta={},
            results=[],
            per_query=[],
            aggregate={},
            performance={},
            scores={},
            raw_json=None,
            raw_csv=None,
            report_path=None,
        )
        assert out.calibration is None

    def test_compute_row_calibration_joins_correctly(self, eval_service, sample_items):
        service, _ = eval_service
        rows = run_questions(service, sample_items)
        per_query = [{"item_id": r.item_id, "answer_accuracy": 0.5} for r in rows]
        cal = compute_row_calibration(rows, per_query)
        assert isinstance(cal, CalibrationMetrics)
        assert cal.total_samples == len(rows)
        for b in cal.confidence_bins:
            assert b.sample_count > 0
            assert 0.0 <= b.average_confidence <= 1.0
