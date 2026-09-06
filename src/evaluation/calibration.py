"""Confidence calibration metrics — measures whether confidence scores match correctness.

Computes Expected Calibration Error (ECE), Maximum Calibration Error (MCE),
and per-bin statistics by comparing each question's ``confidence`` score
against its ``answer_accuracy`` (ground-truth correctness).

This module is fully independent: it does not import report, runner,
pipeline, or any metric module.  It expects plain dicts as input so it
can be called from any integration point without coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CalibrationBin:
    """Statistics for one confidence bin."""

    lower_bound: float
    upper_bound: float
    sample_count: int
    average_confidence: float
    empirical_accuracy: float


@dataclass
class CalibrationMetrics:
    """Complete calibration report for a set of predictions."""

    expected_calibration_error: float
    maximum_calibration_error: float
    average_confidence: float
    average_accuracy: float
    total_samples: int
    confidence_bins: list[CalibrationBin] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_NUM_BINS = 10
_BIN_WIDTH = 1.0 / _NUM_BINS


def compute_calibration_metrics(
    raw_results: list[dict[str, Any]],
) -> CalibrationMetrics:
    """Compute calibration metrics from a list of result dicts.

    Each dict in *raw_results* must contain at least:

    - ``confidence``  — the model's predicted confidence score in [0, 1]
    - ``answer_accuracy`` — the ground-truth correctness score in [0, 1]

    Empty input returns zero-valued metrics with no bins.
    """
    if not raw_results:
        return CalibrationMetrics(
            expected_calibration_error=0.0,
            maximum_calibration_error=0.0,
            average_confidence=0.0,
            average_accuracy=0.0,
            total_samples=0,
        )

    total = len(raw_results)
    avg_conf = sum(float(r.get("confidence", 0.0)) for r in raw_results) / total
    avg_acc = sum(float(r.get("answer_accuracy", 0.0)) for r in raw_results) / total

    bins = _compute_bins(raw_results)
    ece = _compute_ece(bins, total)
    mce = _compute_mce(bins)

    return CalibrationMetrics(
        expected_calibration_error=round(ece, 6),
        maximum_calibration_error=round(mce, 6),
        average_confidence=round(avg_conf, 6),
        average_accuracy=round(avg_acc, 6),
        total_samples=total,
        confidence_bins=bins,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_bins(
    raw_results: list[dict[str, Any]],
) -> list[CalibrationBin]:
    """Assign samples to 10 equal-width bins and compute per-bin stats."""
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(_NUM_BINS)]

    for r in raw_results:
        conf = float(r.get("confidence", 0.0))
        acc = float(r.get("answer_accuracy", 0.0))
        idx = int(conf / _BIN_WIDTH)
        # Clamp into [0, _NUM_BINS - 1] so confidence=1.0 lands in the last bin
        if idx >= _NUM_BINS:
            idx = _NUM_BINS - 1
        buckets[idx].append((conf, acc))

    bins: list[CalibrationBin] = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        lower = round(i * _BIN_WIDTH, 4)
        upper = round((i + 1) * _BIN_WIDTH, 4)
        count = len(bucket)
        mean_conf = sum(c for c, _ in bucket) / count
        mean_acc = sum(a for _, a in bucket) / count
        bins.append(
            CalibrationBin(
                lower_bound=lower,
                upper_bound=upper,
                sample_count=count,
                average_confidence=round(mean_conf, 6),
                empirical_accuracy=round(mean_acc, 6),
            )
        )
    return bins


def _compute_ece(bins: list[CalibrationBin], total: int) -> float:
    """Expected Calibration Error: weighted mean of |accuracy − confidence|."""
    if total == 0 or not bins:
        return 0.0
    return sum(
        (b.sample_count / total) * abs(b.empirical_accuracy - b.average_confidence) for b in bins
    )


def _compute_mce(bins: list[CalibrationBin]) -> float:
    """Maximum Calibration Error: worst absolute gap across all bins."""
    if not bins:
        return 0.0
    return max(abs(b.empirical_accuracy - b.average_confidence) for b in bins)
