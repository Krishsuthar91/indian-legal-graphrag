"""Retrieval speed benchmarking.

Measures per-query latency for embedding, dense search, and hybrid retrieval,
reporting mean / p50 / p95 over a set of queries.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from src.config.logging_config import get_logger
from src.embeddings.retriever import VectorRetriever

log = get_logger("benchmark")


@dataclass
class BenchmarkReport:
    """Latency statistics for one retrieval stage."""

    stage: str
    n: int
    times_ms: list[float] = field(default_factory=list)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0.0

    @property
    def p50_ms(self) -> float:
        return statistics.median(self.times_ms) if self.times_ms else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.times_ms:
            return 0.0
        ordered = sorted(self.times_ms)
        idx = min(len(ordered) - 1, int(0.95 * len(ordered)))
        return ordered[idx]

    @property
    def total_ms(self) -> float:
        return sum(self.times_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "n": self.n,
            "mean_ms": round(self.mean_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "total_ms": round(self.total_ms, 3),
        }


def _time_ms(fn) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000.0


def benchmark_retrieval(
    retriever: VectorRetriever,
    queries: list[str],
    top_k: int = 5,
    warmup: int = 1,
) -> list[BenchmarkReport]:
    """Benchmark embedding, dense, and hybrid retrieval over the queries."""
    embed = BenchmarkReport("embed_query", n=len(queries))
    dense = BenchmarkReport("dense_search", n=len(queries))
    hybrid = BenchmarkReport("hybrid_retrieve", n=len(queries))

    for i in range(warmup):
        retriever.hybrid_retrieve(queries[0], top_k=top_k)

    for q in queries:
        embed.times_ms.append(_time_ms(lambda: retriever.service.embed_query(q)))
        dense.times_ms.append(
            _time_ms(lambda: retriever.dense_search(q, top_k=top_k))
        )
        hybrid.times_ms.append(
            _time_ms(lambda: retriever.hybrid_retrieve(q, top_k=top_k))
        )

    reports = [embed, dense, hybrid]
    log.info(
        "benchmark.complete",
        queries=len(queries),
        top_k=top_k,
        stages=[r.to_dict() for r in reports],
    )
    return reports


def format_report(reports: list[BenchmarkReport]) -> str:
    """Human-readable table of benchmark results."""
    lines = [f"{'stage':<16}{'n':>5}{'mean_ms':>12}{'p50_ms':>12}{'p95_ms':>12}{'total_ms':>12}"]
    for report in reports:
        d = report.to_dict()
        lines.append(
            f"{d['stage']:<16}{d['n']:>5}{d['mean_ms']:>12.3f}{d['p50_ms']:>12.3f}"
            f"{d['p95_ms']:>12.3f}{d['total_ms']:>12.3f}"
        )
    return "\n".join(lines)
