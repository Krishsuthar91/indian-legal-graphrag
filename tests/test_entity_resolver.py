"""Tests for entity resolution."""

from src.knowledge_graph.entity_resolver import (
    find_duplicate_nodes,
    merge_nodes,
    resolve_duplicates,
)
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.knowledge_graph.schema import NodeLabel


class TestFindDuplicates:
    def test_no_duplicates(self):
        g = InMemoryGraph()
        g.create_node(NodeLabel.CASE.value, "c1", {"name": "AIR 1965 SC 123"})
        g.create_node(NodeLabel.CASE.value, "c2", {"name": "2001 SCC 456"})
        groups = find_duplicate_nodes(g, NodeLabel.CASE.value, "name")
        assert len(groups) == 0

    def test_finds_duplicates(self):
        g = InMemoryGraph()
        g.create_node(NodeLabel.COURT.value, "c1", {"name": "Supreme Court"})
        g.create_node(NodeLabel.COURT.value, "c2", {"name": "supreme court"})
        groups = find_duplicate_nodes(g, NodeLabel.COURT.value, "name")
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_finds_duplicates_with_whitespace(self):
        g = InMemoryGraph()
        g.create_node(NodeLabel.COURT.value, "c1", {"name": "  Supreme Court  "})
        g.create_node(NodeLabel.COURT.value, "c2", {"name": "Supreme Court"})
        groups = find_duplicate_nodes(g, NodeLabel.COURT.value, "name")
        assert len(groups) == 1


class TestMergeNodes:
    def test_merge_repoints_edges(self):
        g = InMemoryGraph()
        g.create_node(NodeLabel.COURT.value, "c1", {"name": "SC"})
        g.create_node(NodeLabel.COURT.value, "c2", {"name": "sc"})
        g.create_node(NodeLabel.CASE.value, "case1", {})
        g.create_edge("case1", "c2", "PART_OF")

        merge_nodes(g, "c1", ["c2"])

        assert g.get_node("c1") is not None
        assert g.get_node("c2") is None
        edges = g.get_edges("case1", direction="out")
        assert any(e["to_node"] == "c1" for e in edges)

    def test_merge_preserves_keep_node(self):
        g = InMemoryGraph()
        g.create_node(NodeLabel.COURT.value, "c1", {"name": "SC", "founded": "1950"})
        g.create_node(NodeLabel.COURT.value, "c2", {"name": "sc", "extra": "data"})
        merge_nodes(g, "c1", ["c2"])
        node = g.get_node("c1")
        assert node["name"] == "SC"
        assert node["founded"] == "1950"


class TestResolveDuplicates:
    def test_resolves_all_duplicates(self):
        g = InMemoryGraph()
        g.create_node(NodeLabel.COURT.value, "c1", {"name": "Supreme Court"})
        g.create_node(NodeLabel.COURT.value, "c2", {"name": "supreme court"})
        g.create_node(NodeLabel.COURT.value, "c3", {"name": "SUPREME COURT"})
        merged = resolve_duplicates(g, NodeLabel.COURT.value, "name")
        assert merged == 2
        assert g.node_count(NodeLabel.COURT.value) == 1
