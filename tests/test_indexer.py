"""Tests for hierarchy indexing (full + incremental)."""

import json
from pathlib import Path

import pytest

from src.embeddings.indexer import HierarchyIndexer, node_text, text_hash
from src.embeddings.models import DEFAULT_COLLECTIONS
from src.embeddings.providers import DeterministicEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.embeddings.store import QdrantStore
from src.knowledge_graph.neo4j_driver import InMemoryGraph


@pytest.fixture()
def graph():
    g = InMemoryGraph()
    g.create_node("Document", "doc1", {
        "document_id": "doc1", "title": "THE INDIAN CONTRACT ACT, 1892", "language": "en",
    })
    g.create_node("Chapter", "ch1", {
        "title": "CHAPTER I", "text": "Preliminary", "hierarchy_level": 4,
    })
    g.create_node("Chapter", "ch2", {
        "title": "CHAPTER II", "text": "Of Contracts", "hierarchy_level": 4,
    })
    g.create_node("Section", "s1", {
        "title": "Short title", "numbering": "1", "hierarchy_level": 5,
        "text": "This Act may be called the Indian Contract Act.",
    })
    g.create_node("Section", "s2", {
        "title": "Definitions", "numbering": "2", "hierarchy_level": 5,
        "text": "contract means an agreement enforceable by law.",
    })
    g.create_node("Case", "case1", {"name": "AIR 1965 SC 123", "hierarchy_level": 0})
    g.create_edge("ch1", "doc1", "PART_OF")
    g.create_edge("ch2", "doc1", "PART_OF")
    g.create_edge("s1", "ch1", "PART_OF")
    g.create_edge("s2", "ch1", "PART_OF")
    return g


@pytest.fixture()
def store():
    s = QdrantStore(dim=32, in_memory=True)
    s.ensure_collections()
    yield s
    s.close()


@pytest.fixture()
def service():
    return EmbeddingService(provider=DeterministicEmbeddingProvider(dim=32))


def _indexer(graph, store, service):
    return HierarchyIndexer(graph, store, service)


class TestIndexGraph:
    def test_indexes_hierarchy_nodes(self, graph, store, service):
        _indexer(graph, store, service).index_graph()
        assert store.count("documents") == 1
        assert store.count("chapters") == 2
        assert store.count("sections") == 2
        assert store.count("clauses") == 0

    def test_skips_non_hierarchy_nodes(self, graph, store, service):
        _indexer(graph, store, service).index_graph()
        assert "case1" not in store.indexed_ids("sections")

    def test_payload_language(self, graph, store, service):
        _indexer(graph, store, service).index_graph()
        payloads = store.indexed_payloads("sections")
        assert payloads["s1"]["language"] == "en"

    def test_payload_level_and_node_id(self, graph, store, service):
        _indexer(graph, store, service).index_graph()
        payloads = store.indexed_payloads("sections")
        assert payloads["s1"]["node_id"] == "s1"
        assert payloads["s1"]["level"] == 5
        assert payloads["s1"]["doc_id"] == "doc1"

    def test_selective_indexing(self, graph, store, service):
        _indexer(graph, store, service).index_graph(node_ids=["s1"])
        assert store.count("sections") == 1
        assert store.count("chapters") == 0

    def test_returns_totals(self, graph, store, service):
        result = _indexer(graph, store, service).index_graph()
        assert result["doc_id"] == "doc1"
        assert result["collections"]["sections"] == 2


class TestIndexHierarchyFile:
    def test_indexes_all_nodes_from_file(self, graph, store, service, tmp_path: Path):
        data = {
            "document_id": "docA",
            "root_id": "root",
            "language": "hi",
            "nodes": [
                {"node_id": "root", "parent_id": None, "level": 0, "node_type": "document",
                 "title": "अनुबंध अधिनियम", "text": "", "start_page": 1,
                 "end_page": 1, "numbering": "", "children": ["n1"]},
                {"node_id": "n1", "parent_id": "root", "level": 4, "node_type": "chapter",
                 "title": "CHAPTER I", "text": "प्रारंभिक", "start_page": 1,
                 "end_page": 1, "numbering": "I", "children": []},
            ],
            "nested_set": [],
            "warnings": [],
        }
        path = tmp_path / "hier.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = _indexer(graph, store, service).index_hierarchy_file(path)
        assert result["doc_id"] == "docA"
        assert store.count("documents") == 1
        assert store.count("chapters") == 1
        payload = store.indexed_payloads("chapters")["n1"]
        assert payload["language"] == "hi"
        assert payload["level"] == 4


class TestIncremental:
    def test_second_full_index_skips_all(self, graph, store, service):
        indexer = _indexer(graph, store, service)
        indexer.index_graph()
        result = indexer.index_incremental()
        assert result["indexed"] == 0
        assert result["skipped"] == 5  # 1 doc + 2 chapters + 2 sections

    def test_new_node_indexed(self, graph, store, service):
        indexer = _indexer(graph, store, service)
        indexer.index_graph()
        graph.create_node("Section", "s3", {
            "title": "New", "numbering": "3", "hierarchy_level": 5,
            "text": "freshly added provision",
        })
        graph.create_edge("s3", "ch1", "PART_OF")
        result = indexer.index_incremental()
        assert result["indexed"] == 1
        assert "s3" in store.indexed_ids("sections")

    def test_changed_text_reindexed(self, graph, store, service):
        indexer = _indexer(graph, store, service)
        indexer.index_graph()
        graph.get_node("s1")["text"] = "completely different wording now"
        result = indexer.index_incremental()
        assert result["indexed"] == 1
        assert result["skipped"] == 4

    def test_unchanged_text_skipped(self, graph, store, service):
        indexer = _indexer(graph, store, service)
        indexer.index_graph()
        graph.get_node("s1")["title"] = "Short title"
        result = indexer.index_incremental()
        assert result["indexed"] == 0

    def test_sync_deletes_stale(self, graph, store, service):
        indexer = _indexer(graph, store, service)
        indexer.index_graph()
        # Simulate a node removed from the graph but still indexed
        indexer.store.upsert(
            "sections", "ghost", [0.1] * 32, {"node_id": "ghost", "text_hash": "x"}
        )
        result = indexer.sync_graph()
        assert result["deleted"] == 1
        assert "ghost" not in store.indexed_ids("sections")


class TestHelpers:
    def test_node_text_joins_title_and_text(self):
        node = {"title": "Short title", "text": "the body"}
        assert node_text(node) == "Short title the body"

    def test_text_hash_stable(self):
        node = {"title": "a", "text": "b"}
        assert text_hash(node) == text_hash(node)

    def test_text_hash_changes_with_text(self):
        assert text_hash({"title": "a", "text": "b"}) != text_hash({"title": "a", "text": "c"})

    def test_default_collections_available(self):
        assert DEFAULT_COLLECTIONS == ["documents", "chapters", "sections", "clauses"]
