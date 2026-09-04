"""Reliability diagram — publication-quality calibration plot.

Generates a PNG reliability diagram from a ``CalibrationMetrics`` object,
showing how well the model's confidence scores align with empirical accuracy.

The diagram plots average confidence (x-axis) against empirical accuracy
(y-axis) for each non-empty confidence bin, with an ideal y = x reference
line and sample counts annotated near each point.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

from src.evaluation.calibration import CalibrationMetrics


def generate_reliability_diagram(
    calibration_metrics: CalibrationMetrics,
    output_path: str | Path,
) -> Path:
    """Render a reliability diagram and save it as a PNG.

    Parameters
    ----------
    calibration_metrics:
        The calibration report produced by ``compute_calibration_metrics``.
    output_path:
        Destination file path (overwritten if it exists).  Parent
        directories are created automatically.

    Returns
    -------
    Path
        The resolved path to the saved PNG file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bins = calibration_metrics.confidence_bins

    fig, ax = plt.subplots(figsize=(6, 6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # Ideal calibration line (y = x)
    ax.plot(
        [0.0, 1.0],
        [0.0, 1.0],
        linestyle="--",
        color="gray",
        linewidth=1.0,
        label="Ideal calibration",
    )

    if bins:
        avg_confs = [b.average_confidence for b in bins]
        emp_accs = [b.empirical_accuracy for b in bins]
        sample_counts = [b.sample_count for b in bins]

        ax.plot(
            avg_confs,
            emp_accs,
            marker="o",
            color="C0",
            linewidth=2,
            markersize=8,
            label="Model calibration",
        )

        for x, y, n in zip(avg_confs, emp_accs, sample_counts):
            ax.annotate(
                f"n={n}",
                (x, y),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
                color="black",
            )

    ax.set_xlabel("Average Confidence", fontsize=12)
    ax.set_ylabel("Empirical Accuracy", fontsize=12)
    ax.set_title("Reliability Diagram", fontsize=14)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=300, bbox_inches="tight")
    plt.close(fig)

    return output_path
