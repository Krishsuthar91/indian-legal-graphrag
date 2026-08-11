"""Performance metrics — latency, per-stage times, and memory usage.

Latency figures come from the QA service and retrieval summary:
- ``duration_ms``              end-to-end answer latency
- ``total_retrieval_latency_ms``  retrieval + ranking + evidence resolution
- ``ranking_latency_ms``       ranking + deduplication
- ``llm_time_ms``              duration minus retrieval time (generation)

Memory usage is measured with ``tracemalloc`` (stdlib, cross-platform) over
the benchmark run, and the process RSS via ``psutil`` when it is installed.
"""

from __future__ import annotations

import statistics
import tracemalloc
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

T = TypeVar("T")

_LATENCY_BUDGET_MS = 5000.0


def p95(values: Sequence[float]) -> float:
    """95th percentile of a sequence (0.0 when empty)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def latency_summary(times_ms: Sequence[float]) -> dict[str, float]:
    """Mean / p50 / p95 latency (ms) over a sequence of durations."""
    if not times_ms:
        return {"n": 0, "mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    return {
        "n": len(times_ms),
        "mean_ms": round(statistics.mean(times_ms), 3),
        "p50_ms": round(statistics.median(times_ms), 3),
        "p95_ms": round(p95(times_ms), 3),
    }


def process_rss_mb() -> float | None:
    """Current process RSS in MB (None when psutil is unavailable)."""
    try:
        import psutil  # type: ignore[import-not-found]

        return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return None


def measure_peak_traced_memory(fn: Callable[[], T]) -> tuple[T, int]:
    """Run ``fn`` under ``tracemalloc`` and return ``(result, peak_bytes)``."""
    tracemalloc.start()
    try:
        result = fn()
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return result, peak


def memory_usage_mb(peak_traced_bytes: int | None = None) -> dict[str, float]:
    """Memory usage summary: peak traced heap (MB) plus current RSS (if any)."""
    rss = process_rss_mb()
    summary: dict[str, float] = {}
    if peak_traced_bytes is not None:
        summary["peak_traced_mb"] = round(peak_traced_bytes / (1024 * 1024), 2)
    if rss is not None:
        summary["rss_mb"] = rss
    return summary


def performance_metrics(rows: list[Any]) -> dict[str, float]:
    """Aggregated performance metrics over raw result rows."""
    latencies = [row.latency_ms for row in rows]
    summary = latency_summary(latencies)
    return {
        "average_latency_ms": summary["mean_ms"],
        "p95_latency_ms": summary["p95_ms"],
        "average_retrieval_time_ms": round(
            statistics.mean([row.retrieval_latency_ms for row in rows]), 3
        )
        if rows
        else 0.0,
        "average_llm_time_ms": round(
            statistics.mean([row.llm_time_ms for row in rows]), 3
        )
        if rows
        else 0.0,
        "average_ranking_time_ms": round(
            statistics.mean([row.ranking_latency_ms for row in rows]), 3
        )
        if rows
        else 0.0,
        "memory_usage_mb": memory_usage_mb().get("peak_traced_mb", 0.0),
    }


def latency_score(avg_latency_ms: float, budget_ms: float = _LATENCY_BUDGET_MS) -> float:
    """Normalized latency score in [0, 1] (1.0 at zero latency, 0 at budget)."""
    if budget_ms <= 0:
        return 1.0
    return round(max(0.0, min(1.0, 1.0 - avg_latency_ms / budget_ms)), 4)
