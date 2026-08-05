"""Hybrid scoring signals for graph retrieval.

Four signals are combined into a single relevance score:
- text:      lexical overlap between query keywords and node title/text
- citation:  query legal reference matching the node (numbering or cited text)
- hierarchy: proximity to query matches within the document hierarchy
- structural: node importance (degree + subtree size), normalized per query
"""

from __future__ import annotations

import re
from typing import Any

from src.retrieval.context import get_descendant_ids
from src.retrieval.query import RetrievalQuery, tokenize

WEIGHTS: dict[str, float] = {
    "text": 0.40,
    "hierarchy": 0.25,
    "citation": 0.20,
    "structural": 0.15,
}


def _token_set(text: str) -> set[str]:
    return set(tokenize(text))


def text_score(node: dict[str, Any], query: RetrievalQuery) -> float:
    """Fraction of query keywords found in the node's title and text."""
    if not query.keywords:
        return 0.0
    combined = _token_set(f"{node.get('title', '')} {node.get('text', '')}")
    if not combined:
        return 0.0

    qset = set(query.keywords)
    overlap = qset & combined
    if not overlap:
        return 0.0

    coverage = len(overlap) / len(qset)
    title_overlap = overlap & _token_set(node.get("title", ""))
    title_bonus = min(0.2, 0.1 * len(title_overlap))
    return min(1.0, coverage + title_bonus)


def citation_score(node: dict[str, Any], query: RetrievalQuery) -> float:
    """Score from a query legal reference matching the node.

    Exact ``numbering`` match (e.g. query "Section 5" vs node numbering "5")
    or the normalized reference appearing in the node's text/title.
    """
    if not query.section_refs and not query.section_numbers:
        return 0.0

    numbering = str(node.get("numbering", "")).strip()
    combined = f"{node.get('title', '')} {node.get('text', '')}".lower()

    for ref in query.section_refs:
        if ref in combined:
            return 1.0

    for num in query.section_numbers:
        if not num or not numbering:
            continue
        if numbering == num:
            return 1.0
        if num.isdigit() and numbering.isdigit() and numbering.lstrip("0") == num.lstrip("0"):
            return 1.0

    return 0.0


def structural_importance(graph, node: dict[str, Any]) -> float:
    """Query-independent node importance: degree + subtree size."""
    degree = len(graph.get_edges(node["node_id"]))
    subtree_size = len(get_descendant_ids(graph, node["node_id"]))
    return degree + 0.1 * subtree_size


def combine_signals(signals: dict[str, float]) -> float:
    """Weighted sum of individual retrieval signals."""
    return round(
        sum(WEIGHTS.get(key, 0.0) * float(value) for key, value in signals.items()),
        6,
    )


def matched_keywords(node: dict[str, Any], query: RetrievalQuery) -> list[str]:
    """Query keywords that actually appear in the node's title/text."""
    combined = _token_set(f"{node.get('title', '')} {node.get('text', '')}")
    if not query.keywords:
        return []
    return [k for k in query.keywords if k in combined]
