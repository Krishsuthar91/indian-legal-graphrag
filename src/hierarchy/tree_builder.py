"""Build adjacency tree and Nested Set Index from parsed nodes."""

from __future__ import annotations

import uuid
from collections import defaultdict

from src.hierarchy.models import HierarchyNode, NestedSetEntry, ParsedHierarchy, HierarchyWarning


def _make_id() -> str:
    return uuid.uuid4().hex[:12]


def build_document_root(document_id: str, title: str = "") -> HierarchyNode:
    """Create the root Document node."""
    return HierarchyNode(
        node_id="root",
        parent_id=None,
        level=0,
        node_type="document",
        title=title or "Document",
        text="",
    )


def assign_parents(nodes: list[HierarchyNode]) -> list[HierarchyNode]:
    """Assign parent_id and children lists based on level nesting.

    Uses a stack to track the current ancestor at each level.
    A node becomes the child of the nearest ancestor with a lower level.
    """
    stack: list[HierarchyNode] = []  # stack of open ancestors
    result: list[HierarchyNode] = []

    for node in nodes:
        # Pop ancestors that are at the same or deeper level
        while stack and stack[-1].level >= node.level:
            stack.pop()

        if stack:
            node.parent_id = stack[-1].node_id
            stack[-1].children.append(node.node_id)
        else:
            node.parent_id = "root"

        stack.append(node)
        result.append(node)

    return result


def build_nested_set(root: HierarchyNode, all_nodes: list[HierarchyNode]) -> list[NestedSetEntry]:
    """Compute Nested Set Index using DFS traversal.

    Each node gets (left, right, depth) where:
    - left = pre-order visit number
    - right = post-order visit number
    - depth = level of the node
    """
    node_map: dict[str, HierarchyNode] = {n.node_id: n for n in all_nodes}
    node_map["root"] = root

    entries: list[NestedSetEntry] = []
    counter = [0]  # mutable counter for closure

    def dfs(node_id: str, depth: int) -> None:
        counter[0] += 1
        left = counter[0]

        node = node_map.get(node_id)
        if node:
            for child_id in node.children:
                dfs(child_id, depth + 1)

        counter[0] += 1
        right = counter[0]

        entries.append(NestedSetEntry(
            node_id=node_id,
            left=left,
            right=right,
            depth=depth,
        ))

    dfs("root", 0)
    return entries


def build_hierarchy(
    document_id: str,
    title: str,
    nodes: list[HierarchyNode],
) -> ParsedHierarchy:
    """Build the complete hierarchy: adjacency tree + nested set index.

    Returns a ParsedHierarchy with all nodes, nested set entries, and warnings.
    """
    root = build_document_root(document_id, title)

    # Assign parents and children
    assigned = assign_parents(nodes)

    # Populate root's children list from assigned nodes
    for node in assigned:
        if node.parent_id == "root":
            root.children.append(node.node_id)

    # Build nested set
    nested_set = build_nested_set(root, [root] + assigned)

    return ParsedHierarchy(
        document_id=document_id,
        root_id="root",
        nodes=[root] + assigned,
        nested_set=nested_set,
        warnings=[],
    )
