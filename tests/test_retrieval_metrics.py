"""Tests for the offline research metrics (Phase 3 C5)."""

import pytest

from src.llm.provenance import Confidence, ExplanationResult, RetrievalSummary
from src.retrieval.metrics import (
    average_adaptive_top_k,
    average_candidate_count,
    average_confidence,
    average_final_evidence_count,
    average_ranking_latency_ms,
    average_retrieval_latency_ms,
    duplicate_removal_rate,
    research_metrics,
)
from tests.qa_helpers import build_engine


def _result(**summary_kwargs) -> ExplanationResult:
    base = dict(
        retrieved_candidates=5,
        ranked_candidates=5,
        duplicates_removed=0,
        adaptive_top_k=None,
    )
    base.update(summary_kwargs)
    return ExplanationResult(
        query="q",
        query_language="en",
        retrieval=RetrievalSummary(**base),
        confidence=Confidence(0.5, "medium"),
    )


class TestAverageLatencies:
    def test_average_retrieval_latency(self):
        results = [
            _result(retrieval_latency_ms=4.0),
            _result(retrieval_latency_ms=6.0),
        ]
        assert average_retrieval_latency_ms(results) == pytest.approx(5.0)

    def test_average_ranking_latency(self):
        results = [
            _result(ranking_latency_ms=1.0),
            _result(ranking_latency_ms=3.0),
        ]
        assert average_ranking_latency_ms(results) == pytest.approx(2.0)

    def test_average_latencies_empty(self):
        assert average_retrieval_latency_ms([]) == 0.0
        assert average_ranking_latency_ms([]) == 0.0


class TestDuplicateRemovalRate:
    def test_zero_when_no_duplicates(self):
        results = [_result(), _result()]
        assert duplicate_removal_rate(results) == 0.0

    def test_fraction(self):
        results = [
            _result(ranked_candidates=10, duplicates_removed=4),
            _result(ranked_candidates=10, duplicates_removed=0),
        ]
        assert duplicate_removal_rate(results) == pytest.approx(0.2)

    def test_empty_and_zero_ranked(self):
        assert duplicate_removal_rate([]) == 0.0
        assert duplicate_removal_rate([_result(ranked_candidates=0)]) == 0.0


class TestCounts:
    def test_average_adaptive_top_k_ignores_fixed(self):
        results = [
            _result(adaptive_top_k=4),
            _result(adaptive_top_k=None),
            _result(adaptive_top_k=7),
        ]
        assert average_adaptive_top_k(results) == pytest.approx(5.5)

    def test_average_adaptive_top_k_all_fixed_or_empty(self):
        assert average_adaptive_top_k([_result(adaptive_top_k=None)]) == 0.0
        assert average_adaptive_top_k([]) == 0.0

    def test_average_candidate_count(self):
        results = [_result(retrieved_candidates=5), _result(retrieved_candidates=7)]
        assert average_candidate_count(results) == pytest.approx(6.0)
        assert average_candidate_count([]) == 0.0


class TestEndToEnd:
    def test_average_final_evidence_count(self):
        engine = build_engine()
        results = [engine.explain("performance of contracts", top_k=5) for _ in range(3)]
        expected = sum(len(r.evidence) for r in results) / 3
        assert average_final_evidence_count(results) == pytest.approx(expected)

    def test_average_confidence(self):
        engine = build_engine()
        results = [engine.explain("performance of contracts", top_k=5) for _ in range(3)]
        assert average_confidence(results) == pytest.approx(0.8006, abs=1e-3)

    def test_research_metrics_returns_all_keys(self):
        engine = build_engine()
        results = [engine.explain("performance of contracts", top_k=5) for _ in range(3)]
        metrics = research_metrics(results)
        assert set(metrics) == {
            "average_retrieval_latency_ms",
            "average_ranking_latency_ms",
            "duplicate_removal_rate",
            "average_adaptive_top_k",
            "average_candidate_count",
            "average_final_evidence_count",
            "average_confidence",
        }
        assert all(v >= 0 for v in metrics.values())
        assert metrics["average_confidence"] == pytest.approx(0.8006, abs=1e-3)
