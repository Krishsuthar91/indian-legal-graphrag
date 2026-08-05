"""Tests for the offline RAGAS-style generation metrics (eval/metrics/ragas.py)."""

import pytest

from eval.dataset import GoldCitation
from eval.metrics.ragas import (
    answer_correctness,
    answer_relevancy,
    compute_ragas_metrics,
    context_precision,
    context_recall,
    faithfulness,
    ragas_available,
    token_f1,
)
from eval.metrics.semantic import EmbeddingCache
from src.llm.provenance import Evidence, ExplanationResult


def _evidence(node_id="s4", numbering="4", label="Section"):
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
        sources=["dense"],
        path=["doc", "ch", "s4"],
        snippet="When contracts must be performed",
    )


class TestTokenF1:
    def test_identical_texts(self):
        assert token_f1("contract performance", "contract performance") == pytest.approx(1.0)

    def test_no_overlap(self):
        assert token_f1("contract performance", "quantum physics") == pytest.approx(0.0)

    def test_partial_overlap(self):
        assert 0.0 < token_f1("contract performance rules", "contract") < 1.0

    def test_empty_candidate(self):
        assert token_f1("contract", "") == 0.0


class TestFaithfulness:
    def test_answer_supported_by_evidence(self):
        result = ExplanationResult(
            query="q", query_language="en", evidence=[_evidence()]
        )
        assert faithfulness("When contracts must be performed.", result) == pytest.approx(1.0)

    def test_unsupported_answer(self):
        result = ExplanationResult(
            query="q", query_language="en", evidence=[_evidence()]
        )
        assert faithfulness("Quantum computing is fun.", result) == pytest.approx(0.0)


class TestContextRecall:
    def test_anchor_recovered(self):
        result = ExplanationResult(
            query="q", query_language="en", evidence=[_evidence()]
        )
        gold = [GoldCitation(citation_text="Section 4 of the Act", node_id="s4")]
        assert context_recall(gold, result) == pytest.approx(1.0)

    def test_missing_anchor(self):
        result = ExplanationResult(
            query="q", query_language="en", evidence=[_evidence()]
        )
        gold = [GoldCitation(citation_text="Section 99 of the Act", node_id="s99")]
        assert context_recall(gold, result) == pytest.approx(0.0)


class TestSemanticMetrics:
    def test_answer_relevancy_between_zero_and_one(self):
        cache = EmbeddingCache()
        score = answer_relevancy("performance of contracts", "contracts must be performed", cache)
        assert 0.0 <= score <= 1.0

    def test_answer_relevancy_empty_answer(self):
        cache = EmbeddingCache()
        assert answer_relevancy("q", "", cache) == 0.0

    def test_context_precision_in_range(self):
        cache = EmbeddingCache()
        result = ExplanationResult(query="q", query_language="en", evidence=[_evidence()])
        score = context_precision("performance of contracts", result, cache)
        assert 0.0 <= score <= 1.0

    def test_answer_correctness_in_range(self):
        cache = EmbeddingCache()
        score = answer_correctness(
            "contracts must be performed", "contracts must be performed", cache
        )
        assert 0.0 <= score <= 1.0


class TestComputeRagas:
    def test_full_vector(self):
        cache = EmbeddingCache()
        result = ExplanationResult(query="q", query_language="en", evidence=[_evidence()])
        metrics = compute_ragas_metrics(
            query="performance of contracts",
            answer="When contracts must be performed.",
            reference_answer="contracts must be performed",
            result=result,
            gold_citations=[GoldCitation(citation_text="Section 4")],
            cache=cache,
        )
        data = metrics.to_dict()
        assert set(data) == {
            "faithfulness",
            "answer_relevancy",
            "context_recall",
            "context_precision",
            "answer_correctness",
        }
        assert data["context_recall"] == pytest.approx(1.0)

    def test_empty_evidence_zeroes_context_metrics(self):
        cache = EmbeddingCache()
        result = ExplanationResult(query="q", query_language="en", evidence=[])
        metrics = compute_ragas_metrics(
            query="q",
            answer="",
            reference_answer="ref",
            result=result,
            gold_citations=[],
            cache=cache,
        )
        assert metrics.context_recall == 0.0
        assert metrics.context_precision == 0.0

    def test_ragas_optional(self):
        assert ragas_available() in (True, False)
