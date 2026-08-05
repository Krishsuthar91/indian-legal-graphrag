"""Tests for explainability metrics (eval/metrics/explainability.py)."""

import pytest

from eval.dataset import GoldCitation
from eval.metrics.explainability import (
    citation_accuracy,
    counter_authority_detection_accuracy,
    evidence_coverage,
    explainability_metrics,
    graph_path_accuracy,
    hierarchy_correctness,
    provenance_completeness,
)
from src.llm.provenance import CounterAuthority, Evidence, ExplanationResult


def _evidence(node_id="s4", label="Section", numbering="4", path=("doc", "ch", "s4")):
    return Evidence(
        node_id=node_id,
        title="Performance of contracts",
        text="When contracts must be performed",
        label=label,
        numbering=numbering,
        collection="sections",
        language="en",
        level=3,
        dense_score=0.8,
        graph_score=0.7,
        hierarchy_score=1.0,
        final_score=0.85,
        sources=["dense", "graph"],
        path=list(path),
        snippet="When contracts must be performed",
    )


def _counter(marker="repealed"):
    return CounterAuthority(
        node_id="s1",
        title="Old Act",
        reason="Superseded by the new Act",
        marker=marker,
        evidence_text="This section is repealed.",
    )


def _result(evidence, citations=(), counter=(), paths=()):
    return ExplanationResult(
        query="performance",
        query_language="en",
        evidence=evidence,
        citations=list(citations),
        counter_authorities=list(counter),
        hierarchy_paths=list(paths),
    )


class TestCitationAccuracy:
    def test_perfect_match(self):
        result = _result([_evidence()])
        gold = [GoldCitation(citation_text="Section 4", node_id="s4")]
        assert citation_accuracy(result, gold) == pytest.approx(1.0)

    def test_missing_citation_scores_zero(self):
        result = _result([_evidence()])
        gold = [GoldCitation(citation_text="Section 99", node_id="s99")]
        assert citation_accuracy(result, gold) == pytest.approx(0.0)

    def test_empty_gold_returns_zero(self):
        assert citation_accuracy(_result([_evidence()]), []) == 0.0

    def test_partial_match(self):
        result = _result([_evidence()])
        gold = [
            GoldCitation(citation_text="Section 4"),
            GoldCitation(citation_text="Section 99"),
        ]
        assert citation_accuracy(result, gold) == pytest.approx(0.5)


class TestProvenanceCompleteness:
    def test_full_evidence_is_mostly_complete(self):
        gold = [GoldCitation(citation_text="Section 4", node_id="s4")]
        score = provenance_completeness(_result([_evidence()]), gold)
        assert score > 0.8

    def test_empty_evidence_returns_zero(self):
        assert provenance_completeness(_result([]), []) == 0.0


class TestEvidenceCoverage:
    def test_overlapping_tokens_covered(self):
        result = _result([_evidence()])
        assert evidence_coverage(result, "contracts performed") == pytest.approx(1.0)

    def test_unrelated_answer_zero(self):
        result = _result([_evidence()])
        assert evidence_coverage(result, "quantum computing entropy") == pytest.approx(0.0)


class TestCounterAuthority:
    def test_no_expected_no_detected_is_perfect(self):
        result = _result([_evidence()])
        stats = counter_authority_detection_accuracy(result, expected_markers=None)
        assert stats["f1"] == pytest.approx(1.0)

    def test_expected_but_not_detected_recall_zero(self):
        result = _result([_evidence()])
        stats = counter_authority_detection_accuracy(result, expected_markers=["overruled"])
        assert stats["recall"] == pytest.approx(0.0)

    def test_detected_matches_expected(self):
        result = _result([_evidence()], counter=[_counter("repealed")])
        stats = counter_authority_detection_accuracy(result, expected_markers=["repealed"])
        assert stats["f1"] == pytest.approx(1.0)

    def test_false_positive_penalized(self):
        result = _result([_evidence()], counter=[_counter("repealed")])
        stats = counter_authority_detection_accuracy(result, expected_markers=["overruled"])
        assert stats["precision"] == pytest.approx(0.0)


class TestGraphConsistency:
    def test_hierarchy_correctness_valid_path(self, eval_corpus):
        result = corpus_result_for_first_item(eval_corpus)
        assert hierarchy_correctness(eval_corpus.graph, result) == pytest.approx(1.0)

    def test_graph_path_accuracy_valid_entries(self, eval_corpus):
        result = corpus_result_for_first_item(eval_corpus)
        assert graph_path_accuracy(eval_corpus.graph, result) == pytest.approx(1.0)


class TestFullVector:
    def test_metrics_shape(self, eval_corpus):
        result = corpus_result_for_first_item(eval_corpus)
        gold = [
            GoldCitation(citation_text=c.citation_text, node_id=c.node_id)
            for c in eval_corpus_dummy_gold()
        ]
        metrics = explainability_metrics(eval_corpus.graph, result, gold)
        expected_keys = {
            "citation_accuracy",
            "hierarchy_correctness",
            "graph_path_accuracy",
            "provenance_completeness",
            "evidence_coverage",
            "counter_authority_precision",
            "counter_authority_recall",
            "counter_authority_f1",
        }
        assert set(metrics) == expected_keys
        assert all(0.0 <= value <= 1.0 for value in metrics.values())

    def test_explainability_metrics_high_quality(self, eval_corpus, eval_items):
        gold = eval_items[0].citations
        result = eval_corpus.engine.explain(eval_items[0].query, top_k=5)
        metrics = explainability_metrics(eval_corpus.graph, result, gold)
        assert metrics["citation_accuracy"] >= 0.9
        assert metrics["hierarchy_correctness"] == pytest.approx(1.0)


def corpus_result_for_first_item(corpus):
    from eval.dataset import EvalDataset
    from tests.conftest import EVAL_GOLD_DIR

    dataset = EvalDataset.load(EVAL_GOLD_DIR / "contract_act_gold.json")
    item = dataset.grounded_items()[0]
    return corpus.engine.explain(item.query, top_k=5)


def eval_corpus_dummy_gold():
    return [
        GoldCitation(citation_text="Section 4", node_id="n_0001"),
        GoldCitation(citation_text="Section 5", node_id="n_0002"),
    ]
