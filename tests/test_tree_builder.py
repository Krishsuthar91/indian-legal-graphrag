"""Tests for tree builder (adjacency + nested set index)."""

from src.hierarchy.models import HierarchyNode
from src.hierarchy.tree_builder import (
    assign_parents,
    build_document_root,
    build_hierarchy,
)


class TestDocumentRoot:
    def test_root_created(self):
        root = build_document_root("doc001", "Test Document")
        assert root.node_id == "root"
        assert root.level == 0
        assert root.node_type == "document"
        assert root.title == "Test Document"

    def test_root_default_title(self):
        root = build_document_root("doc001")
        assert root.title == "Document"


class TestAssignParents:
    def test_single_level_nodes(self):
        nodes = [
            HierarchyNode(node_id="n1", level=5, node_type="section", title="S1"),
            HierarchyNode(node_id="n2", level=5, node_type="section", title="S2"),
            HierarchyNode(node_id="n3", level=5, node_type="section", title="S3"),
        ]
        assigned = assign_parents(nodes)
        for n in assigned:
            assert n.parent_id == "root"

    def test_nested_levels(self):
        nodes = [
            HierarchyNode(node_id="ch1", level=4, node_type="chapter", title="Ch1"),
            HierarchyNode(node_id="s1", level=5, node_type="section", title="S1"),
            HierarchyNode(node_id="s2", level=5, node_type="section", title="S2"),
            HierarchyNode(node_id="ch2", level=4, node_type="chapter", title="Ch2"),
            HierarchyNode(node_id="s3", level=5, node_type="section", title="S3"),
        ]
        assigned = assign_parents(nodes)
        ch1 = next(n for n in assigned if n.node_id == "ch1")
        ch2 = next(n for n in assigned if n.node_id == "ch2")
        s1 = next(n for n in assigned if n.node_id == "s1")
        s2 = next(n for n in assigned if n.node_id == "s2")
        s3 = next(n for n in assigned if n.node_id == "s3")

        assert ch1.parent_id == "root"
        assert ch2.parent_id == "root"
        assert s1.parent_id == "ch1"
        assert s2.parent_id == "ch1"
        assert s3.parent_id == "ch2"
        assert "s1" in ch1.children
        assert "s2" in ch1.children
        assert "s3" in ch2.children

    def test_deep_nesting(self):
        nodes = [
            HierarchyNode(node_id="ch1", level=4, node_type="chapter"),
            HierarchyNode(node_id="s1", level=5, node_type="section"),
            HierarchyNode(node_id="cl1", level=7, node_type="clause"),
            HierarchyNode(node_id="sc1", level=8, node_type="sub_clause"),
        ]
        assigned = assign_parents(nodes)
        assert assigned[0].parent_id == "root"
        assert assigned[1].parent_id == "ch1"
        assert assigned[2].parent_id == "s1"
        assert assigned[3].parent_id == "cl1"


class TestBuildHierarchy:
    def test_full_hierarchy(self):
        nodes = [
            HierarchyNode(node_id="ch1", level=4, node_type="chapter", title="Preliminary"),
            HierarchyNode(node_id="s1", level=5, node_type="section", title="Short title"),
            HierarchyNode(node_id="s2", level=5, node_type="section", title="Definitions"),
            HierarchyNode(node_id="cl1", level=7, node_type="clause", title="(a)"),
        ]
        h = build_hierarchy("doc1", "Test Act", nodes)
        assert h.document_id == "doc1"
        assert h.root_id == "root"
        assert len(h.nodes) == 5  # root + 4
        assert len(h.nested_set) == 5

    def test_nested_set_ordering(self):
        nodes = [
            HierarchyNode(node_id="ch1", level=4, node_type="chapter"),
            HierarchyNode(node_id="s1", level=5, node_type="section"),
            HierarchyNode(node_id="s2", level=5, node_type="section"),
        ]
        h = build_hierarchy("doc1", "Test", nodes)
        ns_map = {e.node_id: e for e in h.nested_set}
        # Parent's left < child's left, child's right < parent's right
        assert ns_map["root"].left < ns_map["ch1"].left
        assert ns_map["ch1"].left < ns_map["s1"].left
        assert ns_map["s1"].right < ns_map["s2"].right
        assert ns_map["s2"].right < ns_map["ch1"].right
