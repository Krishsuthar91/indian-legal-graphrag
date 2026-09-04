"""Tests for confidence calibration metrics (Task 8 -- Step 2)."""

from __future__ import annotations

import pytest

from src.evaluation.calibration import (
    compute_calibration_metrics,
)


def _row(confidence: float, answer_accuracy: float) -> dict:
    return {"confidence": confidence, "answer_accuracy": answer_accuracy}


class TestPerfectCalibration:
    def test_perfectly_calibrated(self):
        data = [_row(0.5, 0.5), _row(0.5, 0.5), _row(0.8, 0.8), _row(0.2, 0.2)]
        m = compute_calibration_metrics(data)
        assert m.expected_calibration_error == pytest.approx(0.0, abs=1e-6)
        assert m.maximum_calibration_error == pytest.approx(0.0, abs=1e-6)
        assert m.total_samples == 4
        assert m.average_confidence == pytest.approx(0.5, abs=1e-6)
        assert m.average_accuracy == pytest.approx(0.5, abs=1e-6)


class TestOverConfident:
    def test_over_confident(self):
        data = [_row(0.9, 0.3)] * 10
        m = compute_calibration_metrics(data)
        assert m.expected_calibration_error == pytest.approx(0.6, abs=1e-6)
        assert m.maximum_calibration_error == pytest.approx(0.6, abs=1e-6)
        assert m.average_confidence == pytest.approx(0.9, abs=1e-6)
        assert m.average_accuracy == pytest.approx(0.3, abs=1e-6)
        assert len(m.confidence_bins) == 1
        assert m.confidence_bins[0].sample_count == 10


class TestUnderConfident:
    def test_under_confident(self):
        data = [_row(0.2, 0.8)] * 10
        m = compute_calibration_metrics(data)
        assert m.expected_calibration_error == pytest.approx(0.6, abs=1e-6)
        assert m.maximum_calibration_error == pytest.approx(0.6, abs=1e-6)
        assert m.average_confidence == pytest.approx(0.2, abs=1e-6)
        assert m.average_accuracy == pytest.approx(0.8, abs=1e-6)


class TestEmptyDataset:
    def test_empty(self):
        m = compute_calibration_metrics([])
        assert m.expected_calibration_error == 0.0
        assert m.maximum_calibration_error == 0.0
        assert m.average_confidence == 0.0
        assert m.average_accuracy == 0.0
        assert m.total_samples == 0
        assert m.confidence_bins == []


class TestSingleBin:
    def test_single_bin(self):
        data = [_row(0.45, 0.4), _row(0.45, 0.5), _row(0.45, 0.4)]
        m = compute_calibration_metrics(data)
        assert len(m.confidence_bins) == 1
        b = m.confidence_bins[0]
        assert b.lower_bound == pytest.approx(0.4, abs=1e-4)
        assert b.upper_bound == pytest.approx(0.5, abs=1e-4)
        assert b.sample_count == 3
        assert b.average_confidence == pytest.approx(0.45, abs=1e-6)
        assert b.empirical_accuracy == pytest.approx(0.433333, abs=1e-4)


class TestMixedBins:
    def test_mixed_bins(self):
        data = [
            _row(0.05, 0.0), _row(0.15, 0.1), _row(0.25, 0.3),
            _row(0.35, 0.4), _row(0.45, 0.5), _row(0.55, 0.6),
            _row(0.65, 0.7), _row(0.75, 0.8), _row(0.85, 0.9),
            _row(0.95, 1.0),
        ]
        m = compute_calibration_metrics(data)
        assert m.total_samples == 10
        assert len(m.confidence_bins) == 10
        assert m.expected_calibration_error == pytest.approx(0.05, abs=1e-4)
        # All gaps are |acc - conf| = 0.05
        assert m.maximum_calibration_error == pytest.approx(0.05, abs=1e-4)


class TestECECalculation:
    def test_ece_two_bins(self):
        # Bin [0.0, 0.1): 3 samples, avg_conf=0.05, avg_acc=0.2, gap=0.15
        # Bin [0.5, 0.6): 2 samples, avg_conf=0.55, avg_acc=0.4, gap=0.15
        data = [
            _row(0.05, 0.2), _row(0.05, 0.2), _row(0.05, 0.2),
            _row(0.55, 0.4), _row(0.55, 0.4),
        ]
        m = compute_calibration_metrics(data)
        # ECE = (3/5)*0.15 + (2/5)*0.15 = 0.15
        assert m.expected_calibration_error == pytest.approx(0.15, abs=1e-6)


class TestMCECalculation:
    def test_mce_picks_worst_bin(self):
        # Bin [0.0, 0.1): 1 sample, gap = |1.0 - 0.05| = 0.95
        # Bin [0.9, 1.0): 2 samples, gap = |0.9 - 0.95| = 0.05
        data = [
            _row(0.05, 1.0),
            _row(0.95, 0.9), _row(0.95, 0.9),
        ]
        m = compute_calibration_metrics(data)
        # MCE = max(0.95, 0.05) = 0.95
        assert m.maximum_calibration_error == pytest.approx(0.95, abs=1e-6)
        # ECE = (1/3)*0.95 + (2/3)*0.05 = 0.35
        assert m.expected_calibration_error == pytest.approx(0.35, abs=1e-6)


class TestBoundaryConfidence:
    def test_confidence_exactly_one(self):
        data = [_row(1.0, 1.0), _row(1.0, 0.5)]
        m = compute_calibration_metrics(data)
        assert m.total_samples == 2
        assert len(m.confidence_bins) == 1
        assert m.confidence_bins[0].lower_bound == pytest.approx(0.9, abs=1e-4)
        assert m.confidence_bins[0].upper_bound == pytest.approx(1.0, abs=1e-4)

    def test_confidence_exactly_zero(self):
        data = [_row(0.0, 0.0), _row(0.0, 1.0)]
        m = compute_calibration_metrics(data)
        assert len(m.confidence_bins) == 1
        assert m.confidence_bins[0].lower_bound == pytest.approx(0.0, abs=1e-4)
        assert m.confidence_bins[0].upper_bound == pytest.approx(0.1, abs=1e-4)


class TestMissingKeys:
    def test_defaults_to_zero(self):
        data = [{"unrelated": 42}]
        m = compute_calibration_metrics(data)
        assert m.total_samples == 1
        assert m.average_confidence == 0.0
        assert m.average_accuracy == 0.0
