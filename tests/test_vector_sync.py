"""Tests for persistent Qdrant vector synchronization (Issue #13 V2.8).

``sync_graph`` must insert missing vectors, delete stale ones, leave unchanged
vectors untouched, recreate collections exactly once when the vector dimension
changes, and be idempotent — while never affecting in-memory mode.
"""

from __future__ import annotations

from src.embeddings.indexer import HierarchyIndexer
from src.embeddings.models import DEFAULT_COLLECTIONS
from src.embeddings.providers import DeterministicEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.embeddings.store import QdrantStore
from src.knowledge_graph.neo4j_driver import InMemoryGraph

DIM = 32


def _make_graph(n: int) -> InMemoryGraph:
    g = InMemoryGraph()
    g.create_node(
        "Document",
        "doc1",
        {"document_id": "doc1", "title": "THE ACT", "language": "en"},
    )
    for i in range(1, n + 1):
        g.create_node(
            "Section",
            f"s{i:04d}",
            {
                "title": f"Section {i}",
                "numbering": str(i),
                "hierarchy_level": 5,
                "text": f"provision {i} text",
            },
        )
    return g


def _service(dim: int = DIM) -> EmbeddingService:
    return EmbeddingService(provider=DeterministicEmbeddingProvider(dim=dim))


def _new_section(graph: InMemoryGraph, node_id: str) -> None:
    graph.create_node(
        "Section",
        node_id,
        {"title": f"New {node_id}", "numbering": "99", "hierarchy_level": 5, "text": "added"},
    )


def _index(graph: InMemoryGraph, store: QdrantStore, service: EmbeddingService) -> dict:
    store.ensure_collections()
    return HierarchyIndexer(graph, store, service).index_graph()


class TestSynchronization:
    def test_inserts_new_vector(self) -> None:
        graph = _make_graph(5)
        store = QdrantStore(dim=DIM, in_memory=True)
        service = _service()
        _index(graph, store, service)
        _new_section(graph, "sNEW01")
        try:
            result = HierarchyIndexer(graph, store, service).sync_graph()
            assert result["inserted"] == 1
            assert result["deleted"] == 0
            assert store.count("sections") == 6
            assert "sNEW01" in store.indexed_ids("sections")
        finally:
            store.close()

    def test_removes_stale_vector(self) -> None:
        graph = _make_graph(5)
        store = QdrantStore(dim=DIM, in_memory=True)
        service = _service()
        _index(graph, store, service)
        graph.delete_node("s0001")
        try:
            result = HierarchyIndexer(graph, store, service).sync_graph()
            assert result["deleted"] == 1
            assert result["inserted"] == 0
            assert store.count("sections") == 4
            assert "s0001" not in store.indexed_ids("sections")
        finally:
            store.close()

    def test_unchanged_vectors_preserved(self) -> None:
        graph = _make_graph(5)
        store = QdrantStore(dim=DIM, in_memory=True)
        service = _service()
        _index(graph, store, service)
        before = store.indexed_payloads("sections")
        try:
            result = HierarchyIndexer(graph, store, service).sync_graph()
            assert result["inserted"] == 0
            assert result["updated"] == 0
            assert result["deleted"] == 0
            assert result["unchanged"] == 6  # 1 doc + 5 sections
            assert store.count("sections") == 5
            assert store.indexed_payloads("sections") == before
        finally:
            store.close()

    def test_changed_text_reindexed(self) -> None:
        graph = _make_graph(5)
        store = QdrantStore(dim=DIM, in_memory=True)
        service = _service()
        _index(graph, store, service)
        graph.get_node("s0002")["text"] = "completely different wording now"
        try:
            result = HierarchyIndexer(graph, store, service).sync_graph()
            assert result["updated"] == 1
            assert result["inserted"] == 0
            assert result["deleted"] == 0
        finally:
            store.close()

    def test_second_sync_idempotent(self) -> None:
        graph = _make_graph(5)
        store = QdrantStore(dim=DIM, in_memory=True)
        service = _service()
        _index(graph, store, service)
        indexer = HierarchyIndexer(graph, store, service)
        try:
            first = indexer.sync_graph()
            second = indexer.sync_graph()
            assert first["inserted"] == 0
            assert first["deleted"] == 0
            assert second["inserted"] == 0
            assert second["updated"] == 0
            assert second["deleted"] == 0
            assert store.count("sections") == 5
        finally:
            store.close()


class TestDimensionMismatch:
    def test_recreates_once_and_resyncs(self, tmp_path) -> None:
        path = str(tmp_path / "qd")
        graph = _make_graph(5)
        store32 = QdrantStore(dim=32, in_memory=False, path=path)
        service32 = _service(32)
        _index(graph, store32, service32)
        assert store32.count("sections") == 5
        store32.close()

        store16 = QdrantStore(dim=16, in_memory=False, path=path)
        service16 = _service(16)
        indexer = HierarchyIndexer(graph, store16, service16)
        try:
            result = indexer.sync_graph(recreate_on_dimension_mismatch=True)
            assert result["recreated"] == len(DEFAULT_COLLECTIONS)
            assert result["inserted"] == 6  # 1 doc + 5 sections
            assert result["deleted"] == 0
            assert store16.count("sections") == 5

            second = indexer.sync_graph(recreate_on_dimension_mismatch=True)
            assert second["recreated"] == 0
            assert second["inserted"] == 0
            assert second["updated"] == 0
            assert second["deleted"] == 0
        finally:
            store16.close()

    def test_matching_dimension_never_recreated(self) -> None:
        graph = _make_graph(3)
        store = QdrantStore(dim=DIM, in_memory=True)
        service = _service()
        _index(graph, store, service)
        try:
            result = HierarchyIndexer(graph, store, service).sync_graph(
                recreate_on_dimension_mismatch=True
            )
            assert result["recreated"] == 0
            assert store.count("sections") == 3
        finally:
            store.close()


class TestPersistentInstances:
    def test_sync_across_reopened_persistent_store(self, tmp_path) -> None:
        path = str(tmp_path / "qd")
        graph = _make_graph(100)
        store1 = QdrantStore(dim=DIM, in_memory=False, path=path)
        service = _service()
        _index(graph, store1, service)
        assert store1.count("sections") == 100
        store1.close()

        graph.delete_node("s0100")
        store2 = QdrantStore(dim=DIM, in_memory=False, path=path)
        indexer = HierarchyIndexer(graph, store2, service)
        try:
            result = indexer.sync_graph()
            assert result["deleted"] == 1
            assert result["inserted"] == 0
            assert store2.count("sections") == 99

            rerun = indexer.sync_graph()
            assert rerun["deleted"] == 0
            assert rerun["inserted"] == 0
            assert rerun["updated"] == 0
        finally:
            store2.close()


class TestInMemoryUntouched:
    def test_in_memory_ignores_persistence_path(self, tmp_path) -> None:
        path = tmp_path / "never_created"
        store = QdrantStore(dim=DIM, in_memory=True, path=str(path))
        try:
            assert not path.exists()
            assert not store.collection_exists("sections")
        finally:
            store.close()
