"""Tests for the reliability diagram plot (Task 8 - Step 5)."""

from __future__ import annotations

from src.evaluation.calibration import CalibrationBin, CalibrationMetrics
from src.evaluation.plots import generate_reliability_diagram


def _make_calibration(
    ece: float = 0.08,
    bins: list[CalibrationBin] | None = None,
) -> CalibrationMetrics:
    if bins is None:
        bins = [
            CalibrationBin(0.0, 0.1, 5, 0.05, 0.10),
            CalibrationBin(0.1, 0.2, 10, 0.15, 0.20),
            CalibrationBin(0.2, 0.3, 8, 0.25, 0.30),
            CalibrationBin(0.8, 0.9, 12, 0.85, 0.82),
        ]
    return CalibrationMetrics(
        expected_calibration_error=ece,
        maximum_calibration_error=0.12,
        average_confidence=0.45,
        average_accuracy=0.48,
        total_samples=35,
        confidence_bins=bins,
    )


class TestReliabilityDiagram:
    def test_png_file_created(self, tmp_path):
        cal = _make_calibration()
        out = generate_reliability_diagram(cal, tmp_path / "diagram.png")
        assert out.exists()
        assert out.suffix == ".png"
        assert out.stat().st_size > 0

    def test_empty_calibration_metrics(self, tmp_path):
        cal = CalibrationMetrics(
            expected_calibration_error=0.0,
            maximum_calibration_error=0.0,
            average_confidence=0.0,
            average_accuracy=0.0,
            total_samples=0,
        )
        out = generate_reliability_diagram(cal, tmp_path / "empty.png")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_nonempty_produces_valid_image(self, tmp_path):
        cal = _make_calibration()
        out = generate_reliability_diagram(cal, tmp_path / "valid.png")
        header = out.read_bytes()[:8]
        # PNG magic bytes
        assert header[:4] == b"\x89PNG"

    def test_returns_expected_path(self, tmp_path):
        cal = _make_calibration()
        expected = tmp_path / "subdir" / "diagram.png"
        out = generate_reliability_diagram(cal, expected)
        assert out == expected

    def test_creates_parent_directories(self, tmp_path):
        cal = _make_calibration()
        deep_path = tmp_path / "a" / "b" / "c" / "diagram.png"
        out = generate_reliability_diagram(cal, deep_path)
        assert out.exists()

    def test_custom_bins(self, tmp_path):
        bins = [
            CalibrationBin(0.0, 0.1, 3, 0.05, 0.08),
            CalibrationBin(0.9, 1.0, 7, 0.95, 0.93),
        ]
        cal = _make_calibration(bins=bins)
        out = generate_reliability_diagram(cal, tmp_path / "custom.png")
        assert out.exists()
        assert out.stat().st_size > 0
