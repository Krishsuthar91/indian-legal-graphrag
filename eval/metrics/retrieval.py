"""Module 10, Part 2 — Retrieval ranking metrics.

Implements Recall@K, Precision@K, Hit Rate@K, MRR, MAP, NDCG@K over a ranked
list of retrieved node ids versus the gold relevant set. Latency / throughput
statistics are provided by :func:`latency_stats` over per-query durations.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from typing import Any


def recall_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    """Fraction of gold-relevant nodes present in the top-k results."""
    if not relevant:
        return 0.0
    return len(relevant.intersection(retrieved[:k])) / len(relevant)


def precision_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    """Fraction of top-k results that are gold-relevant."""
    if k == 0:
        return 0.0
    return len(relevant.intersection(retrieved[:k])) / k


def hit_rate_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    """1.0 when at least one gold-relevant node appears in the top-k results."""
    return 1.0 if relevant.intersection(retrieved[:k]) else 0.0


def reciprocal_rank(relevant: set[str], retrieved: Sequence[str]) -> float:
    """Inverse of the rank of the first gold-relevant result (0 when absent)."""
    for i, node_id in enumerate(retrieved, 1):
        if node_id in relevant:
            return 1.0 / i
    return 0.0


def average_precision(relevant: set[str], retrieved: Sequence[str]) -> float:
    """Mean precision at each gold-relevant rank (0 when none retrieved)."""
    hits = 0
    sum_precisions = 0.0
    for i, node_id in enumerate(retrieved, 1):
        if node_id in relevant:
            hits += 1
            sum_precisions += hits / i
    return sum_precisions / len(relevant) if relevant else 0.0


def _dcg_at_k(relevances: Sequence[float], k: int) -> float:
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        rel = relevances[i]
        if rel > 0:
            dcg += (2 ** rel - 1) / math.log2(i + 2)
    return dcg


def ndcg_at_k(
    relevant: set[str],
    retrieved: Sequence[str],
    k: int,
    grades: dict[str, float] | None = None,
) -> float:
    """NDCG@K with binary relevance by default (optional graded relevance)."""
    grades = grades or {}
    relevances = [grades.get(node_id, 1.0) if node_id in relevant else 0.0 for node_id in retrieved]
    dcg = _dcg_at_k(relevances, k)
    ideal = sorted((grades.get(n, 1.0) if n in relevant else 0.0 for n in retrieved), reverse=True)
    idcg = _dcg_at_k(list(ideal), k)
    return dcg / idcg if idcg > 0 else 0.0


def retrieval_metrics(
    relevant: set[str],
    retrieved: Iterable[str],
    k: int = 5,
) -> dict[str, float]:
    """Full retrieval metric vector for one query."""
    ranked = list(retrieved)
    metrics = {
        "recall_at_k": recall_at_k(relevant, ranked, k),
        "precision_at_k": precision_at_k(relevant, ranked, k),
        "hit_rate_at_k": hit_rate_at_k(relevant, ranked, k),
        "mrr": reciprocal_rank(relevant, ranked),
        "map": average_precision(relevant, ranked),
        "ndcg_at_k": ndcg_at_k(relevant, ranked, k),
        "k": float(k),
    }
    return {key: round(value, 4) for key, value in metrics.items()}


def aggregate_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    """Mean of per-query metric dicts, preserving metric keys."""
    if not rows:
        return {}
    keys = [key for key in rows[0] if key != "k"]
    return {key: round(statistics.mean(r[key] for r in rows), 4) for key in keys}


def latency_stats(times_ms: Sequence[float]) -> dict[str, float]:
    """Mean / p50 / p95 latency (ms) plus derived throughput (queries/sec)."""
    if not times_ms:
        return {"n": 0.0, "mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "throughput_qps": 0.0}
    ordered = sorted(times_ms)
    mean_ms = statistics.mean(ordered)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
    throughput = (1000.0 / mean_ms) if mean_ms > 0 else 0.0
    return {
        "n": float(len(ordered)),
        "mean_ms": round(mean_ms, 3),
        "p50_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(p95, 3),
        "throughput_qps": round(throughput, 2),
    }


def summarize(
    rows: list[dict[str, float]],
    latency: Sequence[float],
    system: str,
    items: int,
) -> dict[str, Any]:
    """Combine accuracy aggregates and latency statistics for one system."""
    accuracy = aggregate_metrics(rows)
    timing = latency_stats(latency)
    return {
        "system": system,
        "items": items,
        **accuracy,
        **timing,
    }
