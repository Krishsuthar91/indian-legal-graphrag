"""Graph traversal APIs for querying the knowledge graph."""

from __future__ import annotations

from collections import deque
from typing import Any


def get_parent(graph, node_id: str) -> dict[str, Any] | None:
    """Get the parent node (via PART_OF relationship)."""
    edges = graph.get_edges(node_id, rel_type="PART_OF", direction="out")
    if edges:
        parent_id = edges[0]["to_node"]
        return graph.get_node(parent_id)
    return None


def get_children(graph, node_id: str) -> list[dict[str, Any]]:
    """Get all direct children (via PART_OF relationship, incoming)."""
    edges = graph.get_edges(node_id, rel_type="PART_OF", direction="in")
    children = []
    for edge in edges:
        child_id = edge["from_node"]
        node = graph.get_node(child_id)
        if node:
            children.append(node)
    return sorted(children, key=lambda n: n.get("hierarchy_level", 0))


def get_neighbors(graph, node_id: str, rel_type: str | None = None) -> list[dict[str, Any]]:
    """Get all neighboring nodes (both directions)."""
    edges = graph.get_edges(node_id, rel_type=rel_type)
    neighbor_ids = set()
    for edge in edges:
        if edge["from_node"] == node_id:
            neighbor_ids.add(edge["to_node"])
        else:
            neighbor_ids.add(edge["from_node"])
    return [n for n in (graph.get_node(nid) for nid in neighbor_ids) if n]


def citation_chain(graph, node_id: str, max_depth: int = 5) -> list[dict[str, Any]]:
    """BFS traversal following CITES and REFERENCES edges.

    Returns nodes in order of citation distance from the source.
    """
    visited: set[str] = {node_id}
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])
    result: list[dict[str, Any]] = []

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue

        edges = graph.get_edges(current, rel_type="CITES")
        edges += graph.get_edges(current, rel_type="REFERENCES")

        for edge in edges:
            neighbor_id = edge["to_node"]
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                node = graph.get_node(neighbor_id)
                if node:
                    result.append({"node": node, "depth": depth + 1, "rel_type": edge["rel_type"]})
                    queue.append((neighbor_id, depth + 1))

    return result


def get_all_citations(graph, node_id: str) -> list[dict[str, Any]]:
    """Get all nodes cited by this node."""
    edges = graph.get_edges(node_id, direction="out")
    citations = []
    for edge in edges:
        if edge["rel_type"] in ("CITES", "REFERENCES"):
            node = graph.get_node(edge["to_node"])
            if node:
                citations.append({"node": node, "rel_type": edge["rel_type"]})
    return citations


def get_cited_by(graph, node_id: str) -> list[dict[str, Any]]:
    """Get all nodes that cite this node."""
    edges = graph.get_edges(node_id, direction="in")
    cited_by = []
    for edge in edges:
        if edge["rel_type"] in ("CITES", "REFERENCES"):
            node = graph.get_node(edge["from_node"])
            if node:
                cited_by.append({"node": node, "rel_type": edge["rel_type"]})
    return cited_by


def shortest_path(graph, from_id: str, to_id: str, max_depth: int = 6) -> list[str] | None:
    """Find shortest path between two nodes using BFS.

    Returns list of node_ids forming the path, or None if no path found.
    """
    if from_id == to_id:
        return [from_id]

    visited: set[str] = {from_id}
    queue: deque[tuple[str, list[str]]] = deque([(from_id, [from_id])])

    while queue:
        current, path = queue.popleft()
        if len(path) > max_depth:
            continue

        edges = graph.get_edges(current)
        for edge in edges:
            neighbor = edge["to_node"] if edge["from_node"] == current else edge["from_node"]
            if neighbor not in visited:
                new_path = path + [neighbor]
                if neighbor == to_id:
                    return new_path
                visited.add(neighbor)
                queue.append((neighbor, new_path))

    return None
