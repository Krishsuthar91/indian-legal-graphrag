"""Tests for the hybrid retrieval orchestrator."""

import pytest

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.retrieval.query import parse_query
from src.retrieval.ranker import RetrievalResult, retrieve


@pytest.fixture()
def graph():
    g = InMemoryGraph()
    g.create_node("Document", "doc", {"title": "THE INDIAN CONTRACT ACT, 1892", "text": ""})
    g.create_node("Chapter", "ch1", {"title": "CHAPTER I", "text": "Preliminary"})
    g.create_node("Chapter", "ch2", {"title": "CHAPTER II", "text": "Of Contracts"})
    g.create_node("Chapter", "ch3", {"title": "CHAPTER III", "text": "Of Performance"})
    g.create_node("Section", "s1", {
        "title": "Short title", "numbering": "1",
        "text": "This Act may be called the Indian Contract Act.",
    })
    g.create_node("Section", "s2", {
        "title": "Definitions", "numbering": "2",
        "text": "contract means an agreement enforceable by law.",
    })
    g.create_node("Section", "s3", {
        "title": "Communication of proposals", "numbering": "3",
        "text": "The communication of proposals is complete when it comes to knowledge of the offeree.",
    })
    g.create_node("Section", "s4", {
        "title": "Performance of contracts", "numbering": "4",
        "text": "Performance of contracts. (a) where the contract provides (b) where no provision is made.",
    })
    g.create_edge("ch1", "doc", "PART_OF")
    g.create_edge("ch2", "doc", "PART_OF")
    g.create_edge("ch3", "doc", "PART_OF")
    g.create_edge("s1", "ch1", "PART_OF")
    g.create_edge("s2", "ch1", "PART_OF")
    g.create_edge("s3", "ch2", "PART_OF")
    g.create_edge("s4", "ch3", "PART_OF")
    return g


class TestRetrieveBasic:
    def test_accepts_string_query(self, graph):
        results = retrieve(graph, "performance of contracts")
        assert results
        assert results[0].node_id == "s4"

    def test_accepts_query_object(self, graph):
        results = retrieve(graph, parse_query("performance of contracts"))
        assert results
        assert results[0].node_id == "s4"

    def test_returns_result_type(self, graph):
        results = retrieve(graph, "performance of contracts")
        assert isinstance(results[0], RetrievalResult)

    def test_empty_query_returns_empty(self, graph):
        assert retrieve(graph, "") == []
        assert retrieve(graph, "the and of") == []

    def test_no_match_returns_empty(self, graph):
        assert retrieve(graph, "quantum entanglement fusion reactor") == []


class TestRetrieveRanking:
    def test_seed_outranks_context(self, graph):
        results = retrieve(graph, "performance of contracts")
        assert results[0].is_seed is True
        assert results[0].score >= results[1].score

    def test_hierarchy_includes_ancestor(self, graph):
        results = retrieve(graph, "performance of contracts")
        node_ids = [r.node_id for r in results]
        assert "s4" in node_ids
        assert "ch3" in node_ids
        assert "doc" in node_ids

    def test_result_has_path(self, graph):
        results = retrieve(graph, "performance of contracts")
        top = results[0]
        assert top.path == ["ch3", "doc"]

    def test_result_has_signals(self, graph):
        results = retrieve(graph, "performance of contracts")
        assert set(results[0].signals.keys()) == {"text", "hierarchy", "citation", "structural"}

    def test_result_has_matched_keywords(self, graph):
        results = retrieve(graph, "performance of contracts")
        assert set(results[0].matched_keywords) == {"performance", "contracts"}

    def test_top_k_limit(self, graph):
        results = retrieve(graph, "performance of contracts", top_k=2)
        assert len(results) == 2

    def test_threshold_filters_low_scores(self, graph):
        all_results = retrieve(graph, "performance of contracts", top_k=10)
        filtered = retrieve(graph, "performance of contracts", top_k=10, threshold=0.5)
        assert len(filtered) < len(all_results)


class TestRetrieveByReference:
    def test_section_numbering_query(self, graph):
        results = retrieve(graph, "what does section 4 say")
        assert results
        assert results[0].node_id == "s4"
        assert results[0].is_seed is True

    def test_section_reference_in_text(self, graph):
        graph.create_node("Section", "s5", {
            "title": "Note", "numbering": "5",
            "text": "This applies as per Section 4 of the Act.",
        })
        graph.create_edge("s5", "ch3", "PART_OF")
        results = retrieve(graph, "section 4")
        assert any(r.node_id == "s4" for r in results)
        assert any(r.node_id == "s5" for r in results)

    def test_snippet_truncated(self, graph):
        graph.create_node("Section", "s_long", {
            "title": "Long", "numbering": "9",
            "text": "word " * 200,
        })
        graph.create_edge("s_long", "ch1", "PART_OF")
        results = retrieve(graph, "word", top_k=10)
        long_result = next(r for r in results if r.node_id == "s_long")
        assert len(long_result.text) <= 401
