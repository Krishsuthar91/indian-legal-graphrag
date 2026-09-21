"""Hierarchical context expansion over the knowledge graph.

Provides ancestor/descendant traversal along PART_OF edges and evidence
propagation used for the hierarchical component of hybrid retrieval.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from src.knowledge_graph.traversal import get_children, get_parent


def get_ancestor_chain(graph, node_id: str) -> list[dict[str, Any]]:
    """Walk up PART_OF edges to the document root.

    Returns [parent, grandparent, ..., root]. Empty for a root node.
    """
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = node_id
    while current and current not in seen:
        seen.add(current)
        parent = get_parent(graph, current)
        if not parent:
            break
        chain.append(parent)
        current = parent["node_id"]
    return chain


def get_descendant_ids(graph, node_id: str, max_depth: int | None = None) -> set[str]:
    """BFS down PART_OF edges, returning all descendant node_ids."""
    result: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])
    while queue:
        current, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for child in get_children(graph, current):
            child_id = child["node_id"]
            if child_id not in result:
                result.add(child_id)
                queue.append((child_id, depth + 1))
    return result


def get_related_nodes(
    graph, node_id: str, rel_types: list[str] | None = None
) -> list[dict[str, Any]]:
    """Nodes connected to node_id via any relationship type (or specified ones)."""
    neighbor_ids: set[str] = set()
    for edge in graph.get_edges(node_id):
        if rel_types and edge["rel_type"] not in rel_types:
            continue
        if edge["from_node"] == node_id:
            neighbor_ids.add(edge["to_node"])
        else:
            neighbor_ids.add(edge["from_node"])
    return [n for n in (graph.get_node(nid) for nid in neighbor_ids) if n]


def _node_document(graph, node_id: str) -> str:
    """Return the ``document_id`` of a node, or ``""`` when it has none."""
    node = graph.get_node(node_id)
    if not node:
        return ""
    return str(node.get("document_id") or "")


def _same_document(seed_document: str, node) -> bool:
    """True when ``node`` may be included in a seed's propagation walk.

    The document boundary only ever blocks nodes that explicitly belong to a
    different document than the originating seed. A node without a
    ``document_id`` carries no boundary information and is treated as
    transparent, so propagation over graphs that do not annotate every node
    (synthetic fixtures, partial imports) behaves exactly as before.
    """
    if not seed_document:
        return True
    node_document = str((node or {}).get("document_id") or "")
    if not node_document:
        return True
    return node_document == seed_document


def propagate_hierarchy(
    graph,
    seed_ids: list[str],
    up_factor: float = 0.6,
    down_factor: float = 0.4,
) -> dict[str, float]:
    """Propagate retrieval evidence from seed nodes to ancestors and descendants.

    A seed node receives strength 1.0; each ancestor level is attenuated by
    ``up_factor`` and each descendant level by ``down_factor``. Strengths from
    multiple seeds accumulate (capped at 1.0).

    Propagation is bounded by document: a seed never expands into a node whose
    ``document_id`` differs from the originating seed's, so evidence never
    crosses Acts (or any hierarchy boundary defined by ``document_id``).

    Returns a mapping node_id -> evidence strength in [0, 1].
    """
    evidence: dict[str, float] = {}

    def _add(node_id: str, strength: float) -> None:
        evidence[node_id] = min(1.0, evidence.get(node_id, 0.0) + strength)

    for seed in seed_ids:
        _add(seed, 1.0)
        seed_document = _node_document(graph, seed)

        # Ancestors
        strength = up_factor
        seen: set[str] = {seed}
        current = seed
        while strength > 1e-4:
            parent = get_parent(graph, current)
            if not parent or parent["node_id"] in seen:
                break
            if not _same_document(seed_document, parent):
                break
            seen.add(parent["node_id"])
            _add(parent["node_id"], strength)
            current = parent["node_id"]
            strength *= up_factor

        # Descendants
        visited: set[str] = {seed}
        queue: deque[tuple[str, int]] = deque([(seed, 0)])
        while queue:
            current, depth = queue.popleft()
            child_strength = down_factor ** (depth + 1)
            if child_strength <= 1e-4:
                continue
            for child in get_children(graph, current):
                child_id = child["node_id"]
                if not _same_document(seed_document, child):
                    continue
                if child_id in visited:
                    continue
                visited.add(child_id)
                _add(child_id, child_strength)
                queue.append((child_id, depth + 1))

    return evidence
