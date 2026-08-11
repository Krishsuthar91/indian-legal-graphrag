"""Tests for retrieval, generation, and performance metrics."""

from types import SimpleNamespace

import pytest

from src.evaluation.metrics.aggregate import (
    GENERATION_METRIC_KEYS,
    RETRIEVAL_METRIC_KEYS,
    compute_per_query_metrics,
    generation_score,
    overall_score,
    retrieval_score,
    summarize_metrics,
)
from src.evaluation.metrics.generation import (
    answer_accuracy,
    citation_accuracy,
    evidence_coverage,
    faithfulness,
    generation_metrics,
    grounding_accuracy,
    hallucination_rate,
    token_f1,
)
from src.evaluation.metrics.performance import (
    latency_score,
    latency_summary,
    measure_peak_traced_memory,
    memory_usage_mb,
    p95,
    performance_metrics,
)
from src.evaluation.metrics.retrieval import (
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
    relevant_node_ids,
    retrieval_metrics,
    section_accuracy,
)
from src.llm.service import INSUFFICIENT_EVIDENCE_ANSWER

EVAL_DOCUMENT_ID = "0940d367554383c5"


def _fake_evidence(
    numbering="65",
    title="Obligation of person who has received advantage",
    text="when a person receives advantage under a void agreement",
):
    return SimpleNamespace(
        node_id=f"n-{numbering}",
        numbering=numbering,
        title=title,
        text=text,
        path=["root", f"n-{numbering}"],
    )


def _fake_result(answer, evidence):
    return SimpleNamespace(answer=answer, explanation=SimpleNamespace(evidence=evidence))


def _fake_item(expected_sections):
    return SimpleNamespace(
        id="ICA1872-T1",
        question="q",
        query_type="definition",
        difficulty="Easy",
        expected_section=", ".join(expected_sections),
        expected_sections=expected_sections,
        expected_keywords="",
        expected_answer="A person receives an advantage under a void agreement.",
    )


class TestRetrievalMetricFunctions:
    def test_recall_precision_mrr(self):
        relevant = {"a", "b"}
        retrieved = ["x", "a"]
        assert recall_at_k(relevant, retrieved, 5) == pytest.approx(0.5)
        assert precision_at_k(relevant, retrieved, 2) == pytest.approx(0.5)
        assert mean_reciprocal_rank(relevant, retrieved) == pytest.approx(0.5)
        assert mean_reciprocal_rank(relevant, ["x", "y"]) == 0.0
        assert mean_reciprocal_rank(set(), retrieved) == 0.0

    def test_section_accuracy(self):
        assert section_accuracy(["65", "2(a)"], {"65", "2"}) == 1.0
        assert section_accuracy(["124", "126"], {"124"}) == 0.5


@pytest.fixture(scope="module")
def service_and_graph():
    from src.evaluation.corpus import build_evaluation_service

    return build_evaluation_service(document_id=EVAL_DOCUMENT_ID)


class TestRetrievalMetricsOnCorpus:
    def test_relevant_node_ids_maps_sections(self, service_and_graph):
        _, graph = service_and_graph
        relevant = relevant_node_ids(graph, ["1"])
        assert "n_0002" in relevant  # the 11-node corpus has a section 1 node
        assert relevant_node_ids(graph, ["999"]) == set()

    def test_retrieval_metrics_keys_and_range(self, service_and_graph):
        service, graph = service_and_graph
        result = service.engine.explain("what is chapter one", top_k=5)
        item = _fake_item(["1"])
        metrics = retrieval_metrics(graph, item, result)
        assert set(metrics) == {
            "recall_at_5",
            "recall_at_10",
            "precision_at_5",
            "mrr",
            "section_accuracy",
            "hierarchy_accuracy",
        }
        assert all(0.0 <= value <= 1.0 for value in metrics.values())


class TestGenerationMetricFunctions:
    def test_token_f1(self):
        assert token_f1("a b c", "a b c") == pytest.approx(1.0)
        assert token_f1("a b", "a b c") == pytest.approx(4 / 5)
        assert token_f1("x y", "a b") == 0.0

    def test_answer_accuracy(self):
        assert answer_accuracy("consideration is defined", "consideration is defined") > 0.9
        assert answer_accuracy("", "consideration is defined") == 0.0

    def test_grounding_valid_citations(self):
        evidence = [_fake_evidence("65"), _fake_evidence("66")]
        result = _fake_result("The answer is in source [1].", evidence)
        assert grounding_accuracy(result.answer, result) == 1.0

    def test_grounding_invalid_citation(self):
        result = _fake_result("Claim from [3].", [_fake_evidence("65"), _fake_evidence("66")])
        assert grounding_accuracy(result.answer, result) == 0.0

    def test_grounding_guard_answer(self):
        result = _fake_result(INSUFFICIENT_EVIDENCE_ANSWER, [])
        assert grounding_accuracy(result.answer, result) == 1.0
        assert hallucination_rate(result.answer, result) == 0.0
        assert citation_accuracy(_fake_item(["65"]), result) == 1.0

    def test_citation_accuracy_uses_cited_sources(self):
        item = _fake_item(["65"])
        result = _fake_result("See [1].", [_fake_evidence("65")])
        assert citation_accuracy(item, result) == 1.0
        result2 = _fake_result("See [1].", [_fake_evidence("66")])
        assert citation_accuracy(item, result2) == 0.0
        result3 = _fake_result("No citations inline.", [_fake_evidence("65")])
        assert citation_accuracy(item, result3) == 0.0

    def test_faithfulness_and_coverage(self):
        ev = _fake_evidence(
            "65", "Obligation of person", "receives advantage under a void agreement"
        )
        result = _fake_result("receives advantage under a void agreement", [ev])
        assert faithfulness(result.answer, result) >= 0.9
        coverage = evidence_coverage("receives advantage under a void agreement", result)
        assert coverage >= 0.9
        empty = _fake_result("unknown topic words zzzz", [ev])
        assert faithfulness(empty.answer, empty) < 0.5

    def test_generation_metrics_keys(self):
        item = _fake_item(["65"])
        result = _fake_result("The answer is in source [1].", [_fake_evidence("65")])
        metrics = generation_metrics(item, result)
        assert set(metrics) == set(GENERATION_METRIC_KEYS)
        assert all(0.0 <= value <= 1.0 for value in metrics.values())


class TestPerformanceMetrics:
    def test_p95(self):
        assert p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == pytest.approx(10)
        assert p95([]) == 0.0

    def test_latency_summary(self):
        summary = latency_summary([1.0, 2.0, 3.0, 4.0])
        assert summary["n"] == 4
        assert summary["mean_ms"] == pytest.approx(2.5)
        assert summary["p50_ms"] == pytest.approx(2.5)
        assert summary["p95_ms"] > 0

    def test_latency_score(self):
        assert latency_score(0.0) == 1.0
        assert latency_score(5000.0) == 0.0
        assert latency_score(2500.0) == pytest.approx(0.5)
        assert latency_score(6000.0) == 0.0

    def test_measure_peak_traced_memory(self):
        value, peak = measure_peak_traced_memory(lambda: 1 + 1)
        assert value == 2
        assert peak >= 0
        summary = memory_usage_mb(peak)
        assert summary["peak_traced_mb"] >= 0

    def test_performance_metrics_rows(self):
        row = SimpleNamespace(
            latency_ms=10.0,
            retrieval_latency_ms=4.0,
            llm_time_ms=5.0,
            ranking_latency_ms=1.0,
        )
        perf = performance_metrics([row, SimpleNamespace(**{**row.__dict__, "latency_ms": 20.0})])
        assert perf["average_latency_ms"] == pytest.approx(15.0)
        assert perf["p95_latency_ms"] > 0
        assert perf["average_retrieval_time_ms"] == pytest.approx(4.0)
        assert perf["average_ranking_time_ms"] == pytest.approx(1.0)
        assert perf["memory_usage_mb"] >= 0


class TestAggregates:
    def test_per_query_metrics_on_corpus(self):
        from src.evaluation.corpus import build_evaluation_service

        service, graph = build_evaluation_service(document_id=EVAL_DOCUMENT_ID)
        item = _fake_item(["1"])
        result = service.answer(item.question)
        rows = compute_per_query_metrics(graph, [item], [result])
        assert len(rows) == 1
        row = rows[0]
        assert set(RETRIEVAL_METRIC_KEYS) <= set(row)
        assert set(GENERATION_METRIC_KEYS) <= set(row)

    def test_scores_and_summary(self):
        aggregate = {
            "recall_at_5": 0.5,
            "recall_at_10": 0.6,
            "precision_at_5": 0.2,
            "mrr": 0.4,
            "section_accuracy": 0.7,
            "hierarchy_accuracy": 0.9,
            "answer_accuracy": 0.3,
            "grounding_accuracy": 0.9,
            "citation_accuracy": 0.8,
            "faithfulness": 0.7,
            "evidence_coverage": 0.6,
            "hallucination_rate": 0.3,
        }
        assert 0.0 <= retrieval_score(aggregate) <= 1.0
        assert 0.0 <= generation_score(aggregate) <= 1.0
        score = overall_score(aggregate, avg_latency_ms=100.0)
        assert set(score) == {"overall", "retrieval", "generation", "performance"}
        assert 0.0 <= score["overall"] <= 1.0

        rows = [
            {
                "item_id": "A",
                "question": "q",
                "query_type": "definition",
                "difficulty": "Easy",
                **aggregate,
            },
            {
                "item_id": "B",
                "question": "q",
                "query_type": "definition",
                "difficulty": "Hard",
                **{key: 0.0 for key in aggregate},
            },
        ]
        summary = summarize_metrics(rows)
        assert summary["recall_at_5"] == pytest.approx(0.25)
        assert summary["hallucination_rate"] == pytest.approx(0.15)
