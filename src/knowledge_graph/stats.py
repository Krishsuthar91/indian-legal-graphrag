"""Graph statistics and export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.knowledge_graph.schema import NodeLabel, RelType


def get_graph_stats(graph) -> dict[str, Any]:
    """Compute comprehensive graph statistics."""
    stats: dict[str, Any] = {}

    # Node counts by label
    stats["total_nodes"] = graph.node_count()
    stats["nodes_by_label"] = {}
    for label in NodeLabel:
        count = graph.node_count(label.value)
        if count > 0:
            stats["nodes_by_label"][label.value] = count

    # Edge counts by type
    stats["total_edges"] = graph.edge_count()
    stats["edges_by_type"] = {}
    for rel in RelType:
        count = graph.edge_count(rel.value)
        if count > 0:
            stats["edges_by_type"][rel.value] = count

    # Degree statistics
    stats["avg_degree"] = _avg_degree(graph)
    stats["max_degree"] = _max_degree(graph)

    return stats


def _avg_degree(graph) -> float:
    """Compute average node degree."""
    from src.knowledge_graph.traversal import get_neighbors

    total_nodes = graph.node_count()
    if total_nodes == 0:
        return 0.0

    total_degree = 0
    # Sample nodes from each label
    for label in NodeLabel:
        nodes = graph.get_nodes_by_label(label.value)
        for node in nodes[:50]:  # limit sampling
            neighbors = get_neighbors(graph, node["node_id"])
            total_degree += len(neighbors)

    sampled = sum(
        min(len(graph.get_nodes_by_label(l.value)), 50)
        for l in NodeLabel
        if graph.node_count(l.value) > 0
    )
    return round(total_degree / max(sampled, 1), 2)


def _max_degree(graph) -> int:
    """Find the maximum node degree."""
    from src.knowledge_graph.traversal import get_neighbors

    max_d = 0
    for label in NodeLabel:
        for node in graph.get_nodes_by_label(label.value)[:100]:
            neighbors = get_neighbors(graph, node["node_id"])
            max_d = max(max_d, len(neighbors))
    return max_d


def export_stats(graph, output_path: Path | None = None) -> dict[str, Any]:
    """Compute and optionally save graph statistics."""
    stats = get_graph_stats(graph)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    return stats
