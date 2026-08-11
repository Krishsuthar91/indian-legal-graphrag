"""Retrieval metrics — node-level ranking metrics plus section/hierarchy accuracy.

The node-level metrics (Recall@K, Precision@K, MRR) use a gold relevance set
per question built by mapping the expected sections to graph nodes whose
section key matches (``src/evaluation/sections.matches``). Section Accuracy is
the fraction of expected sections surfaced by the retrieved evidence, and
Hierarchy Accuracy is the fraction of evidence whose reported ancestor path
matches the true graph ancestry.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence

from src.evaluation.sections import matches, section_coverage, section_keys_from_text
from src.retrieval.context import get_ancestor_chain


def relevant_node_ids(graph, expected_sections: Iterable[str]) -> set[str]:
    """Graph node ids whose section key matches any expected section."""
    expected = [key for key in expected_sections if key]
    if not expected:
        return set()
    relevant: set[str] = set()
    for node in graph.all_nodes():
        node_id = node.get("node_id", "")
        if not node_id:
            continue
        keys = section_keys_from_text(node.get("numbering", ""))
        keys.update(section_keys_from_text(node.get("title", "")))
        if any(matches(exp, key) for exp in expected for key in keys):
            relevant.add(node_id)
    return relevant


def recall_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    """Fraction of gold-relevant nodes present in the top-k results."""
    if not relevant or k <= 0:
        return 0.0
    return len(relevant.intersection(retrieved[:k])) / len(relevant)


def precision_at_k(relevant: set[str], retrieved: Sequence[str], k: int) -> float:
    """Fraction of the top-k results that are gold-relevant."""
    if k <= 0:
        return 0.0
    return len(relevant.intersection(retrieved[:k])) / k


def mean_reciprocal_rank(relevant: set[str], retrieved: Sequence[str]) -> float:
    """Inverse rank of the first gold-relevant result (0 when absent)."""
    for i, node_id in enumerate(retrieved, 1):
        if node_id in relevant:
            return 1.0 / i
    return 0.0


def section_accuracy(expected_sections: Iterable[str], predicted_sections: Iterable[str]) -> float:
    """Fraction of expected sections covered by the retrieved evidence sections."""
    return section_coverage(expected_sections, predicted_sections)


def hierarchy_accuracy(graph, result) -> float:
    """Fraction of evidence whose reported path equals the true ancestor chain."""
    evidence = list(result.evidence)
    if not evidence:
        return 0.0
    correct = 0
    for ev in evidence:
        if not graph.get_node(ev.node_id):
            continue
        true_chain = [a["node_id"] for a in reversed(get_ancestor_chain(graph, ev.node_id))]
        true_chain.append(ev.node_id)
        if list(ev.path) == true_chain:
            correct += 1
    return round(correct / len(evidence), 4)


def retrieval_metrics(graph, item, result, *, k5: int = 5, k10: int = 10) -> dict[str, float]:
    """Full per-question retrieval metric vector."""
    relevant = relevant_node_ids(graph, item.expected_sections)
    retrieved = [ev.node_id for ev in result.evidence]
    predicted = {
        key
        for ev in result.evidence
        for key in section_keys_from_text(ev.numbering) | section_keys_from_text(ev.title)
    }
    metrics = {
        "recall_at_5": recall_at_k(relevant, retrieved, k5),
        "recall_at_10": recall_at_k(relevant, retrieved, k10),
        "precision_at_5": precision_at_k(relevant, retrieved, k5),
        "mrr": mean_reciprocal_rank(relevant, retrieved),
        "section_accuracy": section_accuracy(item.expected_sections, predicted),
        "hierarchy_accuracy": hierarchy_accuracy(graph, result),
    }
    return {key: round(value, 4) for key, value in metrics.items()}


def aggregate_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    """Mean of per-query metric dicts (empty input yields empty output)."""
    if not rows:
        return {}
    keys = list(rows[0])
    return {key: round(statistics.mean(row[key] for row in rows), 4) for key in keys}
