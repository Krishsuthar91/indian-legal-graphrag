"""Tests for the retrieval benchmark."""

import pytest

from src.embeddings.benchmark import (
    BenchmarkReport,
    benchmark_retrieval,
    format_report,
)
from src.embeddings.indexer import HierarchyIndexer
from src.embeddings.providers import DeterministicEmbeddingProvider
from src.embeddings.retriever import VectorRetriever
from src.embeddings.service import EmbeddingService
from src.embeddings.store import QdrantStore
from src.knowledge_graph.neo4j_driver import InMemoryGraph


@pytest.fixture()
def retriever():
    g = InMemoryGraph()
    g.create_node("Document", "doc1", {"document_id": "doc1", "language": "en"})
    for i in range(20):
        g.create_node("Section", f"s{i}", {
            "title": f"Section {i}", "numbering": str(i), "hierarchy_level": 5,
            "text": f"provision number {i} about contracts and performance",
        })
        g.create_edge(f"s{i}", "doc1", "PART_OF")

    store = QdrantStore(dim=64, in_memory=True)
    store.ensure_collections()
    service = EmbeddingService(provider=DeterministicEmbeddingProvider(dim=64))
    HierarchyIndexer(g, store, service).index_graph()
    return VectorRetriever(g, store, service)


class TestBenchmarkReport:
    def test_empty_report(self):
        report = BenchmarkReport("x", 0)
        assert report.mean_ms == 0.0
        assert report.p50_ms == 0.0
        assert report.p95_ms == 0.0

    def test_percentiles(self):
        report = BenchmarkReport("x", 5, times_ms=[1.0, 2.0, 3.0, 4.0, 100.0])
        assert report.p50_ms == 3.0
        assert report.p95_ms == 100.0
        assert report.total_ms == 110.0

    def test_to_dict(self):
        report = BenchmarkReport("stage", 2, times_ms=[1.0, 3.0])
        data = report.to_dict()
        assert data["stage"] == "stage"
        assert data["mean_ms"] == 2.0
        assert data["p95_ms"] == 3.0


class TestBenchmarkRetrieval:
    def test_runs_and_reports_positive_times(self, retriever):
        reports = benchmark_retrieval(
            retriever, ["performance of contracts", "section 4", "agreement"], top_k=5
        )
        assert len(reports) == 3
        stages = {r.stage for r in reports}
        assert stages == {"embed_query", "dense_search", "hybrid_retrieve"}
        for report in reports:
            assert report.n == 3
            assert report.mean_ms > 0.0
            assert report.p50_ms <= report.p95_ms

    def test_format_report(self, retriever):
        reports = benchmark_retrieval(
            retriever, ["performance of contracts", "section 4"], top_k=3
        )
        text = format_report(reports)
        assert "stage" in text
        assert "embed_query" in text
        assert "hybrid_retrieve" in text
