"""Tests for the explainability engine (Module 7)."""


import pytest

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import (
    DEDUP_TEXT_SIMILARITY,
    ExplainabilityEngine,
    _Signal,
    _text_similarity,
)
from src.retrieval.query import parse_query
from tests.qa_helpers import build_engine, build_graph, build_service


class TestExplain:
    def test_returns_ranked_evidence(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence
        assert result.evidence[0].node_id == "s4"
        assert result.evidence[0].sources
        assert result.evidence[0].final_score > 0

    def test_reasoning_chain_steps(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        kinds = [step.kind for step in result.reasoning_chain]
        assert kinds == ["query_parse", "dense", "graph", "hierarchy", "fusion", "verification"]
        assert all(step.step == i for i, step in enumerate(result.reasoning_chain, 1))

    def test_hierarchy_paths(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        path = next(p for p in result.hierarchy_paths if p.node_id == "s4")
        assert [e.node_id for e in path.entries] == ["doc1", "ch2", "s4"]
        assert path.entries[0].label == "Document"
        assert path.entries[-1].numbering == "4"

    def test_citations(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        assert result.citations
        first = result.citations[0]
        assert first.index == 1
        assert "Section 4" in first.citation_text
        assert first.node_id == "s4"

    def test_section_ref_boosts_confidence(self):
        engine = build_engine()
        result = engine.explain("section 4 performance")
        assert result.retrieval.section_refs == ["section 4"]
        assert result.confidence.factors["citation_bonus"] == 0.1

    def test_confidence_and_validity(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        assert result.confidence.score > 0.45
        assert result.confidence.label == "high"
        assert result.validity.supported is True
        assert result.validity.is_valid is True
        assert result.validity.insufficient_evidence is False

    def test_retrieval_summary(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        assert result.retrieval.dense_hits > 0
        assert result.retrieval.graph_hits > 0
        assert result.retrieval.returned > 0
        assert "performance" in result.retrieval.keywords


class TestGraphOnlyMode:
    def test_works_without_vector_store(self):
        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = engine.explain("performance of contracts")
        assert result.evidence
        assert result.evidence[0].node_id == "s4"
        assert all(ev.dense_score == 0.0 for ev in result.evidence)
        assert any(ev.graph_score > 0 for ev in result.evidence)

    def test_no_evidence_for_gibberish(self):
        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = engine.explain("zzzqxwv unrelated gibberish")
        assert result.evidence == []
        assert result.confidence.score == 0.0
        assert result.confidence.label == "low"
        assert result.validity.supported is False
        assert result.validity.insufficient_evidence is True


class TestCounterAuthority:
    def _graph_with_counter(self) -> InMemoryGraph:
        g = InMemoryGraph()
        g.create_node("Document", "docV", {
            "document_id": "docV", "title": "SAMPLE ACT", "language": "en",
        })
        g.create_node("Chapter", "chV", {
            "title": "CHAPTER I", "text": "General", "hierarchy_level": 4,
        })
        g.create_node("Section", "sVoid", {
            "title": "Void agreements", "numbering": "25", "hierarchy_level": 5,
            "text": "An agreement without consideration is void ab initio and not enforceable.",
        })
        g.create_edge("chV", "docV", "PART_OF")
        g.create_edge("sVoid", "chV", "PART_OF")
        return g

    def test_detects_counter_authority(self):
        graph = self._graph_with_counter()
        engine = build_engine(graph)
        result = engine.explain("agreements without consideration are void")
        assert result.counter_authorities
        ca = result.counter_authorities[0]
        assert ca.node_id == "sVoid"
        assert ca.marker == "void ab initio"
        assert result.validity.has_conflicts is True
        assert result.validity.is_valid is False

    def test_clean_graph_has_no_counter_authorities(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        assert result.counter_authorities == []
        assert result.validity.has_conflicts is False
        assert result.validity.is_valid is True


class TestEvidenceTextResolution:
    """Regression: ranked nodes with empty text must resolve to text-bearing
    descendants (e.g. a Section supplies the text of an empty Document wrapper)
    so the evidence handed to the LLM is never a bare title."""

    def test_ranked_node_with_empty_text_resolves_to_best_descendant(self):
        engine = build_engine()
        parsed = parse_query("performance of contracts")
        node, resolved_id = engine._resolve_evidence_node("doc1", parsed)
        assert resolved_id == "s4"
        assert (node.get("text") or "").strip()

    def test_node_with_text_resolves_to_itself(self):
        engine = build_engine()
        parsed = parse_query("performance of contracts")
        node, resolved_id = engine._resolve_evidence_node("s4", parsed)
        assert resolved_id == "s4"
        assert node["text"].strip()

    def test_all_evidence_blocks_carry_text(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        assert result.evidence
        assert all(ev.text.strip() for ev in result.evidence)
        assert all(ev.snippet.strip() for ev in result.evidence)

    def test_graph_only_evidence_blocks_carry_text(self):
        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = engine.explain("performance of contracts")
        assert result.evidence
        assert all(ev.text.strip() for ev in result.evidence)

    def test_cycle_in_hierarchy_does_not_hang(self):
        """Regression: a PART_OF cycle (malformed/merged data) must terminate
        instead of looping forever in the descendant resolution walk."""
        g = InMemoryGraph()
        g.create_node("Document", "docA", {"title": "DOC A", "language": "en"})
        g.create_node(
            "Section",
            "secA",
            {
                "title": "Definitions",
                "numbering": "2",
                "text": "contract means an agreement enforceable by law.",
            },
        )
        g.create_edge("secA", "docA", "PART_OF")
        g.create_edge("docA", "secA", "PART_OF")
        engine = ExplainabilityEngine(g, vector_retriever=None)
        parsed = parse_query("contract definitions")
        node, resolved_id = engine._resolve_evidence_node("docA", parsed)
        assert resolved_id == "secA"
        assert (node.get("text") or "").strip()

    def test_duplicate_resolved_descendants_are_deduplicated(self):
        """Two empty-text wrappers sharing the same best descendant must not
        produce duplicate evidence blocks."""
        g = InMemoryGraph()
        g.create_node("Document", "docA", {"title": "DOC A", "language": "en"})
        g.create_node("Chapter", "chA", {"title": "CH I", "hierarchy_level": 4})
        g.create_node("Chapter", "chB", {"title": "CH II", "hierarchy_level": 4})
        g.create_node(
            "Section",
            "secA",
            {
                "title": "Definitions",
                "numbering": "2",
                "text": "contract means an agreement enforceable by law.",
            },
        )
        g.create_edge("chA", "docA", "PART_OF")
        g.create_edge("chB", "docA", "PART_OF")
        g.create_edge("secA", "chA", "PART_OF")
        g.create_edge("secA", "chB", "PART_OF")
        engine = ExplainabilityEngine(g, vector_retriever=None)
        parsed = parse_query("contract definitions")
        ids = ["docA", "chA", "chB"]
        signals = {nid: _Signal(dense=0.0, graph=0.1, hierarchy=0.0) for nid in ids}
        evidence = engine._build_evidence(ids, signals, parsed)
        assert len(evidence) == 1
        assert evidence[0].node_id == "secA"
        assert evidence[0].text.strip()


class TestConfiguration:
    def test_custom_confidence_threshold(self):
        engine = build_engine(confidence_threshold=0.99)
        result = engine.explain("performance of contracts")
        assert result.validity.supported is False
        assert result.validity.insufficient_evidence is True

    def test_weights_recorded(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        assert set(result.retrieval_weights) == {"dense", "graph", "hierarchy"}


class TestAdaptiveTopK:
    def test_intent_recorded_and_adaptive_budget_used(self):
        engine = build_engine(adaptive=True, top_k_easy=2)
        result = engine.explain("performance of contracts")
        assert result.retrieval.intent == "explanation"
        assert result.retrieval.retrieval_strategy == "adaptive"
        assert result.retrieval.adaptive_top_k == 2
        assert len(result.evidence) <= 2

    def test_section_lookup_intent(self):
        engine = build_engine(adaptive=True)
        result = engine.explain("what does section 4 say")
        assert result.retrieval.intent == "section_lookup"
        assert result.retrieval.retrieval_strategy == "adaptive"
        assert result.evidence
        assert result.evidence[0].node_id == "s4"

    def test_definition_intent(self):
        engine = build_engine(adaptive=True)
        result = engine.explain("what is the definition of contract")
        assert result.retrieval.intent == "definition"
        assert result.retrieval.adaptive_top_k == engine.top_k_easy

    def test_explicit_top_k_wins(self):
        engine = build_engine(adaptive=True, top_k_easy=2)
        result = engine.explain("performance of contracts", top_k=4)
        assert result.retrieval.retrieval_strategy == "fixed"
        assert result.retrieval.adaptive_top_k is None
        assert len(result.evidence) <= 4

    def test_adaptive_disabled_uses_fixed_default(self):
        engine = build_engine(adaptive=False)
        result = engine.explain("performance of contracts")
        assert result.retrieval.retrieval_strategy == "fixed"
        assert result.retrieval.adaptive_top_k is None
        assert len(result.evidence) <= 5

    def test_intent_recorded_on_reasoning_chain(self):
        engine = build_engine(adaptive=True)
        result = engine.explain("performance of contracts")
        fusion = next(s for s in result.reasoning_chain if s.kind == "fusion")
        assert fusion.detail["intent"] == "explanation"
        assert fusion.detail["strategy"] == "adaptive"

    def test_service_answer_uses_adaptive_default(self):
        service = build_service()
        result = service.answer("performance of contracts")
        assert result.explanation.retrieval.retrieval_strategy == "adaptive"
        assert result.explanation.retrieval.intent == "explanation"


class TestRankingSignals:
    def test_final_score_still_three_signal_sum(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        for ev in result.evidence:
            assert ev.final_score == pytest.approx(
                ev.dense_score + ev.graph_score + ev.hierarchy_score, abs=1e-3
            )

    def test_ranking_breakdown_recorded(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        breakdown = result.retrieval.ranking_breakdown
        assert breakdown
        first = result.evidence[0]
        assert first.node_id in breakdown
        assert {"dense", "graph", "hierarchy", "keyword", "citation", "rank"} <= set(
            breakdown[first.node_id]
        )
        assert 0.0 <= breakdown[first.node_id]["rank"] <= 1.0
        assert all(
            0.0 <= v <= 1.0
            for node in breakdown.values()
            for v in node.values()
        )

    def test_evidence_ordered_by_breakdown_rank(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        ids = [ev.node_id for ev in result.evidence]
        ranks = [result.retrieval.ranking_breakdown[nid]["rank"] for nid in ids]
        assert ranks == sorted(ranks, reverse=True)

    def test_s4_remains_top_evidence(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence[0].node_id == "s4"

    def test_keyword_signal_reflects_query_coverage(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        breakdown = result.retrieval.ranking_breakdown
        assert breakdown["s4"]["keyword"] == 1.0

    def test_graph_only_mode_records_ranking_signals(self):
        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = engine.explain("performance of contracts", top_k=5)
        breakdown = result.retrieval.ranking_breakdown
        assert breakdown
        assert breakdown["s4"]["keyword"] == 1.0
        assert breakdown["s4"]["citation"] == 0.0

    def test_custom_ranking_weights_are_used(self):
        engine = build_engine(ranking_weights={"keyword": 1.0})
        assert engine.ranking_weights["keyword"] == 1.0
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence[0].node_id == "s4"
        breakdown = result.retrieval.ranking_breakdown
        assert breakdown["s4"]["rank"] == pytest.approx(1.0)

    def test_confidence_preserved_with_ranking_signals(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        assert result.confidence.score > 0.45
        assert result.confidence.label == "high"


class TestEvidenceDeduplication:
    """C3: deduplicate ranked evidence before evidence construction."""

    @staticmethod
    def _signals(ids):
        return {nid: _Signal(dense=0.1, graph=0.1, hierarchy=0.0) for nid in ids}

    def _multi_parent_graph(self) -> InMemoryGraph:
        g = InMemoryGraph()
        g.create_node("Document", "docA", {"title": "DOC A", "language": "en"})
        g.create_node("Chapter", "chA", {"title": "CH I", "hierarchy_level": 4})
        g.create_node("Chapter", "chB", {"title": "CH II", "hierarchy_level": 4})
        g.create_node(
            "Section",
            "secA",
            {
                "title": "Definitions",
                "numbering": "2",
                "text": "contract means an agreement enforceable by law.",
            },
        )
        g.create_edge("chA", "docA", "PART_OF")
        g.create_edge("chB", "docA", "PART_OF")
        g.create_edge("secA", "chA", "PART_OF")
        g.create_edge("secA", "chB", "PART_OF")
        return g

    # -- text similarity helper -------------------------------------------

    def test_text_similarity_identical(self):
        assert _text_similarity("alpha beta gamma", "alpha beta gamma") == 1.0

    def test_text_similarity_whitespace_insensitive(self):
        assert _text_similarity("alpha beta gamma", "alpha   beta\ngamma") == 1.0

    def test_text_similarity_disjoint_is_zero(self):
        assert _text_similarity("alpha beta", "zzz www") == 0.0
        assert _text_similarity("abc", "xyz") == 0.0

    def test_text_similarity_near_identical_above_threshold(self):
        a = "The contract must be performed in good faith by both parties."
        b = "The contract must be performed in good faith by both partie."
        assert _text_similarity(a, b) >= DEDUP_TEXT_SIMILARITY

    def test_text_similarity_clearly_different_below_threshold(self):
        a = "The contract must be performed in good faith by both parties."
        b = "Consideration must be lawful and given voluntarily at the time of agreement."
        assert _text_similarity(a, b) < DEDUP_TEXT_SIMILARITY

    def test_dedup_threshold_constant(self):
        assert DEDUP_TEXT_SIMILARITY == 0.95

    # -- duplicate criteria ------------------------------------------------

    def test_duplicate_node_ids_removed(self):
        engine = build_engine()
        parsed = parse_query("performance of contracts")
        ids = ["s4", "s4", "s1"]
        retained, details = engine._dedupe_evidence(ids, self._signals(ids), parsed)
        assert retained == ["s4", "s1"]
        assert len(details) == 1
        assert details[0]["duplicate_reason"] == "duplicate_node_id"
        assert details[0]["removed_node"] == "s4"
        assert details[0]["retained_node"] == "s4"

    def test_duplicate_hierarchy_paths_removed(self):
        graph = self._multi_parent_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        parsed = parse_query("contract definitions")
        ids = ["docA", "chA", "chB"]
        retained, details = engine._dedupe_evidence(ids, self._signals(ids), parsed)
        assert retained == ["docA"]
        assert len(details) == 2
        assert all(d["duplicate_reason"] == "duplicate_path" for d in details)
        assert all(d["retained_node"] == "docA" for d in details)
        assert {d["removed_node"] for d in details} == {"chA", "chB"}

    def test_near_identical_text_removed(self):
        g = InMemoryGraph()
        g.create_node(
            "Section",
            "sX",
            {
                "title": "X",
                "numbering": "10",
                "text": "The contract must be performed in good faith by both parties.",
            },
        )
        g.create_node(
            "Section",
            "sY",
            {
                "title": "Y",
                "numbering": "11",
                "text": "The contract must be performed in good faith by both partie.",
            },
        )
        engine = ExplainabilityEngine(g, vector_retriever=None)
        ids = ["sX", "sY"]
        retained, details = engine._dedupe_evidence(
            ids, self._signals(ids), parse_query("contract performance")
        )
        assert retained == ["sX"]
        assert len(details) == 1
        assert details[0]["duplicate_reason"] == "duplicate_text"
        assert details[0]["retained_node"] == "sX"
        assert details[0]["removed_node"] == "sY"

    # -- ordering + false positives ---------------------------------------

    def test_ordering_stability(self):
        engine = build_engine()
        parsed = parse_query("performance of contracts")
        ids = ["s4", "s1", "s4", "s2"]
        retained, details = engine._dedupe_evidence(ids, self._signals(ids), parsed)
        assert retained == ["s4", "s1", "s2"]
        assert len(details) == 1
        assert details[0]["removed_node"] == "s4"
        assert details[0]["retained_node"] == "s4"

    def test_no_false_positive_removals(self):
        engine = build_engine()
        parsed = parse_query("performance of contracts")
        ids = ["s4", "s1", "s2"]
        retained, details = engine._dedupe_evidence(ids, self._signals(ids), parsed)
        assert retained == ids
        assert details == []

    def test_subthreshold_text_similarity_retained(self):
        g = InMemoryGraph()
        g.create_node(
            "Section",
            "sX",
            {
                "title": "X",
                "numbering": "10",
                "text": "The contract must be performed in good faith by both parties.",
            },
        )
        g.create_node(
            "Section",
            "sY",
            {
                "title": "Y",
                "numbering": "11",
                "text": "Consideration must be lawful and given voluntarily by both parties.",
            },
        )
        engine = ExplainabilityEngine(g, vector_retriever=None)
        ids = ["sX", "sY"]
        retained, details = engine._dedupe_evidence(
            ids, self._signals(ids), parse_query("contract performance")
        )
        assert retained == ids
        assert details == []

    # -- end-to-end diagnostics -------------------------------------------

    def test_end_to_end_diagnostics_populated(self):
        graph = self._multi_parent_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = engine.explain("contract definitions", top_k=5)
        assert result.retrieval.duplicates_removed == 2
        assert len(result.retrieval.duplicate_details) == 2
        details = result.retrieval.duplicate_details
        assert all(d["duplicate_reason"] == "duplicate_path" for d in details)
        removed = {d["removed_node"] for d in details}
        retained = {d["retained_node"] for d in details}
        assert len(removed) == 2
        assert len(retained) == 1
        assert removed | retained == {"docA", "chA", "secA"}
        assert removed.isdisjoint(retained)
        assert len(result.evidence) == 1
        assert result.evidence[0].node_id == "secA"
        fusion = next(s for s in result.reasoning_chain if s.kind == "fusion")
        assert fusion.detail["duplicates_removed"] == 2

    def test_no_duplicates_reports_zero_and_empty(self):
        g = InMemoryGraph()
        g.create_node(
            "Section", "n1", {"title": "One", "numbering": "1",
                              "text": "first distinct text about performance"}
        )
        g.create_node(
            "Section", "n2", {"title": "Two", "numbering": "2",
                              "text": "second distinct text about performance"}
        )
        engine = ExplainabilityEngine(g, vector_retriever=None)
        result = engine.explain("performance", top_k=5)
        assert result.retrieval.duplicates_removed == 0
        assert result.retrieval.duplicate_details == []
        assert len(result.evidence) == 2

    def test_summary_serializes_new_fields(self):
        import dataclasses

        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        dumped = dataclasses.asdict(result.retrieval)
        assert "duplicates_removed" in dumped
        assert "duplicate_details" in dumped
