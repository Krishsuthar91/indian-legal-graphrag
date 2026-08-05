"""Tests for retrieval ranking and latency metrics (eval/metrics/retrieval.py)."""

import pytest

from eval.metrics.retrieval import (
    aggregate_metrics,
    average_precision,
    hit_rate_at_k,
    latency_stats,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    retrieval_metrics,
    summarize,
)


class TestRankingMetrics:
    def test_recall_at_k(self):
        assert recall_at_k({"a", "b"}, ["a", "c", "b"], 3) == pytest.approx(1.0)
        assert recall_at_k({"a", "b"}, ["a", "c"], 2) == pytest.approx(0.5)
        assert recall_at_k({"a"}, [], 5) == pytest.approx(0.0)
        assert recall_at_k(set(), ["a"], 1) == pytest.approx(0.0)

    def test_precision_at_k(self):
        assert precision_at_k({"a"}, ["a", "b", "c"], 3) == pytest.approx(1 / 3)
        assert precision_at_k({"a"}, ["a", "b", "c"], 1) == pytest.approx(1.0)
        assert precision_at_k({"a"}, ["x"], 5) == pytest.approx(0.0)
        assert precision_at_k({"a"}, ["a"], 0) == pytest.approx(0.0)

    def test_hit_rate_at_k(self):
        assert hit_rate_at_k({"a"}, ["x", "a"], 2) == 1.0
        assert hit_rate_at_k({"a"}, ["x", "y"], 2) == 0.0

    def test_reciprocal_rank(self):
        assert reciprocal_rank({"a"}, ["x", "y", "a"]) == pytest.approx(1 / 3)
        assert reciprocal_rank({"a"}, ["a"]) == pytest.approx(1.0)
        assert reciprocal_rank({"a"}, ["x"]) == pytest.approx(0.0)

    def test_average_precision(self):
        assert average_precision({"a", "b"}, ["a", "b"]) == pytest.approx(1.0)
        assert average_precision({"a", "b"}, ["a", "x", "b"]) == pytest.approx(
            (1.0 + (2 / 3)) / 2
        )
        assert average_precision({"a"}, ["x"]) == pytest.approx(0.0)

    def test_ndcg_perfect_ranking_is_one(self):
        assert ndcg_at_k({"a", "b"}, ["a", "b", "c"], 5) == pytest.approx(1.0)
        assert ndcg_at_k({"a"}, ["a"], 5) == pytest.approx(1.0)

    def test_ndcg_graded_relevance(self):
        grades = {"a": 2.0, "b": 1.0}
        assert ndcg_at_k({"a", "b"}, ["a", "b"], 5, grades=grades) == pytest.approx(1.0)

    def test_ndcg_no_relevant(self):
        assert ndcg_at_k({"a"}, ["x", "y"], 5) == pytest.approx(0.0)

    def test_retrieval_metrics_vector(self):
        metrics = retrieval_metrics({"a"}, ["a", "b"], k=2)
        assert metrics["recall_at_k"] == pytest.approx(1.0)
        assert metrics["precision_at_k"] == pytest.approx(0.5)
        assert metrics["hit_rate_at_k"] == pytest.approx(1.0)
        assert metrics["mrr"] == pytest.approx(1.0)
        assert metrics["map"] == pytest.approx(1.0)
        assert metrics["k"] == 2


class TestAggregation:
    def test_aggregate_metrics_mean(self):
        rows = [
            {"recall_at_k": 1.0, "precision_at_k": 0.5, "k": 5.0},
            {"recall_at_k": 0.0, "precision_at_k": 0.5, "k": 5.0},
        ]
        agg = aggregate_metrics(rows)
        assert agg["recall_at_k"] == pytest.approx(0.5)
        assert agg["precision_at_k"] == pytest.approx(0.5)
        assert "k" not in agg

    def test_aggregate_metrics_empty(self):
        assert aggregate_metrics([]) == {}

    def test_latency_stats(self):
        stats = latency_stats([10.0, 20.0, 30.0, 40.0])
        assert stats["n"] == 4
        assert stats["mean_ms"] == pytest.approx(25.0)
        assert stats["p50_ms"] == pytest.approx(25.0)
        assert stats["throughput_qps"] == pytest.approx(40.0)

    def test_latency_stats_empty(self):
        stats = latency_stats([])
        assert stats["n"] == 0
        assert stats["mean_ms"] == 0.0

    def test_summarize_combines(self):
        rows = [retrieval_metrics({"a"}, ["a", "b"], k=2)]
        summary = summarize(rows, [5.0], system="hhgr", items=1)
        assert summary["system"] == "hhgr"
        assert summary["items"] == 1
        assert summary["mrr"] == pytest.approx(1.0)
        assert summary["mean_ms"] == pytest.approx(5.0)
