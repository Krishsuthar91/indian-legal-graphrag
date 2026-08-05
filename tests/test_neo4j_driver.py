"""Tests for the in-memory graph store."""

from src.knowledge_graph.neo4j_driver import InMemoryGraph


class TestInMemoryGraphNodes:
    def test_create_and_get_node(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {"title": "Section 1", "level": 5})
        node = g.get_node("s1")
        assert node is not None
        assert node["title"] == "Section 1"
        assert node["label"] == "Section"

    def test_get_nodes_by_label(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {"title": "S1"})
        g.create_node("Section", "s2", {"title": "S2"})
        g.create_node("Chapter", "ch1", {"title": "Ch1"})
        assert len(g.get_nodes_by_label("Section")) == 2
        assert len(g.get_nodes_by_label("Chapter")) == 1

    def test_all_nodes(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {"title": "S1"})
        g.create_node("Chapter", "ch1", {"title": "Ch1"})
        nodes = g.all_nodes()
        assert len(nodes) == 2
        assert {n["node_id"] for n in nodes} == {"s1", "ch1"}

    def test_all_nodes_empty(self):
        g = InMemoryGraph()
        assert g.all_nodes() == []

    def test_find_nodes(self):
        g = InMemoryGraph()
        g.create_node("Case", "c1", {"citation": "AIR 1965 SC 123"})
        g.create_node("Case", "c2", {"citation": "2001 SCC 456"})
        results = g.find_nodes("Case", "citation", "AIR 1965 SC 123")
        assert len(results) == 1
        assert results[0]["citation"] == "AIR 1965 SC 123"

    def test_merge_node_creates_new(self):
        g = InMemoryGraph()
        nid = g.merge_node("Court", "name", "Supreme Court", {"jurisdiction": "India"})
        assert nid
        assert g.get_node(nid)["name"] == "Supreme Court"

    def test_merge_node_updates_existing(self):
        g = InMemoryGraph()
        g.merge_node("Court", "name", "Supreme Court", {"jurisdiction": "India"})
        nid2 = g.merge_node("Court", "name", "Supreme Court", {"founded": "1950"})
        node = g.get_node(nid2)
        assert node["jurisdiction"] == "India"
        assert node["founded"] == "1950"

    def test_delete_node(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.delete_node("s1")
        assert g.get_node("s1") is None

    def test_get_nonexistent_node(self):
        g = InMemoryGraph()
        assert g.get_node("nonexistent") is None


class TestInMemoryGraphEdges:
    def test_create_and_get_edge(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Chapter", "ch1", {})
        g.create_edge("s1", "ch1", "PART_OF")
        edges = g.get_edges("s1", direction="out")
        assert len(edges) == 1
        assert edges[0]["rel_type"] == "PART_OF"

    def test_get_edges_by_type(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.create_node("Case", "c1", {})
        g.create_edge("s1", "s2", "CITES")
        g.create_edge("s1", "c1", "REFERENCES")
        cites = g.get_edges("s1", rel_type="CITES")
        assert len(cites) == 1

    def test_get_edges_incoming(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Chapter", "ch1", {})
        g.create_edge("s1", "ch1", "PART_OF")
        edges = g.get_edges("ch1", direction="in")
        assert len(edges) == 1

    def test_find_existing_edge(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.create_edge("s1", "s2", "CITES")
        found = g.find_edge("s1", "s2", "CITES")
        assert found is not None

    def test_find_nonexistent_edge(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        assert g.find_edge("s1", "s1", "CITES") is None

    def test_merge_edge_creates_new(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        created = g.merge_edge("s1", "s2", "CITES")
        assert created is True
        assert g.edge_count("CITES") == 1

    def test_merge_edge_skips_existing(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.merge_edge("s1", "s2", "CITES")
        created = g.merge_edge("s1", "s2", "CITES")
        assert created is False
        assert g.edge_count("CITES") == 1

    def test_delete_edge(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.create_edge("s1", "s2", "CITES")
        deleted = g.delete_edge("s1", "s2", "CITES")
        assert deleted is True
        assert g.edge_count("CITES") == 0


class TestInMemoryGraphStats:
    def test_node_count(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Chapter", "ch1", {})
        assert g.node_count() == 2
        assert g.node_count("Section") == 1

    def test_edge_count(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.create_edge("s1", "s2", "CITES")
        g.create_edge("s2", "s1", "REFERENCES")
        assert g.edge_count() == 2
        assert g.edge_count("CITES") == 1

    def test_clear(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_edge("s1", "s1", "CITES")
        g.clear()
        assert g.node_count() == 0
        assert g.edge_count() == 0
