"""Offline research metrics for adaptive retrieval evaluation.

These helpers compute aggregate diagnostics across many ``ExplanationResult``
records. They are for offline evaluation only — the QA runtime does not call
them, and the public API surface is untouched.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.llm.provenance import ExplanationResult


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def average_retrieval_latency_ms(results: Sequence[ExplanationResult]) -> float:
    """Mean ``retrieval_latency_ms`` (intent + dense + graph + hierarchy + fusion)."""
    return round(_mean([r.retrieval.retrieval_latency_ms for r in results]), 3)


def average_ranking_latency_ms(results: Sequence[ExplanationResult]) -> float:
    """Mean ``ranking_latency_ms`` (ranking + deduplication)."""
    return round(_mean([r.retrieval.ranking_latency_ms for r in results]), 3)


def duplicate_removal_rate(results: Sequence[ExplanationResult]) -> float:
    """Fraction of ranked candidates removed by evidence deduplication, in [0, 1]."""
    removed = sum(r.retrieval.duplicates_removed for r in results)
    ranked = sum(r.retrieval.ranked_candidates for r in results)
    if ranked <= 0:
        return 0.0
    return round(removed / ranked, 4)


def average_adaptive_top_k(results: Sequence[ExplanationResult]) -> float:
    """Mean adaptive evidence budget; ignores fixed-strategy runs (``None``)."""
    values = [r.retrieval.adaptive_top_k for r in results]
    return round(_mean([float(k) for k in values if k is not None]), 3)


def average_candidate_count(results: Sequence[ExplanationResult]) -> float:
    """Mean retrieved-candidate count (before ranking)."""
    return round(_mean([float(r.retrieval.retrieved_candidates) for r in results]), 3)


def average_final_evidence_count(results: Sequence[ExplanationResult]) -> float:
    """Mean final evidence count surfaced in the explanation."""
    return round(_mean([float(len(r.evidence)) for r in results]), 3)


def average_confidence(results: Sequence[ExplanationResult]) -> float:
    """Mean aggregate confidence score."""
    return round(_mean([r.confidence.score for r in results]), 4)


def research_metrics(results: Sequence[ExplanationResult]) -> dict[str, float]:
    """All research metrics for a batch of explanations in one dict."""
    return {
        "average_retrieval_latency_ms": average_retrieval_latency_ms(results),
        "average_ranking_latency_ms": average_ranking_latency_ms(results),
        "duplicate_removal_rate": duplicate_removal_rate(results),
        "average_adaptive_top_k": average_adaptive_top_k(results),
        "average_candidate_count": average_candidate_count(results),
        "average_final_evidence_count": average_final_evidence_count(results),
        "average_confidence": average_confidence(results),
    }
