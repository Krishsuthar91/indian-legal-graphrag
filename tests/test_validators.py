"""Tests for hierarchy validation."""

from src.hierarchy.models import HierarchyNode, ParsedHierarchy
from src.hierarchy.validators import validate_hierarchy


def _make_hierarchy(nodes: list[HierarchyNode], warnings=None) -> ParsedHierarchy:
    """Build a hierarchy directly from nodes, preserving their parent_id values."""
    from src.hierarchy.tree_builder import build_document_root, build_nested_set

    root = build_document_root("doc1", "Test")

    # Populate root.children from nodes that reference root as parent
    for n in nodes:
        if n.parent_id == "root":
            root.children.append(n.node_id)

    all_nodes = [root] + nodes
    ns = build_nested_set(root, all_nodes)
    return ParsedHierarchy(
        document_id="doc1",
        root_id="root",
        nodes=all_nodes,
        nested_set=ns,
        warnings=warnings or [],
    )


class TestMissingParent:
    def test_no_missing_parent(self):
        nodes = [
            HierarchyNode(node_id="s1", level=5, node_type="section", parent_id="root"),
        ]
        h = _make_hierarchy(nodes)
        warnings = validate_hierarchy(h)
        assert not any(w.warning_type == "missing_parent" for w in warnings)

    def test_missing_parent_detected(self):
        nodes = [
            HierarchyNode(node_id="s1", level=5, node_type="section", parent_id="nonexistent"),
        ]
        h = _make_hierarchy(nodes)
        warnings = validate_hierarchy(h)
        assert any(w.warning_type == "missing_parent" for w in warnings)


class TestDuplicateNumbering:
    def test_no_duplicates(self):
        nodes = [
            HierarchyNode(
                node_id="s1", level=5, node_type="section", numbering="1", parent_id="root"
            ),
            HierarchyNode(
                node_id="s2", level=5, node_type="section", numbering="2", parent_id="root"
            ),
        ]
        h = _make_hierarchy(nodes)
        warnings = validate_hierarchy(h)
        assert not any(w.warning_type == "duplicate_numbering" for w in warnings)

    def test_duplicate_detected(self):
        nodes = [
            HierarchyNode(
                node_id="s1", level=5, node_type="section", numbering="12", parent_id="root"
            ),
            HierarchyNode(
                node_id="s2", level=5, node_type="section", numbering="12", parent_id="root"
            ),
        ]
        h = _make_hierarchy(nodes)
        warnings = validate_hierarchy(h)
        assert any(w.warning_type == "duplicate_numbering" for w in warnings)


class TestBrokenNesting:
    def test_valid_nesting(self):
        nodes = [
            HierarchyNode(node_id="ch1", level=4, node_type="chapter", parent_id="root"),
            HierarchyNode(node_id="s1", level=5, node_type="section", parent_id="ch1"),
        ]
        h = _make_hierarchy(nodes)
        warnings = validate_hierarchy(h)
        assert not any(w.warning_type == "broken_nesting" for w in warnings)

    def test_broken_nesting_detected(self):
        nodes = [
            HierarchyNode(node_id="ch1", level=4, node_type="chapter", parent_id="root"),
            HierarchyNode(node_id="s1", level=4, node_type="section", parent_id="ch1"),
        ]
        h = _make_hierarchy(nodes)
        warnings = validate_hierarchy(h)
        assert any(w.warning_type == "broken_nesting" for w in warnings)
