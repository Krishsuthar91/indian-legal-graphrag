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
from src.retrieval.query import _STOPWORDS, RetrievalQuery, tokenize

WEIGHTS: dict[str, float] = {
    "text": 0.40,
    "hierarchy": 0.25,
    "citation": 0.20,
    "structural": 0.15,
    "leaf": 0.00,
}

# Legal leaf node labels: concrete provisions a query can be asking about.
# Container nodes (Chapter/Part/Document/... ) merely group these leaves, so a
# query that directly matches a leaf should prefer the leaf over its container.
LEAF_LABELS: frozenset[str] = frozenset({
    "section", "clause", "article", "rule", "order", "paragraph", "subclause",
})


def leaf_direct_priority(node: dict[str, Any], query: RetrievalQuery) -> float:
    """1.0 if the node is a legal leaf whose own text/title matches the query;
    0.0 otherwise.

    This offsets the container-bias from ``structural_importance``, where a
    Chapter/Part wins purely because it aggregates many keyword-bearing
    descendants. A query asking about "coercion" should surface the Section
    that *defines* coercion, not the Chapter that contains it.
    """
    label = str(node.get("label", "")).lower()
    if label not in LEAF_LABELS:
        return 0.0
    if not query.keywords:
        return 0.0
    combined = _token_set(f"{node.get('title', '')} {node.get('text', '')}")
    if not combined:
        return 0.0
    if combined & set(query.keywords):
        return 1.0
    return 0.0


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


def keyword_overlap(node: dict[str, Any], query: RetrievalQuery) -> float:
    """Fraction of query keywords found in the node's title/text.

    Stop words are ignored so common tokens never inflate the overlap. Unlike
    ``text_score`` there is no title bonus — this is a pure lexical overlap
    signal used only for ordering evidence.
    """
    keywords = [k for k in query.keywords if k not in _STOPWORDS]
    if not keywords:
        return 0.0
    combined = _token_set(f"{node.get('title', '')} {node.get('text', '')}")
    if not combined:
        return 0.0
    matched = sum(1 for k in set(keywords) if k in combined)
    return min(1.0, matched / len(set(keywords)))


def citation_score(node: dict[str, Any], query: RetrievalQuery) -> float:
    """Score from a query legal reference matching the node.

    Exact ``numbering`` match (e.g. query "Section 5" vs node numbering "5")
    or the normalized reference appearing in the node's text/title.

    When the query specifies a ``document_id`` the node must belong to the same
    document for a citation match to be awarded.  This prevents Section 10 of
    the Indian Contract Act from matching Section 10 of the Indian Penal Code.

    A reference found in body *text* (``ref in combined``) is only awarded when
    it appears as a standalone reference (word boundaries), so "Section 1" does
    not spuriously match "Section 141" or "Section 12".  This stops a query for
    one section flooding the seed set with unrelated sections whose prose merely
    cross-references the number.
    """
    if not query.section_refs and not query.section_numbers:
        return 0.0

    if query.document_id:
        node_doc = node.get("document_id", "")
        if node_doc and node_doc != query.document_id:
            return 0.0

    numbering = str(node.get("numbering", "")).strip()
    combined = f"{node.get('title', '')} {node.get('text', '')}".lower()

    for num in query.section_numbers:
        if not num or not numbering:
            continue
        if numbering == num:
            return 1.0
        if num.isdigit() and numbering.isdigit() and numbering.lstrip("0") == num.lstrip("0"):
            return 1.0

    for ref in query.section_refs:
        # Word-boundary match: "section 1" must not match "section 141"/"section 12".
        if re.search(rf"\b{re.escape(ref)}\b", combined):
            return 1.0

    return 0.0


def citation_frequency(graph, node_id: str) -> float:
    """Raw count of CITES/REFERENCES edges involving the node (both directions).

    Used as the base for a citation-frequency signal; callers normalize it to
    [0, 1] (e.g. by the maximum count across the candidate set).
    """
    count = 0
    for rel_type in ("CITES", "REFERENCES"):
        count += len(graph.get_edges(node_id, rel_type=rel_type))
    return float(count)


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
