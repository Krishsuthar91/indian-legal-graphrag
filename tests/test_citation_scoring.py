"""Focused tests for Issue #6 — citation score semantics.

The Phase-3 ranking ``citation`` signal must reflect whether a node actually
matches the legal citation requested by the query. Cross-reference frequency
(CITES/REFERENCES edge counts) must never substitute for a match — unrelated
high-reference nodes must not receive the maximum citation score and outrank
the actual provision.
"""

from __future__ import annotations

import pytest

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine, _Signal
from src.retrieval.query import parse_query
from src.retrieval.scorer import citation_score


def _build_graph() -> InMemoryGraph:
    """ICA-like graph with an exact-match section, a text-mention section,
    an unrelated high-reference hub, and an orphan."""
    g = InMemoryGraph()
    g.create_node(
        "Document", "doc1", {"document_id": "doc1", "title": "The Indian Contract Act, 1872"}
    )
    g.create_node(
        "Section",
        "s10",
        {
            "document_id": "doc1",
            "numbering": "10",
            "title": "Agreements void",
            "text": "Agreements without consideration are void.",
        },
    )
    g.create_node(
        "Section",
        "s02",
        {
            "document_id": "doc1",
            "numbering": "2",
            "title": "Mere reference",
            "text": "This section refers to section 10 for the general rule.",
        },
    )
    g.create_node(
        "Section",
        "s01",
        {
            "document_id": "doc1",
            "numbering": "1",
            "title": "Short title",
            "text": "This Act may be called the Indian Contract Act.",
        },
    )
    g.create_node(
        "Section",
        "s20",
        {
            "document_id": "doc1",
            "numbering": "20",
            "title": "Orphan",
            "text": "Unrelated provision with no cross references.",
        },
    )
    for i in range(5):
        g.create_edge("s01", f"ref{i}", "CITES")
    g.create_edge("s02", "refX", "CITES")
    return g


@pytest.fixture()
def engine() -> ExplainabilityEngine:
    return ExplainabilityEngine(_build_graph(), vector_retriever=None)


def _fill(graph: InMemoryGraph, engine: ExplainabilityEngine, query: str, node_ids: list[str]):
    parsed = parse_query(query)
    signals = {nid: _Signal() for nid in node_ids}
    engine._fill_ranking_signals(signals, parsed)
    return signals, parsed


def test_exact_section_match_scores_full_citation(engine: ExplainabilityEngine):
    graph = engine.graph
    signals, _ = _fill(graph, engine, "Section 10", ["s10", "s02", "s01", "s20"])
    assert signals["s10"].citation == 1.0


def test_text_mention_match_scores_full_citation(engine: ExplainabilityEngine):
    graph = engine.graph
    signals, _ = _fill(graph, engine, "Section 10", ["s10", "s02", "s01", "s20"])
    # "refers to section 10" is a standalone, word-boundary citation match.
    assert signals["s02"].citation == 1.0


def test_unrelated_high_reference_node_never_gets_max_citation(engine: ExplainabilityEngine):
    """Regression: a node with many CITES edges but no citation match must not
    receive citation=1.0 via frequency normalization."""
    graph = engine.graph
    assert len(graph.get_edges("s01", rel_type="CITES")) == 5
    signals, _ = _fill(graph, engine, "Section 10", ["s10", "s02", "s01", "s20"])
    assert signals["s01"].citation == 0.0
    assert signals["s01"].citation != 1.0


def test_exact_match_ranks_above_high_reference_hub(engine: ExplainabilityEngine):
    """With all other signals equal, the exact-match node outranks the
    high-reference hub that previously tied it at the maximum citation score."""
    graph = engine.graph
    parsed = parse_query("Section 10")
    signals = {nid: _Signal() for nid in ("s10", "s01", "s20")}
    engine._fill_ranking_signals(signals, parsed)

    assert citation_score(graph.get_node("s10"), parsed) == 1.0
    assert citation_score(graph.get_node("s01"), parsed) == 0.0

    rank = {nid: engine._rank(sig) for nid, sig in signals.items()}
    assert rank["s10"] == pytest.approx(rank["s01"] + engine.ranking_weights["citation"])
    assert rank["s10"] > rank["s01"]


def test_no_reference_query_keeps_frequency_popularity(engine: ExplainabilityEngine):
    """Backward compatibility: without a legal reference in the query, the
    normalized cross-reference count still acts as a popularity signal."""
    graph = engine.graph
    signals, parsed = _fill(graph, engine, "What is consideration?", ["s10", "s01", "s20"])

    for nid in signals:
        assert citation_score(graph.get_node(nid), parsed) == 0.0
    assert signals["s01"].citation == 1.0  # 5 edges / max(5)
    assert signals["s10"].citation == 0.0  # no edges
    assert signals["s20"].citation == 0.0
