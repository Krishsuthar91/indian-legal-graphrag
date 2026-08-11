"""Per-query metric aggregation and overall scoring."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from types import SimpleNamespace

from src.evaluation.metrics.generation import generation_metrics
from src.evaluation.metrics.performance import latency_score
from src.evaluation.metrics.retrieval import aggregate_metrics, retrieval_metrics

RETRIEVAL_METRIC_KEYS = (
    "recall_at_5",
    "recall_at_10",
    "precision_at_5",
    "mrr",
    "section_accuracy",
    "hierarchy_accuracy",
)

GENERATION_METRIC_KEYS = (
    "answer_accuracy",
    "grounding_accuracy",
    "citation_accuracy",
    "faithfulness",
    "evidence_coverage",
    "hallucination_rate",
)

# Weights used for the composite overall score (0.4 retrieval / 0.4
# generation / 0.2 performance).
RETRIEVAL_WEIGHT = 0.4
GENERATION_WEIGHT = 0.4
PERFORMANCE_WEIGHT = 0.2

# Non-metric columns carried on per-query rows.
META_COLUMNS = ("item_id", "question", "query_type", "difficulty")


def _evidence_from_row(result) -> list[SimpleNamespace]:
    """Rebuild lightweight evidence entries from a ``RawResult`` row.

    ``retrieval_metrics`` reads ``result.evidence`` and ``generation_metrics``
    reads ``result.explanation.evidence``, so the adapter exposes both while
    keeping the metric functions usable directly with production
    ``AnswerResult`` objects.
    """
    evidence: list[SimpleNamespace] = []
    for ev in result.retrieved_evidence:
        evidence.append(
            SimpleNamespace(
                node_id=ev["node_id"],
                title=ev.get("title", ""),
                text=ev.get("text", ""),
                numbering=ev.get("numbering", ""),
                path=list(ev.get("path", [])),
            )
        )
    return evidence


def _metric_view(result) -> SimpleNamespace:
    """Expose a result through the metric-interface (``.answer`` / ``.evidence``).

    ``AnswerResult`` objects are passed through (their ``.evidence`` re-exposes
    ``explanation.evidence``); ``RawResult`` rows are rebuilt into lightweight
    evidence entries. This keeps ``retrieval_metrics`` (reads ``result.evidence``)
    and ``generation_metrics`` (reads ``result.answer`` and
    ``result.explanation.evidence``) working for both input kinds.
    """
    if hasattr(result, "answer") and hasattr(result, "explanation"):
        return SimpleNamespace(
            answer=result.answer,
            evidence=list(result.explanation.evidence),
            explanation=result.explanation,
        )
    evidence = _evidence_from_row(result)
    return SimpleNamespace(
        answer=result.answer,
        evidence=evidence,
        explanation=SimpleNamespace(evidence=evidence),
    )


def compute_per_query_metrics(graph, items: Sequence, results: Sequence) -> list[dict[str, float]]:
    """Retrieval + generation metrics for each (item, result) pair.

    ``results`` may be ``AnswerResult`` objects or ``RawResult`` rows from the
    evaluation runner; both are normalized to the metric interface.
    """
    rows: list[dict[str, float]] = []
    for item, result in zip(items, results):
        view = _metric_view(result)
        rows.append(
            {
                "item_id": item.id,
                "question": item.question,
                "query_type": item.query_type,
                "difficulty": item.difficulty,
                **retrieval_metrics(graph, item, view),
                **generation_metrics(item, view),
            }
        )
    return rows


def _mean(values: Sequence[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def group_by(rows: list[dict[str, float]], key: str) -> dict[str, dict[str, float]]:
    """Aggregate metric means grouped by a row column (e.g. query_type)."""
    groups: dict[str, list[dict[str, float]]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return {name: _mean_metric_rows(group) for name, group in groups.items()}


def _mean_metric_rows(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    keys = [key for key in rows[0] if key not in META_COLUMNS]
    return {key: _mean([row[key] for row in rows]) for key in keys}


def retrieval_score(aggregate: dict[str, float]) -> float:
    """Mean of the retrieval metrics (all higher-is-better)."""
    return _mean([aggregate[key] for key in RETRIEVAL_METRIC_KEYS])


def generation_score(aggregate: dict[str, float]) -> float:
    """Mean of the generation metrics with hallucination inverted."""
    positives = (
        "answer_accuracy",
        "grounding_accuracy",
        "citation_accuracy",
        "faithfulness",
        "evidence_coverage",
    )
    components = [aggregate[key] for key in positives]
    components.append(round(1.0 - aggregate["hallucination_rate"], 4))
    return _mean(components)


def overall_score(
    aggregate: dict[str, float],
    avg_latency_ms: float,
    *,
    latency_budget_ms: float = 5000.0,
) -> dict[str, float]:
    """Composite score = 0.4*retrieval + 0.4*generation + 0.2*performance."""
    retrieval = retrieval_score(aggregate)
    generation = generation_score(aggregate)
    performance = latency_score(avg_latency_ms, latency_budget_ms)
    total = round(
        RETRIEVAL_WEIGHT * retrieval
        + GENERATION_WEIGHT * generation
        + PERFORMANCE_WEIGHT * performance,
        4,
    )
    return {
        "overall": total,
        "retrieval": round(retrieval, 4),
        "generation": round(generation, 4),
        "performance": performance,
    }


def summarize_metrics(
    rows: list[dict[str, float]],
) -> dict[str, float]:
    """Aggregate per-query metric rows into a single summary vector."""
    meta_keys = ("item_id", "question", "query_type", "difficulty")
    metric_rows = [
        {key: row[key] for key in row if key not in meta_keys}
        for row in rows
    ]
    return aggregate_metrics(metric_rows)
