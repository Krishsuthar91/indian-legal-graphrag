"""Tests for provenance dataclasses and the provenance store (Module 7)."""

from dataclasses import asdict

from src.llm.provenance import (
    AnswerResult,
    Evidence,
    ExplanationResult,
    ProvenanceStore,
)


def _answer() -> AnswerResult:
    explanation = ExplanationResult(
        query="performance of contracts",
        query_language="en",
        evidence=[
            Evidence(
                node_id="s4",
                title="Performance of contracts",
                text="text",
                label="Section",
                numbering="4",
                collection="sections",
                language="en",
                level=5,
                dense_score=0.8,
                graph_score=0.7,
                hierarchy_score=1.0,
                final_score=0.85,
                sources=["dense"],
                path=["doc1", "ch2", "s4"],
            )
        ],
    )
    return AnswerResult(
        provenance_id="abc123",
        query="performance of contracts",
        answer="The answer.",
        model="mock-llm",
        explanation=explanation,
        duration_ms=12.3,
    )


class TestSerialization:
    def test_answer_result_to_dict(self):
        data = asdict(_answer())
        assert data["provenance_id"] == "abc123"
        assert data["explanation"]["evidence"][0]["node_id"] == "s4"
        assert data["duration_ms"] == 12.3


class TestProvenanceStore:
    def test_save_and_get_roundtrip(self):
        store = ProvenanceStore()
        store.save(_answer())
        record = store.get("abc123")
        assert record is not None
        assert record["query"] == "performance of contracts"
        assert record["answer"] == "The answer."
        assert record["explanation"]["evidence"][0]["node_id"] == "s4"

    def test_missing_returns_none(self):
        store = ProvenanceStore()
        assert store.get("nope") is None

    def test_list_ids(self):
        store = ProvenanceStore()
        for i in range(3):
            a = _answer()
            a.provenance_id = f"id{i}"
            store.save(a)
        assert store.list_ids() == ["id0", "id1", "id2"]

    def test_persists_to_disk(self, tmp_path):
        store = ProvenanceStore(directory=tmp_path)
        store.save(_answer())
        assert (tmp_path / "abc123.json").exists()
        # A fresh store instance reads from disk
        store2 = ProvenanceStore(directory=tmp_path)
        record = store2.get("abc123")
        assert record is not None
        assert record["answer"] == "The answer."
