"""Tests for the markdown evaluation report generator."""

from types import SimpleNamespace

import pytest

from src.evaluation.report import (
    FAILURE_CATEGORIES,
    _failure_score,
    build_report,
    write_report,
)


def _row(
    item_id="ICA1872-001",
    question="q",
    section_acc=0.0,
    mrr=0.0,
    hall=0.0,
    grounding=1.0,
    confidence=0.9,
    latency=1.0,
):
    return {
        "item_id": item_id,
        "question": question,
        "query_type": "definition",
        "difficulty": "Easy",
        "recall_at_5": 0.0,
        "recall_at_10": 0.0,
        "precision_at_5": 0.0,
        "mrr": mrr,
        "section_accuracy": section_acc,
        "hierarchy_accuracy": 1.0,
        "answer_accuracy": 0.0,
        "grounding_accuracy": grounding,
        "citation_accuracy": 0.0,
        "faithfulness": 0.0,
        "evidence_coverage": 0.0,
        "hallucination_rate": hall,
        "latency_ms": latency,
        "confidence": confidence,
    }


def _raw_row(item_id="ICA1872-001", **kwargs):
    fields = {
        "item_id": item_id,
        "insufficient_evidence": False,
        "retrieved_nodes": ["n_0001"],
        "latency_ms": 1.0,
    }
    fields.update(kwargs)
    return SimpleNamespace(**fields)


class TestFailureScore:
    def test_failure_score(self):
        row = _row(section_acc=0.0, mrr=0.0, hall=0.5, grounding=0.5)
        assert _failure_score(row) == pytest.approx(3.0)
        clean = _row(section_acc=1.0, mrr=1.0, hall=0.0, grounding=1.0)
        assert _failure_score(clean) == 0.0


class TestBuildReport:
    def test_report_contains_all_sections(self, tmp_path):
        rows = [_row(item_id=f"ICA1872-{i:03d}", section_acc=0.2, hall=0.7) for i in range(1, 6)]
        raw_rows = [_raw_row(item_id=f"ICA1872-{i:03d}") for i in range(1, 6)]
        report = build_report(
            meta={
                "document_id": "doc1",
                "hierarchy_file": "h.json",
                "questions": 5,
                "llm_provider": "mock",
                "model": "mock",
                "embedding_provider": "deterministic",
                "seed": 42,
                "confidence_threshold": 0.45,
            },
            per_query_rows=rows,
            performance={
                "average_latency_ms": 10.0,
                "p95_latency_ms": 20.0,
                "average_retrieval_time_ms": 4.0,
                "average_llm_time_ms": 5.0,
                "average_ranking_time_ms": 1.0,
                "memory_usage_mb": 12.0,
            },
            scores={"overall": 0.4, "retrieval": 0.3, "generation": 0.4, "performance": 0.9},
            p95_latency_ms=20.0,
            raw_rows=raw_rows,
        )
        for heading in (
            "# HHGR Research Evaluation Report",
            "## Overall Score",
            "## Metric Tables",
            "### Retrieval Metrics",
            "### Generation Metrics",
            "### Performance Metrics",
            "## Error Analysis",
            "## Failure Categories",
            "## Top Failure Examples",
            "## Most Successful Queries",
            "## Recommendations",
        ):
            assert heading in report

    def test_failure_categories_counted(self, tmp_path):
        rows = [
            _row(item_id="ICA1872-001", section_acc=0.0, hall=0.9, grounding=0.5, confidence=0.2)
        ]
        raw_rows = [
            _raw_row(
                item_id="ICA1872-001",
                insufficient_evidence=True,
                retrieved_nodes=[],
                latency_ms=50.0,
            )
        ]
        report = build_report(
            meta={},
            per_query_rows=rows,
            performance={},
            scores={"overall": 0.0, "retrieval": 0.0, "generation": 0.0, "performance": 0.0},
            p95_latency_ms=10.0,
            raw_rows=raw_rows,
        )
        for name, _ in FAILURE_CATEGORIES:
            assert name in report

    def test_write_report_creates_file(self, tmp_path):
        path = write_report(tmp_path / "evaluation_report.md", "# Report")
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "# Report"
