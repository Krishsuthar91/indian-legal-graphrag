"""Tests for the retrieval failure analyzer (Task 7)."""

from __future__ import annotations

import json

import pytest

from src.evaluation.analysis import (
    RetrievalFailureAnalysis,
    _analyze_retrieval_failure,
    build_failure_analyses,
    summarize_failure_types,
    top_recommendations,
)


def _ev(numbering: str, title: str = "", score: float = 0.5) -> dict:
    """Helper to build a minimal evidence dict."""
    return {
        "node_id": f"n_{numbering}",
        "title": title or f"Section {numbering}",
        "text": "lorem ipsum",
        "label": "section",
        "numbering": numbering,
        "final_score": score,
        "dense_score": score,
        "graph_score": 0.0,
        "hierarchy_score": 0.0,
        "sources": [],
        "path": [],
        "snippet": "",
    }


class TestMissingSection:
    """1. Expected section 72 not retrieved → missing_section."""

    def test_missing_section(self):
        evidence = [_ev("68", score=0.6), _ev("23", score=0.5), _ev("477", score=0.4)]
        result = _analyze_retrieval_failure(
            query="What does Section 72 provide?",
            expected_sections=["72"],
            retrieved_evidence=evidence,
        )
        assert result.failure_type == "missing_section"
        assert "72" in result.missing_sections
        assert result.retrieved_sections  # should have keys extracted
        assert result.query == "What does Section 72 provide?"
        assert "Section 72" not in result.retrieved_sections
        assert result.failure_reason
        assert result.recommendation


class TestWrongSection:
    """2. Retrieved sections don't match any expected → missing_section (all expected missing)."""

    def test_wrong_section(self):
        evidence = [_ev("68", score=0.8), _ev("23", score=0.7)]
        result = _analyze_retrieval_failure(
            query="What is Section 10?",
            expected_sections=["10"],
            retrieved_evidence=evidence,
        )
        # When expected section is entirely absent, classification is
        # missing_section (the expected section was not retrieved).
        assert result.failure_type == "missing_section"
        assert result.missing_sections == ["10"]
        assert result.expected_sections == ["10"]


class TestPartialMatch:
    """3. Some expected sections found, some missing → partial_match."""

    def test_partial_match(self):
        evidence = [_ev("72", score=0.9), _ev("68", score=0.5)]
        result = _analyze_retrieval_failure(
            query="Sections 72 and 80?",
            expected_sections=["72", "80"],
            retrieved_evidence=evidence,
        )
        assert result.failure_type == "partial_match"
        assert "80" in result.missing_sections
        assert "72" not in result.missing_sections


class TestNoEvidence:
    """4. No evidence retrieved → no_evidence."""

    def test_no_evidence(self):
        result = _analyze_retrieval_failure(
            query="What is Section 99?",
            expected_sections=["99"],
            retrieved_evidence=[],
        )
        assert result.failure_type == "no_evidence"
        assert result.retrieved_sections == []
        assert result.missing_sections == ["99"]
        assert "no evidence" in result.failure_reason.lower()


class TestRankingError:
    """5. Expected section is in retrieved but ranked below top_k → ranking_error."""

    def test_ranking_error(self):
        evidence = [
            _ev("68", score=0.9),
            _ev("23", score=0.8),
            _ev("477", score=0.7),
            _ev("10", score=0.15),
        ]
        result = _analyze_retrieval_failure(
            query="What does Section 10 provide?",
            expected_sections=["10"],
            retrieved_evidence=evidence,
            ranking_top_k=3,
        )
        assert result.failure_type == "ranking_error"
        assert "10" not in result.missing_sections  # it was found


class TestSerialization:
    """6. RetrievalFailureAnalysis round-trips through JSON."""

    def test_to_dict(self):
        analysis = RetrievalFailureAnalysis(
            query="test query",
            expected_sections=["10", "20"],
            retrieved_sections=["30"],
            missing_sections=["10", "20"],
            extra_sections=["30"],
            failure_type="wrong_section",
            failure_reason="Wrong sections retrieved.",
            recommendation="Fix retrieval.",
        )
        d = analysis.to_dict()
        assert d["query"] == "test query"
        assert d["expected_sections"] == ["10", "20"]
        assert d["failure_type"] == "wrong_section"

        # JSON round-trip
        dumped = json.dumps(d)
        loaded = json.loads(dumped)
        assert loaded["query"] == "test query"
        assert loaded["missing_sections"] == ["10", "20"]

    def test_build_failure_analyses_returns_none_when_accurate(self):
        """build_failure_analyses returns None when section_accuracy is 1.0."""
        assert build_failure_analyses(
            query="q",
            expected_sections=["72"],
            retrieved_evidence=[_ev("72")],
            section_accuracy=1.0,
        ) is None

    def test_build_failure_analyses_returns_analysis_when_incomplete(self):
        result = build_failure_analyses(
            query="q",
            expected_sections=["72"],
            retrieved_evidence=[_ev("68")],
            section_accuracy=0.0,
        )
        assert result is not None
        assert result.failure_type != ""

    def test_summarize_failure_types(self):
        analyses = [
            RetrievalFailureAnalysis(
                failure_type="missing_section", query="q1", recommendation="rec1",
            ),
            RetrievalFailureAnalysis(
                failure_type="missing_section", query="q2", recommendation="rec1",
            ),
            RetrievalFailureAnalysis(
                failure_type="no_evidence", query="q3", recommendation="rec2",
            ),
        ]
        summary = summarize_failure_types(analyses)
        assert summary["missing_section"]["count"] == 2
        assert summary["missing_section"]["percentage"] == pytest.approx(66.7, abs=0.1)
        assert summary["missing_section"]["examples"] == ["q1", "q2"]
        assert summary["no_evidence"]["count"] == 1

    def test_top_recommendations(self):
        analyses = [
            RetrievalFailureAnalysis(recommendation="rec1"),
            RetrievalFailureAnalysis(recommendation="rec1"),
            RetrievalFailureAnalysis(recommendation="rec1"),
            RetrievalFailureAnalysis(recommendation="rec2"),
        ]
        recs = top_recommendations(analyses, limit=2)
        assert recs[0]["recommendation"] == "rec1"
        assert recs[0]["count"] == 3
        assert recs[1]["recommendation"] == "rec2"
        assert recs[1]["count"] == 1


class TestRegression:
    """7. Regression: Section 72 query with wrong evidence → correct classification."""

    def test_section72_regression(self):
        """The exact scenario from the spec: Section 72 expected, 68/23/477 retrieved."""
        evidence = [
            _ev("68", "Section 68", score=0.75),
            _ev("23", "Section 23", score=0.65),
            _ev("477", "Section 477", score=0.55),
        ]
        result = _analyze_retrieval_failure(
            query="What does Section 72 provide?",
            expected_sections=["72"],
            retrieved_evidence=evidence,
        )
        assert result.failure_type == "missing_section"
        assert "72" in result.missing_sections
        assert "72" not in result.retrieved_sections
        assert len(result.extra_sections) > 0
        assert result.failure_reason
        assert result.recommendation

    def test_full_pipeline_integration(self):
        """Verify runner attaches analysis to RawResult for failed retrievals."""
        from src.evaluation.corpus import build_evaluation_service
        from src.evaluation.dataset import load_benchmark_csv
        from src.evaluation.runner import run_questions

        document_id = "0940d367554383c5"
        service, _ = build_evaluation_service(document_id=document_id)
        items = load_benchmark_csv()[:2]
        rows = run_questions(service, items)

        for row in rows:
            assert hasattr(row, "retrieval_failure_analysis")
            if row.retrieval_failure_analysis is not None:
                a = row.retrieval_failure_analysis
                assert a.failure_type in (
                    "missing_section", "wrong_section", "partial_match",
                    "low_similarity", "no_evidence", "ranking_error",
                    "graph_error", "chunking_error",
                )
                assert a.query
                assert a.failure_reason
                assert a.recommendation
