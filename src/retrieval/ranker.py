"""Hybrid Hierarchical Graph Retrieval (HHGR) — orchestration.

Pipeline:
1. Parse the query into keywords + legal references.
2. Select seed nodes (text match above threshold or citation/numbering match).
3. Propagate hierarchical evidence from seeds to ancestors/descendants.
4. Score candidates with four weighted signals.
5. Rank and return top-k results with a signal breakdown and context path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.logging_config import get_logger
from src.retrieval.context import get_ancestor_chain, propagate_hierarchy
from src.retrieval.query import RetrievalQuery, parse_query
from src.retrieval.scorer import (
    citation_score,
    combine_signals,
    leaf_direct_priority,
    matched_keywords,
    structural_importance,
    text_score,
)

log = get_logger("retrieval")

TEXT_THRESHOLD = 0.25
SNIPPET_CHARS = 400


@dataclass
class RetrievalResult:
    """A single retrieved node with its hybrid score and evidence."""

    node_id: str
    label: str
    title: str
    text: str
    numbering: str
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    path: list[str] = field(default_factory=list)      # ancestor chain node ids
    matched_keywords: list[str] = field(default_factory=list)
    is_seed: bool = False


def _node_to_result(
    graph,
    node: dict[str, Any],
    query: RetrievalQuery,
    signals: dict[str, float],
    path: list[str],
    is_seed: bool,
    score: float | None = None,
) -> RetrievalResult:
    text = node.get("text", "") or ""
    if len(text) > SNIPPET_CHARS:
        text = text[:SNIPPET_CHARS] + "…"
    return RetrievalResult(
        node_id=node["node_id"],
        label=node.get("label", ""),
        title=node.get("title", ""),
        text=text,
        numbering=node.get("numbering", ""),
        score=combine_signals(signals) if score is None else score,
        signals=signals,
        path=path,
        matched_keywords=matched_keywords(node, query),
        is_seed=is_seed,
    )


def retrieve(
    graph,
    query: str | RetrievalQuery,
    top_k: int = 5,
    threshold: float = 0.0,
    document_id: str | None = None,
) -> list[RetrievalResult]:
    """Run hybrid hierarchical graph retrieval over the given graph store.

    ``document_id`` restricts candidate nodes to those belonging to the
    specified document (via the ``document_id`` property set during import).
    When *None* all graph nodes are searched (legacy behaviour).
    """
    if isinstance(query, str):
        query = parse_query(query)

    if query.is_empty:
        log.info("retrieval.empty_query")
        return []

    all_nodes = [n for n in graph.all_nodes() if n.get("node_id")]
    if document_id:
        nodes = [n for n in all_nodes if n.get("document_id") == document_id]
        if not nodes:
            log.info(
                "retrieval.document_filter_empty",
                document_id=document_id,
                fallback=True,
            )
            nodes = all_nodes
    else:
        nodes = all_nodes

    # 1. Seed selection: per-node text + citation signals
    per_node: dict[str, dict[str, float]] = {}
    seeds: list[dict[str, Any]] = []
    for node in nodes:
        t = text_score(node, query)
        c = citation_score(node, query)
        per_node[node["node_id"]] = {"text": t, "citation": c}
        if t >= TEXT_THRESHOLD or c >= 1.0:
            seeds.append(node)

    if not seeds:
        log.info("retrieval.no_seeds", query=query.raw)
        return []

    # 2. Hierarchical evidence propagation from seeds
    seed_ids = [n["node_id"] for n in seeds]
    evidence = propagate_hierarchy(graph, seed_ids)

    # 3. Structural importance, normalized over the candidate set
    structural: dict[str, float] = {}
    for nid in evidence:
        node = graph.get_node(nid)
        if node:
            structural[nid] = structural_importance(graph, node)
    max_structural = max(structural.values()) if structural else 0.0

    # 4. Score candidates
    results: list[RetrievalResult] = []
    for nid in evidence:
        node = graph.get_node(nid)
        if not node:
            continue
        signals = {
            "text": per_node.get(nid, {}).get("text", 0.0),
            "hierarchy": evidence[nid],
            "citation": per_node.get(nid, {}).get("citation", 0.0),
            "structural": (structural[nid] / max_structural) if max_structural > 0 else 0.0,
        }
        score = combine_signals(signals)
        # Prefer a legal leaf (Section/Clause/...) whose own text directly
        # matches the query over container nodes (Chapter/Part/...) that only
        # aggregate keyword-bearing descendants. This is a bounded ranking
        # bonus, not a linear weight, so it cannot swamp the citation signal.
        if leaf_direct_priority(node, query) == 1.0:
            score = min(1.0, score + 0.10)
        result = _node_to_result(
            graph,
            node,
            query,
            signals,
            [p["node_id"] for p in get_ancestor_chain(graph, nid)],
            is_seed=nid in set(seed_ids),
            score=score,
        )
        if result.score < threshold:
            continue
        results.append(result)

    results.sort(key=lambda r: (-r.score, r.node_id))
    top = results[:top_k]

    log.info(
        "retrieval.complete",
        query=query.raw,
        seeds=len(seed_ids),
        candidates=len(results),
        returned=len(top),
    )
    return top
