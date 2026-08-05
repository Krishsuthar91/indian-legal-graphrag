"""Tests for hierarchical context expansion."""

import pytest

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.retrieval.context import (
    get_ancestor_chain,
    get_descendant_ids,
    get_related_nodes,
    propagate_hierarchy,
)


def _build_doc_graph() -> InMemoryGraph:
    g = InMemoryGraph()
    g.create_node("Document", "doc", {"title": "Act"})
    g.create_node("Chapter", "ch1", {"title": "Ch1"})
    g.create_node("Chapter", "ch2", {"title": "Ch2"})
    g.create_node("Section", "s1", {"title": "S1", "numbering": "1"})
    g.create_node("Section", "s2", {"title": "S2", "numbering": "2"})
    g.create_node("Clause", "c1", {"title": "C1"})
    g.create_edge("ch1", "doc", "PART_OF")
    g.create_edge("ch2", "doc", "PART_OF")
    g.create_edge("s1", "ch1", "PART_OF")
    g.create_edge("s2", "ch2", "PART_OF")
    g.create_edge("c1", "s2", "PART_OF")
    g.create_edge("s1", "s2", "CITES")
    return g


class TestAncestorChain:
    def test_returns_chain_to_root(self):
        g = _build_doc_graph()
        chain = get_ancestor_chain(g, "s1")
        ids = [n["node_id"] for n in chain]
        assert ids == ["ch1", "doc"]

    def test_deep_node_chain(self):
        g = _build_doc_graph()
        ids = [n["node_id"] for n in get_ancestor_chain(g, "c1")]
        assert ids == ["s2", "ch2", "doc"]

    def test_root_has_empty_chain(self):
        g = _build_doc_graph()
        assert get_ancestor_chain(g, "doc") == []

    def test_missing_node(self):
        g = _build_doc_graph()
        assert get_ancestor_chain(g, "nope") == []


class TestDescendants:
    def test_all_descendants(self):
        g = _build_doc_graph()
        ids = get_descendant_ids(g, "doc")
        assert ids == {"ch1", "ch2", "s1", "s2", "c1"}

    def test_nested_descendants(self):
        g = _build_doc_graph()
        ids = get_descendant_ids(g, "ch2")
        assert ids == {"s2", "c1"}

    def test_respects_max_depth(self):
        g = _build_doc_graph()
        ids = get_descendant_ids(g, "doc", max_depth=1)
        assert ids == {"ch1", "ch2"}

    def test_leaf_has_no_descendants(self):
        g = _build_doc_graph()
        assert get_descendant_ids(g, "c1") == set()


class TestRelatedNodes:
    def test_returns_citation_neighbors(self):
        g = _build_doc_graph()
        related = get_related_nodes(g, "s1", rel_types=["CITES"])
        assert any(n["node_id"] == "s2" for n in related)

    def test_returns_hierarchy_neighbors(self):
        g = _build_doc_graph()
        related = get_related_nodes(g, "s1")
        ids = {n["node_id"] for n in related}
        assert "ch1" in ids
        assert "s2" in ids


class TestPropagateHierarchy:
    def test_seed_is_1(self):
        g = _build_doc_graph()
        evidence = propagate_hierarchy(g, ["s1"])
        assert evidence["s1"] == 1.0

    def test_ancestors_attenuated(self):
        g = _build_doc_graph()
        evidence = propagate_hierarchy(g, ["s1"])
        assert evidence["ch1"] == pytest.approx(0.6)
        assert evidence["doc"] == pytest.approx(0.36)

    def test_descendants_attenuated(self):
        g = _build_doc_graph()
        evidence = propagate_hierarchy(g, ["s2"])
        assert evidence["c1"] == pytest.approx(0.4)

    def test_multiple_seeds_accumulate(self):
        g = _build_doc_graph()
        evidence = propagate_hierarchy(g, ["s1", "s2"])
        assert evidence["ch1"] == pytest.approx(0.6)
        assert evidence["ch2"] == pytest.approx(0.6)
        assert evidence["doc"] == pytest.approx(0.72)

    def test_strength_capped_at_one(self):
        g = _build_doc_graph()
        evidence = propagate_hierarchy(g, ["s1", "ch1"])
        assert evidence["ch1"] == 1.0
