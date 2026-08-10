"""Tests for hybrid scoring signals."""

import pytest

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.retrieval.query import RetrievalQuery, parse_query
from src.retrieval.scorer import (
    WEIGHTS,
    citation_frequency,
    citation_score,
    combine_signals,
    keyword_overlap,
    matched_keywords,
    structural_importance,
    text_score,
)


def _node(**overrides):
    node = {
        "node_id": "n1",
        "label": "Section",
        "title": "Short title",
        "text": "This Act may be called the Indian Contract Act.",
        "numbering": "1",
    }
    node.update(overrides)
    return node


class TestTextScore:
    def test_full_keyword_coverage(self):
        q = parse_query("Indian Contract Act")
        assert text_score(_node(), q) == 1.0

    def test_partial_coverage(self):
        q = parse_query("Indian Contract Criminal")
        score = text_score(_node(), q)
        assert score > 0.0
        assert score < 1.0

    def test_no_overlap(self):
        q = parse_query("electricity supply")
        assert text_score(_node(), q) == 0.0

    def test_empty_keywords(self):
        q = parse_query("the and of")
        assert text_score(_node(), q) == 0.0

    def test_empty_text(self):
        q = parse_query("contract")
        assert text_score(_node(text="", title=""), q) == 0.0

    def test_title_hit_boosts(self):
        q = parse_query("short title extra")
        plain = _node(title="other", text="short title text here")
        titled = _node(title="short title", text="other")
        assert text_score(titled, q) > text_score(plain, q)


class TestCitationScore:
    def test_numbering_match(self):
        q = parse_query("section 1 of the act")
        assert citation_score(_node(numbering="1"), q) == 1.0

    def test_leading_zero_numbering_match(self):
        q = parse_query("section 7")
        assert citation_score(_node(numbering="07"), q) == 1.0

    def test_reference_in_text(self):
        q = parse_query("what about section 12")
        node = _node(text="As per Section 12 the remedy is...")
        assert citation_score(node, q) == 1.0

    def test_no_reference_match(self):
        q = parse_query("section 99")
        assert citation_score(_node(numbering="1"), q) == 0.0

    def test_no_query_reference(self):
        q = parse_query("performance of contracts")
        assert citation_score(_node(), q) == 0.0


class TestStructuralImportance:
    def test_degree_increases_importance(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.create_node("Chapter", "ch1", {})
        g.create_edge("s1", "ch1", "PART_OF")
        g.create_edge("s2", "ch1", "PART_OF")
        assert structural_importance(g, g.get_node("ch1")) > structural_importance(
            g, g.get_node("s1")
        )

    def test_subtree_increases_importance(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.create_node("Chapter", "ch1", {})
        g.create_edge("s1", "ch1", "PART_OF")
        g.create_edge("s2", "ch1", "PART_OF")
        chapter = structural_importance(g, g.get_node("ch1"))
        leaf = structural_importance(g, g.get_node("s1"))
        assert chapter > leaf


class TestCombineSignals:
    def test_weighted_sum(self):
        score = combine_signals({"text": 1.0, "hierarchy": 1.0, "citation": 1.0, "structural": 1.0})
        assert score == 1.0

    def test_partial_signals(self):
        score = combine_signals({"text": 0.5, "hierarchy": 0.0, "citation": 0.0, "structural": 0.0})
        assert score == pytest.approx(0.5 * WEIGHTS["text"])

    def test_missing_signals_treated_zero(self):
        assert combine_signals({"text": 1.0}) == pytest.approx(WEIGHTS["text"])


class TestKeywordOverlap:
    def test_full_overlap(self):
        q = parse_query("contract performance")
        assert keyword_overlap(_node(text="contract performance", title="X"), q) == 1.0

    def test_partial_overlap(self):
        q = parse_query("contract criminal")
        score = keyword_overlap(_node(), q)
        assert score > 0.0
        assert score < 1.0

    def test_no_overlap(self):
        q = parse_query("electricity supply")
        assert keyword_overlap(_node(), q) == 0.0

    def test_stopwords_in_query_ignored(self):
        q = RetrievalQuery(raw="x", keywords=["the", "contract", "and"])
        assert keyword_overlap(_node(), q) == 1.0

    def test_only_stopwords_returns_zero(self):
        q = RetrievalQuery(raw="x", keywords=["the", "and", "of"])
        assert keyword_overlap(_node(), q) == 0.0

    def test_empty_keywords(self):
        q = parse_query("the and of")
        assert keyword_overlap(_node(), q) == 0.0

    def test_never_exceeds_one(self):
        q = RetrievalQuery(raw="x", keywords=["contract", "contract", "contract"])
        assert keyword_overlap(_node(), q) == 1.0


class TestCitationFrequency:
    def test_counts_citation_edges(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Section", "s2", {})
        g.create_node("Section", "s3", {})
        g.create_edge("s1", "s2", "CITES")
        g.create_edge("s3", "s1", "REFERENCES")
        assert citation_frequency(g, "s1") == 2.0
        assert citation_frequency(g, "s2") == 1.0
        assert citation_frequency(g, "s3") == 1.0

    def test_zero_when_no_edges(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        assert citation_frequency(g, "s1") == 0.0

    def test_ignores_non_citation_edges(self):
        g = InMemoryGraph()
        g.create_node("Section", "s1", {})
        g.create_node("Chapter", "ch1", {})
        g.create_edge("s1", "ch1", "PART_OF")
        assert citation_frequency(g, "s1") == 0.0


class TestMatchedKeywords:
    def test_returns_overlapping_keywords(self):
        q = parse_query("contract performance")
        assert set(matched_keywords(_node(), q)) == {"contract"}

    def test_empty_query(self):
        q = parse_query("the")
        assert matched_keywords(_node(), q) == []
