"""Tests for graph importer and traversal APIs."""

import json
from pathlib import Path

import pytest

from src.knowledge_graph.importer import import_all, import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.knowledge_graph.stats import get_graph_stats
from src.knowledge_graph.traversal import (
    citation_chain,
    get_children,
    get_neighbors,
    get_parent,
    shortest_path,
)


@pytest.fixture()
def graph():
    return InMemoryGraph()


@pytest.fixture()
def sample_hierarchy(tmp_path: Path) -> Path:
    """Create a sample hierarchy JSON for import testing."""
    data = {
        "document_id": "test_doc_01",
        "root_id": "root",
        "nodes": [
            {
                "node_id": "root",
                "parent_id": None,
                "level": 0,
                "node_type": "document",
                "title": "Test Act",
                "text": "",
                "start_page": 1,
                "end_page": 1,
                "numbering": "",
                "children": ["n1", "n2"],
            },
            {
                "node_id": "n1",
                "parent_id": "root",
                "level": 4,
                "node_type": "chapter",
                "title": "CHAPTER I",
                "text": "",
                "start_page": 1,
                "end_page": 1,
                "numbering": "I",
                "children": ["n3"],
            },
            {
                "node_id": "n2",
                "parent_id": "root",
                "level": 4,
                "node_type": "chapter",
                "title": "CHAPTER II",
                "text": "",
                "start_page": 2,
                "end_page": 2,
                "numbering": "II",
                "children": [],
            },
            {
                "node_id": "n3",
                "parent_id": "n1",
                "level": 5,
                "node_type": "section",
                "title": "Section 1",
                "text": "Section 12 of the Act and Article 14 of the Constitution.",
                "start_page": 1,
                "end_page": 1,
                "numbering": "1",
                "children": [],
            },
        ],
        "nested_set": [],
        "warnings": [],
        "language": "en",
    }
    p = tmp_path / "test_doc_01.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


class TestImportHierarchy:
    def test_import_creates_nodes(self, graph, sample_hierarchy):
        counts = import_hierarchy_json(graph, sample_hierarchy)
        assert counts["nodes_created"] >= 4  # doc + 3 structural

    def test_import_creates_part_of_edges(self, graph, sample_hierarchy):
        import_hierarchy_json(graph, sample_hierarchy)
        edges = graph.get_edges("n1", rel_type="PART_OF")
        assert len(edges) >= 1

    def test_import_extracts_citations(self, graph, sample_hierarchy):
        import_hierarchy_json(graph, sample_hierarchy)
        # n3 references Section 12 and Article 14
        refs = graph.get_edges("n3", rel_type="REFERENCES")
        assert len(refs) >= 2

    def test_import_document_node(self, graph, sample_hierarchy):
        import_hierarchy_json(graph, sample_hierarchy)
        doc = graph.get_node("test_doc_01")
        assert doc is not None
        assert doc["title"] == "Test Act"

    def test_import_all(self, graph, tmp_path: Path):
        data = {
            "document_id": "doc_a", "root_id": "root", "language": "en",
            "nodes": [
                {
                    "node_id": "root",
                    "parent_id": None,
                    "level": 0,
                    "node_type": "document",
                    "title": "Act A",
                    "text": "",
                    "start_page": 1,
                    "end_page": 1,
                    "numbering": "",
                    "children": [],
                },
                {
                    "node_id": "s1",
                    "parent_id": "root",
                    "level": 5,
                    "node_type": "section",
                    "title": "S1",
                    "text": "",
                    "start_page": 1,
                    "end_page": 1,
                    "numbering": "1",
                    "children": [],
                },
            ],
            "nested_set": [], "warnings": [],
        }
        d = tmp_path / "hierarchy"
        d.mkdir()
        (d / "doc_a.json").write_text(json.dumps(data), encoding="utf-8")
        result = import_all(graph, d)
        assert result["files_imported"] == 1
        assert result["total_nodes"] >= 2


class TestTraversal:
    def _build_chain(self, g):
        g.create_node("Document", "doc1", {"title": "Act"})
        g.create_node("Chapter", "ch1", {"title": "Ch1"})
        g.create_node("Section", "s1", {"title": "S1"})
        g.create_node("Section", "s2", {"title": "S2"})
        g.create_edge("ch1", "doc1", "PART_OF")
        g.create_edge("s1", "ch1", "PART_OF")
        g.create_edge("s2", "ch1", "PART_OF")
        g.create_edge("s1", "s2", "CITES")

    def test_get_parent(self, graph):
        self._build_chain(graph)
        parent = get_parent(graph, "s1")
        assert parent is not None
        assert parent["node_id"] == "ch1"

    def test_get_children(self, graph):
        self._build_chain(graph)
        children = get_children(graph, "ch1")
        ids = {c["node_id"] for c in children}
        assert "s1" in ids
        assert "s2" in ids

    def test_get_neighbors(self, graph):
        self._build_chain(graph)
        neighbors = get_neighbors(graph, "s1")
        ids = {n["node_id"] for n in neighbors}
        assert "ch1" in ids
        assert "s2" in ids

    def test_citation_chain(self, graph):
        self._build_chain(graph)
        chain = citation_chain(graph, "s1")
        assert len(chain) >= 1
        cited_ids = {c["node"]["node_id"] for c in chain}
        assert "s2" in cited_ids

    def test_shortest_path(self, graph):
        self._build_chain(graph)
        path = shortest_path(graph, "s1", "doc1")
        assert path is not None
        assert "s1" in path
        assert "doc1" in path

    def test_shortest_path_same_node(self, graph):
        self._build_chain(graph)
        path = shortest_path(graph, "s1", "s1")
        assert path == ["s1"]

    def test_shortest_path_none(self, graph):
        graph.create_node("Section", "s1", {})
        graph.create_node("Section", "s2", {})
        path = shortest_path(graph, "s1", "s2")
        assert path is None


class TestStats:
    def test_graph_stats(self, graph):
        graph.create_node("Section", "s1", {})
        graph.create_node("Chapter", "ch1", {})
        graph.create_edge("s1", "ch1", "PART_OF")
        stats = get_graph_stats(graph)
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert "Section" in stats["nodes_by_label"]
