"""Entity resolution — detect and merge duplicate graph nodes."""

from __future__ import annotations

from typing import Any

from src.knowledge_graph.schema import NodeLabel


def _normalize(text: str) -> str:
    """Normalize a string for comparison: lowercase, strip, collapse whitespace."""
    return " ".join(text.lower().strip().split())


def find_duplicate_nodes(graph, label: str, key: str = "name") -> list[list[dict[str, Any]]]:
    """Find groups of nodes with the same label and matching property.

    Returns groups where each group is a list of nodes that should be merged.
    """
    nodes = graph.get_nodes_by_label(label)
    groups: dict[str, list[dict[str, Any]]] = {}

    for node in nodes:
        val = node.get(key, "")
        if not val:
            continue
        norm = _normalize(str(val))
        if norm not in groups:
            groups[norm] = []
        groups[norm].append(node)

    return [g for g in groups.values() if len(g) > 1]


def merge_nodes(graph, keep_id: str, merge_ids: list[str]) -> int:
    """Merge multiple nodes into one, re-pointing all edges.

    The node with keep_id is retained. All edges from/to merge_ids
    are re-pointed to keep_id, then the merge_ids nodes are deleted.

    Returns the number of edges redirected.
    """
    edges_redirected = 0

    for mid in merge_ids:
        if mid == keep_id:
            continue

        # Re-point outgoing edges
        for edge in graph.get_edges(mid, direction="out"):
            to_node = edge.get("to_node") or edge.get("m", {}).get("node_id")
            if to_node and to_node != keep_id:
                graph.create_edge(keep_id, to_node, edge["rel_type"])
                edges_redirected += 1

        # Re-point incoming edges
        for edge in graph.get_edges(mid, direction="in"):
            from_node = edge.get("from_node") or edge.get("n", {}).get("node_id")
            if from_node and from_node != keep_id:
                graph.create_edge(from_node, keep_id, edge["rel_type"])
                edges_redirected += 1

        # Delete the merged node
        graph.delete_node(mid)

    return edges_redirected


def resolve_duplicates(graph, label: str, key: str = "name") -> int:
    """Resolve all duplicate nodes for a given label.

    Returns total number of nodes merged.
    """
    groups = find_duplicate_nodes(graph, label, key)
    merged_count = 0

    for group in groups:
        keep = group[0]
        merge_ids = [n["node_id"] for n in group[1:]]
        merge_nodes(graph, keep["node_id"], merge_ids)
        merged_count += len(merge_ids)

    return merged_count
