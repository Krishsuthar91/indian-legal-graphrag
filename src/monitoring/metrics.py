"""Lightweight Prometheus metrics collector (stdlib only).

Exports request counters, latency, and process metrics in the Prometheus
text exposition format without requiring the `prometheus_client` package.
Neo4j / Qdrant expose their own /metrics endpoints that the Prometheus
scrape config collects separately.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class MetricsRegistry:
    """Thread-safe in-process metrics registry with text exposition."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._info: dict[str, str] = {}
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Instrumentation API
    # ------------------------------------------------------------------

    def inc(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._counters[(name, self._labels_tuple(labels))] += value

    def set(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._gauges[(name, self._labels_tuple(labels))] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._histograms[name][self._labels_tuple(labels)].append(value)

    def set_info(self, key: str, value: str) -> None:
        with self._lock:
            self._info[key] = value

    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    # ------------------------------------------------------------------
    # Exposition
    # ------------------------------------------------------------------

    def render(self) -> str:
        with self._lock:
            lines: list[str] = []

            # Counters
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(self._metric_line(name, "counter", value, labels))
                lines.append(self._metric_line(name, "counter", value, labels, sample=True))

            # Gauges
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(self._metric_line(name, "gauge", value, labels, sample=True))

            # Histograms (plain observation counts + sum as untyped helpers)
            for name, buckets in sorted(self._histograms.items()):
                for labels, values in sorted(buckets.items()):
                    if not values:
                        continue
                    lines.append(
                        f"{name}_count{self._format_labels(labels)} {len(values)}"
                    )
                    lines.append(
                        f"{name}_sum{self._format_labels(labels)} {sum(values):.9f}"
                    )
                    lines.append(
                        f"{name}{self._format_labels(labels)} {values[-1]:.9f}"
                    )

            lines.append(
                f"process_uptime_seconds{self._format_labels(())} {self.uptime_seconds():.2f}"
            )
            return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _labels_tuple(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    @staticmethod
    def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        inner = ",".join(f'{k}="{v}"' for k, v in labels)
        return "{" + inner + "}"

    def _metric_line(
        self,
        name: str,
        kind: str,
        value: float,
        labels: tuple[tuple[str, str], ...],
        sample: bool = False,
    ) -> str:
        if sample:
            return f"{name}{self._format_labels(labels)} {value:.9f}"
        return f"# TYPE {name} {kind}"


metrics = MetricsRegistry()
