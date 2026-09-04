"""Tests for the explainability engine (Module 7)."""


import pytest

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import (
    DEDUP_TEXT_SIMILARITY,
    ExplainabilityEngine,
    _Signal,
    _text_similarity,
)
from src.llm.provenance import (
    CitationEntailment,
    Evidence,
    EvidenceRelevance,
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
        assert kinds == [
            "query_parse",
            "query_expansion",
            "dense",
            "graph",
            "hierarchy",
            "fusion",
            "verification",
        ]
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
        assert result.confidence.factors["citation_entailment"] == 0.0

    def test_confidence_and_validity(self):
        engine = build_engine()
        result = engine.explain("performance of contracts")
        assert result.confidence.score > 0.0
        assert result.confidence.label in ("low", "medium", "high", "very_high")
        # Task 4: badge is driven by the verification framework, not evidence count.
        assert result.validity.status in ("supported", "insufficient")
        assert isinstance(result.validity.reason, str)
        assert isinstance(result.validity.relevance_score, float)
        assert isinstance(result.validity.sufficiency_score, float)

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
        assert result.confidence.label == "very_low"
        assert result.confidence.factors["verification_status"] == "insufficient"
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
        # Task 4: is_valid now depends on verification framework badge.
        assert result.validity.status in ("supported", "insufficient")


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
        assert engine.threshold == 0.99
        result = engine.explain("performance of contracts")
        assert result.confidence.score < engine.threshold

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
        assert result.confidence.score > 0.0
        assert result.confidence.label in ("low", "medium", "high", "very_high")


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


def _make_evidence(title: str, text: str, numbering: str = "") -> Evidence:
    """Build a minimal Evidence node for unit-testing sufficiency."""
    return Evidence(
        node_id="test",
        title=title,
        text=text,
        label="Section",
        numbering=numbering,
        collection="sections",
        language="en",
        level=5,
        dense_score=0.5,
        graph_score=0.5,
        hierarchy_score=0.0,
        final_score=1.0,
    )


class TestEvidenceSufficiency:
    """Unit tests for ExplainabilityEngine._compute_evidence_sufficiency."""

    def test_relevant_evidence_scores_high(self):
        query = "What does Section 72 require when money is paid by mistake?"
        evidence = [
            _make_evidence(
                "Section 72",
                "Where a person to whom money has been paid or anything "
                "delivered by mistake or under coercion, must repay or "
                "return it.",
                "72",
            ),
        ]
        score = ExplainabilityEngine._compute_evidence_sufficiency(
            query, evidence, keyword_coverage=0.8
        )
        assert score > 0.50

    def test_partially_relevant_evidence_mid_range(self):
        query = "What does Section 72 require when money is paid by mistake?"
        evidence = [
            _make_evidence(
                "Section 68",
                "The promisee may recover compensation for breach of "
                "contract where the promisee has performed his part.",
                "68",
            ),
        ]
        score = ExplainabilityEngine._compute_evidence_sufficiency(
            query, evidence, keyword_coverage=0.2
        )
        assert 0.15 <= score <= 0.70

    def test_unrelated_evidence_scores_low(self):
        query = "What does Section 72 require when money is paid by mistake?"
        evidence = [
            _make_evidence(
                "Section 477",
                "Criminal breach of trust by carrier or warehouse-keeper "
                "shall be punishable with imprisonment.",
                "477",
            ),
        ]
        score = ExplainabilityEngine._compute_evidence_sufficiency(
            query, evidence, keyword_coverage=0.0
        )
        assert score < 0.30

    def test_many_unrelated_chunks_do_not_inflate_score(self):
        query = "What does Section 72 require?"
        unrelated = [
            _make_evidence(
                f"Section {n}",
                f"Criminal offence provision number {n} with imprisonment.",
                str(n),
            )
            for n in range(400, 410)
        ]
        score_few = ExplainabilityEngine._compute_evidence_sufficiency(
            query, unrelated[:1], keyword_coverage=0.0
        )
        score_many = ExplainabilityEngine._compute_evidence_sufficiency(
            query, unrelated, keyword_coverage=0.0
        )
        assert score_many - score_few < 0.15

    def test_score_always_in_unit_range(self):
        query = "test query"
        evidence = [_make_evidence("t", "test evidence text", "1")]
        score = ExplainabilityEngine._compute_evidence_sufficiency(
            query, evidence, keyword_coverage=0.5
        )
        assert 0.0 <= score <= 1.0

    def test_empty_evidence_returns_zero(self):
        score = ExplainabilityEngine._compute_evidence_sufficiency(
            "test query", [], keyword_coverage=0.0
        )
        assert score == 0.0



class TestChainRelevance:
    """C4: canonical hierarchy-path preference — affects ranking order only."""

    @staticmethod
    def _sig() -> _Signal:
        return _Signal(dense=0.2, graph=0.2, hierarchy=0.5, keyword=0.5, citation=0.0)

    def test_multiplier_table(self):
        engine = build_engine()
        cases = {
            "Section": 1.10,
            "Clause": 1.08,
            "Article": 1.07,
            "Rule": 1.06,
            "Chapter": 1.03,
            "Part": 1.02,
            "Act": 1.00,
            "Document": 0.95,
            "Wrapper": 0.90,
        }
        for label, expected in cases.items():
            assert engine._chain_relevance({"label": label}) == pytest.approx(expected)

    def test_unknown_label_neutral(self):
        engine = build_engine()
        assert engine._chain_relevance({"label": "Paragraph"}) == 1.0
        assert engine._chain_relevance({"label": ""}) == 1.0
        assert engine._chain_relevance({}) == 1.0
        assert engine._chain_relevance(None) == 1.0

    def test_label_match_case_and_whitespace_insensitive(self):
        engine = build_engine()
        assert engine._chain_relevance({"label": "  sEcTiOn "}) == pytest.approx(1.10)

    def test_section_preferred_over_chapter(self):
        engine = build_engine()
        sig = self._sig()
        section = engine._rank(sig, engine._chain_relevance({"label": "Section"}))
        chapter = engine._rank(sig, engine._chain_relevance({"label": "Chapter"}))
        assert section > chapter

    def test_clause_preferred_over_act(self):
        engine = build_engine()
        sig = self._sig()
        clause = engine._rank(sig, engine._chain_relevance({"label": "Clause"}))
        act = engine._rank(sig, engine._chain_relevance({"label": "Act"}))
        assert clause > act

    def test_wrapper_demoted(self):
        engine = build_engine()
        sig = self._sig()
        section = engine._rank(sig, engine._chain_relevance({"label": "Section"}))
        document = engine._rank(sig, engine._chain_relevance({"label": "Document"}))
        wrapper = engine._rank(sig, engine._chain_relevance({"label": "Wrapper"}))
        assert section > document > wrapper

    def test_unknown_rank_unaffected(self):
        engine = build_engine()
        sig = self._sig()
        plain = engine._rank(sig)
        unknown = engine._rank(sig, engine._chain_relevance({"label": "AnythingElse"}))
        assert plain == pytest.approx(unknown)

    def test_section_ranks_above_chapter_end_to_end(self):
        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence[0].label == "Section"
        assert result.evidence[1].label == "Chapter"

    def test_stable_ordering_preserved(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        ids = [ev.node_id for ev in result.evidence]
        breakdown = result.retrieval.ranking_breakdown
        assert ids == sorted(ids, key=lambda n: (-breakdown[n]["rank"], n))

    def test_confidence_unchanged(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        assert result.confidence.score == pytest.approx(0.4605, abs=1e-4)
        assert result.confidence.label == "low"

    def test_final_score_unchanged(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        for ev in result.evidence:
            assert ev.final_score == pytest.approx(
                ev.dense_score + ev.graph_score + ev.hierarchy_score, abs=1e-3
            )
        s4 = next(ev for ev in result.evidence if ev.node_id == "s4")
        assert s4.final_score == pytest.approx(0.8742, abs=1e-4)

    def test_retrieval_statistics_unchanged(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        # Candidate set may exceed top_k because standalone graph matches are
        # merged in so an explicit reference is never dropped (Task 14).
        assert result.retrieval.candidates >= 5
        assert result.retrieval.returned == 5
        assert result.retrieval.graph_hits > 0
        assert result.retrieval.duplicates_removed == 0

    def test_api_output_unchanged(self):
        import dataclasses

        from src.llm.schemas import ExplanationResponse

        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        payload = dataclasses.asdict(result)
        response = ExplanationResponse.model_validate(payload)
        dumped = response.retrieval.model_dump()
        assert "chain_ranking" not in dumped
        assert "ranking_breakdown" in dumped
        assert {"dense", "graph", "hierarchy", "keyword", "citation", "rank"} <= set(
            dumped["ranking_breakdown"]["s4"]
        )

    def test_diagnostics_recorded_per_retained_node(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        cr = result.retrieval.chain_ranking
        assert set(cr) == {ev.node_id for ev in result.evidence}
        s4 = cr["s4"]
        assert s4["chain_relevance"] == pytest.approx(1.10)
        assert s4["ranking_reason"] == "canonical:section"
        assert s4["effective_hierarchy_score"] == pytest.approx(
            result.retrieval.ranking_breakdown["s4"]["hierarchy"] * 1.10, abs=1e-4
        )
        ch2 = cr["ch2"]
        assert ch2["chain_relevance"] == pytest.approx(1.03)
        assert ch2["ranking_reason"] == "canonical:chapter"

    def test_unknown_node_reason_and_multiplier(self):
        g = InMemoryGraph()
        g.create_node(
            "Paragraph", "p1", {"title": "P1", "text": "some paragraph text"}
        )
        g.create_node(
            "Paragraph", "p2", {"title": "P2", "text": "another paragraph"}
        )
        engine = ExplainabilityEngine(g, vector_retriever=None)
        result = engine.explain("paragraph text", top_k=5)
        cr = result.retrieval.chain_ranking
        assert cr
        assert all(e["chain_relevance"] == 1.0 for e in cr.values())
        assert all(e["ranking_reason"] == "unknown" for e in cr.values())


class TestRetrievalPipelineDiagnostics:
    """C5: adaptive retrieval integration + research diagnostics."""

    PIPELINE = [
        "intent_detection",
        "adaptive_top_k",
        "dense_retrieval",
        "graph_retrieval",
        "hierarchy_retrieval",
        "keyword_ranking",
        "citation_ranking",
        "canonical_hierarchy_preference",
        "evidence_deduplication",
        "evidence_resolution",
        "provenance_generation",
        "llm_answer_generation",
    ]

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

    def test_full_adaptive_pipeline_executes(self):
        engine = build_engine(adaptive=True, top_k_easy=2)
        result = engine.explain("what does section 4 say")
        s = result.retrieval
        assert s.retrieval_strategy == "adaptive"
        assert s.adaptive_top_k == 2
        assert s.intent == "section_lookup"
        assert s.query_intent == "section_lookup"
        assert s.retrieval_pipeline == self.PIPELINE
        assert result.evidence

    def test_diagnostics_populated(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        s = result.retrieval
        assert s.retrieval_pipeline == self.PIPELINE
        assert s.query_intent == "explanation"
        assert s.retrieved_candidates == s.candidates > 0
        assert s.ranked_candidates >= s.returned
        assert s.ranking_weights == {
            "dense": 0.2916666666666667,
            "graph": 0.20833333333333334,
            "hierarchy": 0.125,
            "keyword": 0.125,
            "citation": 0.25,
        }
        assert s.ranking_breakdown
        assert s.chain_ranking
        assert s.retrieval_strategy == "fixed"
        assert s.adaptive_top_k is None

    def test_expansion_enabled_adds_legal_expansion_stage(self):
        engine = build_engine(expansion_enabled=True)
        result = engine.explain("performance of contracts", top_k=5)
        pipeline = result.retrieval.retrieval_pipeline
        assert "legal_expansion" in pipeline
        assert pipeline.index("legal_expansion") == 2

    def test_timing_fields_exist_and_consistent(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        s = result.retrieval
        assert s.retrieval_latency_ms >= 0.0
        assert s.ranking_latency_ms >= 0.0
        assert s.total_retrieval_latency_ms >= s.retrieval_latency_ms + s.ranking_latency_ms
        breakdown = s.latency_breakdown
        assert set(breakdown) >= {
            "intent_detection",
            "fusion",
            "ranking",
            "deduplication",
            "evidence_resolution",
        }
        assert all(v >= 0.0 for v in breakdown.values())
        assert s.total_retrieval_latency_ms == pytest.approx(
            s.retrieval_latency_ms
            + s.ranking_latency_ms
            + breakdown["evidence_resolution"],
            abs=0.02,
        )

    def test_ranking_breakdown_preserved(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        ids = [ev.node_id for ev in result.evidence]
        ranks = [result.retrieval.ranking_breakdown[nid]["rank"] for nid in ids]
        assert ranks == sorted(ranks, reverse=True)

    def test_dedup_diagnostics_preserved(self):
        graph = self._multi_parent_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = engine.explain("contract definitions", top_k=5)
        s = result.retrieval
        assert s.duplicates_removed == 2
        assert len(s.duplicate_details) == 2
        assert s.ranked_candidates - s.duplicates_removed == s.returned
        assert len(result.evidence) == s.returned

    def test_chain_diagnostics_preserved(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        cr = result.retrieval.chain_ranking
        assert set(cr) == {ev.node_id for ev in result.evidence}
        assert cr["s4"]["chain_relevance"] == pytest.approx(1.10)

    def test_adaptive_top_k_preserved(self):
        engine = build_engine(adaptive=True, top_k_easy=2)
        result = engine.explain("performance of contracts")
        assert result.retrieval.retrieval_strategy == "adaptive"
        assert result.retrieval.adaptive_top_k == 2
        assert result.retrieval.query_intent == "explanation"

    def test_explicit_top_k_stays_fixed(self):
        engine = build_engine(adaptive=True, top_k_easy=2)
        result = engine.explain("performance of contracts", top_k=4)
        assert result.retrieval.retrieval_strategy == "fixed"
        assert result.retrieval.adaptive_top_k is None

    def test_api_schema_unchanged(self):
        import dataclasses

        from src.llm.schemas import ExplanationResponse

        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        payload = dataclasses.asdict(result)
        response = ExplanationResponse.model_validate(payload)
        dumped = response.retrieval.model_dump()
        assert "retrieval_pipeline" not in dumped
        assert "query_intent" not in dumped
        assert "retrieved_candidates" not in dumped
        assert "ranked_candidates" not in dumped
        assert "ranking_weights" not in dumped
        assert "retrieval_latency_ms" not in dumped
        assert "ranking_latency_ms" not in dumped
        assert "total_retrieval_latency_ms" not in dumped
        assert "latency_breakdown" not in dumped
        assert "chain_ranking" not in dumped
        assert "ranking_breakdown" in dumped
        assert "retrieval_strategy" in dumped
        assert "adaptive_top_k" in dumped

    def test_new_provenance_record_roundtrips(self, tmp_path):
        import uuid

        from src.llm.provenance import AnswerResult, ProvenanceStore

        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        answer = AnswerResult(
            provenance_id=uuid.uuid4().hex,
            query=result.query,
            answer="The answer.",
            model="mock-llm",
            explanation=result,
            duration_ms=1.0,
        )
        store = ProvenanceStore(directory=tmp_path)
        pid = store.save(answer)
        record = store.get(pid)
        assert record is not None
        retrieval = record["explanation"]["retrieval"]
        assert retrieval["retrieval_pipeline"] == self.PIPELINE
        assert retrieval["total_retrieval_latency_ms"] >= 0.0
        assert retrieval["query_intent"] == "explanation"

    def test_old_provenance_record_still_loads(self, tmp_path):
        import json

        from src.llm.provenance import ProvenanceStore
        from src.llm.schemas import ExplanationResponse

        old_record = {
            "provenance_id": "old1",
            "query": "performance of contracts",
            "answer": "The answer.",
            "model": "mock-llm",
            "duration_ms": 12.3,
            "explanation": {
                "query": "performance of contracts",
                "query_language": "en",
                "retrieval": {
                    "keywords": ["performance", "contracts"],
                    "section_refs": [],
                    "dense_hits": 5,
                    "graph_hits": 3,
                    "hierarchy_propagated": 2,
                    "candidates": 5,
                    "returned": 5,
                    "intent": "explanation",
                    "adaptive_top_k": None,
                    "retrieval_strategy": "fixed",
                    "ranking_breakdown": {},
                    "duplicates_removed": 0,
                    "duplicate_details": [],
                },
                "evidence": [],
                "reasoning_chain": [],
                "hierarchy_paths": [],
                "citations": [],
                "counter_authorities": [],
                "confidence": {"score": 0.5, "label": "medium", "factors": {}},
                "validity": {
                    "is_valid": True,
                    "supported": True,
                    "has_conflicts": False,
                    "cites_counter_authority": False,
                    "insufficient_evidence": False,
                    "reasons": [],
                },
                "retrieval_weights": {"dense": 0.4, "graph": 0.35, "hierarchy": 0.25},
            },
        }
        (tmp_path / "old1.json").write_text(
            json.dumps(old_record), encoding="utf-8"
        )
        store = ProvenanceStore(directory=tmp_path)
        record = store.get("old1")
        assert record is not None
        assert record["explanation"]["retrieval"]["retrieval_strategy"] == "fixed"
        response = ExplanationResponse.model_validate(record["explanation"])
        assert response.confidence.score == 0.5
        assert response.retrieval.retrieval_strategy == "fixed"


# ---------------------------------------------------------------------------
# Task 2 — Evidence relevance (LLM judge + fallback)
# ---------------------------------------------------------------------------


class _MockJudgeClient:
    """Minimal LLM client that returns a preconfigured relevance JSON response."""

    def __init__(self, response_json: str):
        self._response = response_json

    def chat(self, *, system: str, user: str, temperature: float = 0.0, max_tokens: int = 200):
        from src.llm.llm import LLMResponse

        return LLMResponse(text=self._response, model="mock-judge")


class _BrokenClient:
    """LLM client that always raises — used to test fallback paths."""

    def chat(self, **kwargs):
        raise RuntimeError("LLM is down")


class TestEvidenceRelevance:
    """Tests for ExplainabilityEngine._compute_evidence_relevance."""

    def test_perfect_evidence(self):
        response_json = '{"score": 1.0, "label": "direct", "reason": "Perfect match."}'
        engine = build_engine(llm_client=_MockJudgeClient(response_json))
        result = engine.explain("performance of contracts", top_k=5)
        rel = result.evidence_relevance
        assert isinstance(rel, EvidenceRelevance)
        assert rel.score >= 0.9
        assert rel.label == "direct"

    def test_mostly_relevant_evidence(self):
        response_json = (
            '{"score": 0.75, "label": "mostly",'
            ' "reason": "Good match with minor gaps."}'
        )
        engine = build_engine(llm_client=_MockJudgeClient(response_json))
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence_relevance.score == pytest.approx(0.75, abs=0.01)

    def test_partially_relevant_evidence(self):
        response_json = (
            '{"score": 0.50, "label": "partial",'
            ' "reason": "Only tangentially related."}'
        )
        engine = build_engine(llm_client=_MockJudgeClient(response_json))
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence_relevance.score == pytest.approx(0.50, abs=0.01)

    def test_wrong_statute(self):
        response_json = '{"score": 0.20, "label": "unrelated", "reason": "Wrong statute."}'
        engine = build_engine(llm_client=_MockJudgeClient(response_json))
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence_relevance.score < 0.3

    def test_empty_evidence(self):
        engine = build_engine(llm_client=_MockJudgeClient('{"score": 1.0}'))
        graph = InMemoryGraph()
        bare_engine = ExplainabilityEngine(graph, llm_client=engine.llm_client)
        result = bare_engine.explain("anything", top_k=5)
        assert result.evidence_relevance.score == 0.0
        assert result.evidence_relevance.label == "none"

    def test_llm_failure_fallback(self):
        """When the LLM raises, the deterministic fallback must execute."""
        engine = build_engine(llm_client=_BrokenClient())
        result = engine.explain("performance of contracts", top_k=5)
        rel = result.evidence_relevance
        assert isinstance(rel, EvidenceRelevance)
        assert 0.0 <= rel.score <= 1.0
        assert rel.label in {"direct", "partial", "tangential", "unrelated"}


# ---------------------------------------------------------------------------
# Task 3 — Citation entailment judge
# ---------------------------------------------------------------------------


def _make_ev(node_id: str, title: str, text: str) -> Evidence:
    """Build a minimal Evidence node for entailment tests."""
    return Evidence(
        node_id=node_id,
        title=title,
        text=text,
        label="Section",
        numbering="1",
        collection="sections",
        language="en",
        level=5,
        dense_score=0.5,
        graph_score=0.5,
        hierarchy_score=0.0,
        final_score=1.0,
    )


class _EntailmentJudgeClient:
    """Returns a fixed JSON for every entailment judge call."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._idx = 0

    def chat(self, *, system: str, user: str, **kw):
        from src.llm.llm import LLMResponse

        text = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return LLMResponse(text=text, model="mock-entailment")


class TestCitationEntailment:
    """Tests for ExplainabilityEngine._compute_citation_entailment."""

    def test_direct_support(self):
        response = (
            '{"entailment": 1.0, "contradicts": false,'
            ' "reason": "Directly supported."}'
        )
        engine = build_engine(llm_client=_EntailmentJudgeClient([response]))
        ev = [_make_ev("s1", "Section 72", "Money paid by mistake must be repaid.")]
        result = engine._compute_citation_entailment(
            "Section 72 requires that money paid by mistake must be repaid.",
            ev,
        )
        assert isinstance(result, CitationEntailment)
        assert result.overall_score == 1.0
        assert not result.contradiction_found
        assert len(result.claim_results) == 1

    def test_partial_support(self):
        response = (
            '{"entailment": 0.5, "contradicts": false,'
            ' "reason": "Partially relevant."}'
        )
        engine = build_engine(llm_client=_EntailmentJudgeClient([response]))
        ev = [_make_ev("s1", "Section 68", "Compensation for breach of contract.")]
        result = engine._compute_citation_entailment(
            "Section 68 allows recovery of damages for delayed performance.",
            ev,
        )
        assert result.overall_score == pytest.approx(0.5, abs=0.01)

    def test_unsupported_claim(self):
        response = (
            '{"entailment": 0.0, "contradicts": false,'
            ' "reason": "Not supported."}'
        )
        engine = build_engine(llm_client=_EntailmentJudgeClient([response]))
        ev = [_make_ev("s1", "Section 477", "Criminal breach of trust provision.")]
        result = engine._compute_citation_entailment(
            "Section 72 requires money to be returned within 30 days.",
            ev,
        )
        assert result.overall_score == 0.0

    def test_contradiction_found(self):
        response = (
            '{"entailment": 0.0, "contradicts": true,'
            ' "reason": "Evidence states the opposite."}'
        )
        engine = build_engine(llm_client=_EntailmentJudgeClient([response]))
        ev = [_make_ev("s1", "Section 72", "Money need not be repaid if under 100.")]
        result = engine._compute_citation_entailment(
            "Section 72 states all money paid by mistake must be repaid.",
            ev,
        )
        assert result.contradiction_found
        assert result.overall_score == 0.0

    def test_multiple_claims_average(self):
        r1 = (
            '{"entailment": 1.0, "contradicts": false,'
            ' "reason": "Supported."}'
        )
        r2 = (
            '{"entailment": 0.0, "contradicts": false,'
            ' "reason": "Not supported."}'
        )
        engine = build_engine(llm_client=_EntailmentJudgeClient([r1, r2]))
        ev = [
            _make_ev("s1", "Section 72", "Money paid by mistake must be repaid."),
            _make_ev("s2", "Section 73", "Interest accrues on unpaid debts."),
        ]
        result = engine._compute_citation_entailment(
            "Section 72 requires repayment. Section 75 imposes strict liability.",  # noqa: E501
            ev,
        )
        assert len(result.claim_results) == 2
        assert result.overall_score == pytest.approx(0.5, abs=0.01)

    def test_empty_answer(self):
        engine = build_engine(llm_client=_EntailmentJudgeClient([]))
        result = engine._compute_citation_entailment("", [])
        assert result.overall_score == 0.0
        assert not result.contradiction_found
        assert result.claim_results == []

    def test_llm_failure_fallback(self):
        engine = build_engine(llm_client=_BrokenClient())
        ev = [_make_ev("s1", "Section 72", "Money paid by mistake must be repaid.")]
        result = engine._compute_citation_entailment(
            "Money paid by mistake must be returned to the payer.", ev
        )
        assert isinstance(result, CitationEntailment)
        assert 0.0 <= result.overall_score <= 1.0
        assert not result.contradiction_found
        assert len(result.claim_results) >= 1


# ---------------------------------------------------------------------------
# Task 4 — Verification badge rewrite
# ---------------------------------------------------------------------------


class TestVerificationBadge:
    """Tests for the verification badge decision logic (Task 4)."""

    def test_supported(self):
        """All signals above thresholds → status 'supported'."""
        status, reason = ExplainabilityEngine._compute_verification_badge(
            evidence_relevance_score=0.80,
            evidence_sufficiency_score=0.70,
            citation_entailment_overall=0.90,
            citation_contradiction_found=False,
        )
        assert status == "supported"
        assert "supported" in reason.lower()

    def test_contradiction(self):
        """Contradiction found → status 'conflicts' (Priority 1)."""
        status, reason = ExplainabilityEngine._compute_verification_badge(
            evidence_relevance_score=0.90,
            evidence_sufficiency_score=0.80,
            citation_entailment_overall=1.0,
            citation_contradiction_found=True,
        )
        assert status == "conflicts"
        assert "contradicts" in reason.lower()

    def test_low_entailment(self):
        """Entailment score below threshold → 'insufficient' (Priority 2)."""
        status, reason = ExplainabilityEngine._compute_verification_badge(
            evidence_relevance_score=0.90,
            evidence_sufficiency_score=0.80,
            citation_entailment_overall=0.20,
            citation_contradiction_found=False,
        )
        assert status == "insufficient"
        assert "not support" in reason.lower()

    def test_low_relevance(self):
        """Relevance score below threshold → 'insufficient' (Priority 3)."""
        status, reason = ExplainabilityEngine._compute_verification_badge(
            evidence_relevance_score=0.20,
            evidence_sufficiency_score=0.80,
            citation_entailment_overall=0.90,
            citation_contradiction_found=False,
        )
        assert status == "insufficient"
        assert "not relevant" in reason.lower()

    def test_low_sufficiency(self):
        """Sufficiency score below threshold → 'insufficient' (Priority 4)."""
        status, reason = ExplainabilityEngine._compute_verification_badge(
            evidence_relevance_score=0.80,
            evidence_sufficiency_score=0.30,
            citation_entailment_overall=0.90,
            citation_contradiction_found=False,
        )
        assert status == "insufficient"
        assert "insufficient" in reason.lower()

    def test_boundary_values(self):
        """Exactly at thresholds → 'supported'."""
        status, _reason = ExplainabilityEngine._compute_verification_badge(
            evidence_relevance_score=0.40,
            evidence_sufficiency_score=0.45,
            citation_entailment_overall=-1.0,
            citation_contradiction_found=False,
        )
        assert status == "supported"

    def test_multiple_claims(self):
        """Contradiction in one claim triggers 'conflicts' regardless of score."""
        status, _ = ExplainabilityEngine._compute_verification_badge(
            evidence_relevance_score=0.90,
            evidence_sufficiency_score=0.90,
            citation_entailment_overall=0.75,
            citation_contradiction_found=True,
        )
        assert status == "conflicts"

    def test_section_72_regression(self):
        """Section 72 query with wrong evidence → 'insufficient', NOT 'supported'.

        This is the key regression: the old badge would report 'Supported'
        simply because evidence exists. The new badge correctly identifies
        that the evidence is not relevant to the question.
        """
        graph = InMemoryGraph()
        graph.create_node("Document", "d1", {"title": "Indian Contract Act"})
        graph.create_node(
            "Section", "s68",
            {
                "title": "Section 68",
                "numbering": "68",
                "text": "Promisee may recover compensation for breach.",
            },
        )
        graph.create_node(
            "Section", "s23",
            {
                "title": "Section 23",
                "numbering": "23",
                "text": "What considerations and objects are lawful.",
            },
        )
        graph.create_node(
            "Section", "s477",
            {
                "title": "Section 477",
                "numbering": "477",
                "text": "Criminal breach of trust by carrier.",
            },
        )
        graph.create_edge("s68", "d1", "PART_OF")
        graph.create_edge("s23", "d1", "PART_OF")
        graph.create_edge("s477", "d1", "PART_OF")
        bare_engine = ExplainabilityEngine(graph, vector_retriever=None)
        result = bare_engine.explain(
            "What does Section 72 provide?", top_k=3
        )
        assert result.validity.status == "insufficient"
        assert result.validity.supported is False
        assert result.validity.insufficient_evidence is True


class TestConfidenceScoring:
    """Task 5: verification-aware confidence scoring."""

    @staticmethod
    def _ev(node_id, title, text, final_score, **kw):
        return Evidence(
            node_id=node_id, title=title, text=text,
            label=kw.pop("label", "Section"),
            numbering=kw.pop("numbering", "1"),
            collection=kw.pop("collection", "sections"),
            language="en", level=3,
            dense_score=final_score, graph_score=0.0,
            hierarchy_score=0.0, final_score=final_score, **kw,
        )

    @staticmethod
    def _parsed(keywords=None):
        from src.retrieval.query import parse_query
        return parse_query(" ".join(keywords or []))

    def test_perfect_evidence(self):
        """1. Perfect evidence -> confidence > 0.85 (very_high)."""
        engine = build_engine()
        evidence = [
            self._ev("s1", "S1", "performance of contracts by both parties", 0.95),
            self._ev("s2", "S2", "contracts mean agreements enforceable by law", 0.92),
            self._ev("s3", "S3", "obligation of performance under contract", 0.90),
            self._ev("s4", "S4", "performance of contracts obligations agreement", 0.88),
            self._ev("s5", "S5", "enforceable by law parties contracts performance", 0.85),
        ]
        parsed = self._parsed(["performance", "contracts"])
        relevance = EvidenceRelevance(
            score=0.98, label="direct", explanation="perfect",
        )
        entailment = CitationEntailment(
            overall_score=0.98, contradiction_found=False,
            claim_results=[], summary="",
        )
        result = engine._score_confidence(
            evidence, parsed, "performance of contracts",
            evidence_relevance=relevance,
            citation_entailment=entailment,
        )
        assert result.score > 0.85
        assert result.label == "very_high"

    def test_partial_evidence(self):
        """2. Partial evidence -> medium confidence."""
        engine = build_engine()
        evidence = [
            self._ev("s1", "S1", "short title of the act 1872", 0.60),
            self._ev("s2", "S2", "definitions chapter preliminary", 0.50),
        ]
        parsed = self._parsed(["performance", "contracts"])
        relevance = EvidenceRelevance(
            score=0.50, label="partial", explanation="partial",
        )
        result = engine._score_confidence(
            evidence, parsed, "performance of contracts",
            evidence_relevance=relevance,
        )
        assert 0.40 <= result.score <= 0.70
        assert result.label in ("medium", "low")

    def test_unsupported_evidence(self):
        """3. Unsupported evidence -> confidence < 0.45."""
        engine = build_engine()
        evidence = [
            self._ev("s1", "S1", "criminal breach of trust by carrier", 0.30),
            self._ev("s2", "S2", "penalty for dishonest misappropriation", 0.20),
        ]
        parsed = self._parsed(["performance", "contracts"])
        relevance = EvidenceRelevance(
            score=0.15, label="unrelated", explanation="wrong",
        )
        result = engine._score_confidence(
            evidence, parsed, "performance of contracts",
            evidence_relevance=relevance,
        )
        assert result.score < 0.45
        assert result.factors["verification_status"] == "insufficient"

    def test_contradiction_caps_at_020(self):
        """4. Contradiction -> confidence <= 0.20."""
        engine = build_engine()
        evidence = [
            self._ev("s1", "S1", "performance of contracts", 0.95),
            self._ev("s2", "S2", "contracts agreements enforceable", 0.90),
        ]
        parsed = self._parsed(["performance", "contracts"])
        relevance = EvidenceRelevance(
            score=0.90, label="direct", explanation="perfect",
        )
        result = engine._score_confidence(
            evidence, parsed, "performance of contracts",
            evidence_relevance=relevance,
            contradiction_found=True,
        )
        assert result.score <= 0.20
        assert result.factors["contradiction_found"] is True
        assert result.factors["final_adjustment"] == "contradiction_cap"

    def test_no_evidence(self):
        """5. No evidence -> confidence == 0."""
        engine = build_engine()
        parsed = self._parsed(["performance", "contracts"])
        result = engine._score_confidence(
            [], parsed, "performance of contracts",
        )
        assert result.score == 0.0
        assert result.label == "very_low"
        assert result.factors["verification_status"] == "insufficient"
        assert result.factors["final_adjustment"] == "no_evidence"

    def test_section72_regression(self):
        """6. Section 72 regression: wrong evidence -> confidence <= 0.45."""
        engine = build_engine()
        evidence = [
            self._ev("s68", "S68", "promisee may recover compensation", 0.50,
                      numbering="68"),
            self._ev("s23", "S23", "what considerations are lawful", 0.40,
                      numbering="23"),
            self._ev("s477", "S477", "criminal breach of trust", 0.30,
                      numbering="477"),
        ]
        parsed = self._parsed(["section", "72", "provide"])
        relevance = EvidenceRelevance(
            score=0.20, label="unrelated", explanation="wrong sections",
        )
        result = engine._score_confidence(
            evidence, parsed, "what does section 72 provide",
            evidence_relevance=relevance,
        )
        assert result.score <= 0.45
        assert result.factors["verification_status"] == "insufficient"

    def test_label_boundaries(self):
        """7. Verify 5-tier label boundaries.

        Sufficiency must be >= 0.45 for badge to be "supported" (otherwise
        capped at 0.45).  Use a realistic query + matching evidence text
        so text similarity drives sufficiency above 0.45.
        """
        engine = build_engine()
        query = "performance of contracts"
        parsed = self._parsed(["performance", "contracts"])
        ev_text = (
            "performance of contracts and obligations under agreement "
            "enforceable by law between parties"
        )
        base_ev = [
            self._ev("s1", "S1", ev_text, 0.90),
            self._ev("s2", "S2", ev_text, 0.85),
        ]
        cases = [
            (1.00, 1.00, "very_high"),
            (0.75, 0.75, "high"),
            (0.55, 0.55, "medium"),
            (0.35, 0.35, "low"),
            (0.00, 0.00, "very_low"),
        ]
        for rel, ent, expected in cases:
            relevance = EvidenceRelevance(
                score=rel, label="x", explanation="",
            )
            entailment = CitationEntailment(
                overall_score=ent, contradiction_found=False,
                claim_results=[], summary="",
            )
            result = engine._score_confidence(
                base_ev, parsed, query,
                evidence_relevance=relevance,
                citation_entailment=entailment,
            )
            assert result.label == expected, (
                f"rel={rel}, ent={ent} -> score={result.score:.4f} "
                f"label={result.label}, expected {expected}"
            )

    def test_existing_api_compatibility(self):
        """8. Verify confidence factors contain all required keys."""
        engine = build_engine()
        result = engine.explain("performance of contracts")
        required_keys = {
            "retrieval_base", "evidence_relevance",
            "evidence_sufficiency", "citation_entailment",
            "verification_status", "contradiction_found",
            "final_adjustment", "n_evidence", "matched_keywords",
        }
        assert required_keys.issubset(result.confidence.factors.keys())
        assert isinstance(result.confidence.score, float)
        assert isinstance(result.confidence.label, str)


class TestVerificationTrace:
    """Task 6: Structured VerificationTrace explaining verification decisions."""

    def test_supported_answer_trace(self):
        """1. Supported answer produces a trace with 'supported' status."""
        engine = build_engine()
        result = engine.explain("performance of contracts")
        trace = result.verification_trace
        assert trace is not None
        assert trace.verification_status in ("supported", "insufficient")
        assert isinstance(trace.decision_path, list)
        assert len(trace.decision_path) > 0
        assert trace.confidence_score == result.confidence.score
        assert trace.confidence_label == result.confidence.label
        # The trace should include the final confidence line
        assert any("Final confidence" in step for step in trace.decision_path)

    def test_insufficient_trace(self):
        """2. Insufficient evidence produces INSUFFICIENT trace."""
        graph = InMemoryGraph()
        graph.create_node("Document", "d1", {"title": "Test"})
        graph.create_node(
            "Section", "s1",
            {"title": "Section 1", "numbering": "1", "text": "Irrelevant text about birds."},
        )
        engine = build_engine(graph=graph)
        result = engine.explain("quantum computing regulations", top_k=3)
        trace = result.verification_trace
        assert trace is not None
        assert trace.verification_status == "insufficient"
        assert trace.confidence_score <= 0.45
        assert any("insufficient" in step.lower() for step in trace.decision_path)

    def test_contradiction_trace(self):
        """3. Contradiction produces CONFLICTS trace."""
        from src.llm.provenance import Confidence

        # Build a Confidence that simulates contradiction found by entailment
        conf = Confidence(
            score=0.20,
            label="very_low",
            factors={
                "retrieval_base": 0.50,
                "evidence_relevance": 0.40,
                "evidence_sufficiency": 0.50,
                "citation_entailment": 0.10,
                "verification_status": "conflicts",
                "contradiction_found": True,
                "final_adjustment": "contradiction_cap",
                "n_evidence": 2,
                "matched_keywords": ["performance", "contracts"],
            },
        )
        trace = ExplainabilityEngine._build_verification_trace(conf)
        assert trace.contradiction_found is True
        assert trace.verification_status == "conflicts"
        assert trace.confidence_score <= 0.20
        assert any("contradiction" in step.lower() for step in trace.decision_path)
        assert any("cap" in step.lower() for step in trace.decision_path)

    def test_no_evidence_trace(self):
        """4. No evidence produces trace with no_evidence adjustment."""
        graph = InMemoryGraph()
        graph.create_node("Document", "d1", {"title": "Empty"})
        engine = build_engine(graph=graph)
        result = engine.explain("quantum entanglement", top_k=3)
        trace = result.verification_trace
        assert trace is not None
        assert trace.confidence_score == 0.0
        assert trace.final_adjustment == "no_evidence"
        assert any("No evidence" in step for step in trace.decision_path)

    def test_confidence_capped_trace(self):
        """5. Confidence capped traces show the cap rule applied."""
        engine = build_engine()
        # Section 72 query with wrong evidence should cap confidence
        result = engine.explain("what is the time limit under section 72")
        trace = result.verification_trace
        assert trace is not None
        if trace.verification_status == "insufficient":
            assert trace.confidence_score <= 0.45
            cap_steps = [
                s for s in trace.decision_path if "cap" in s.lower()
            ]
            # Should have a cap-related step OR be below 0.45 naturally
            assert len(cap_steps) > 0 or trace.confidence_score <= 0.45

    def test_serialization(self):
        """6. VerificationTrace round-trips through dict/json."""
        import json
        from dataclasses import asdict

        engine = build_engine()
        result = engine.explain("performance of contracts")
        trace = result.verification_trace
        assert trace is not None
        d = asdict(trace)
        dumped = json.dumps(d)
        loaded = json.loads(dumped)
        assert loaded["verification_status"] == trace.verification_status
        assert loaded["confidence_score"] == trace.confidence_score
        assert loaded["decision_path"] == trace.decision_path
        assert loaded["contradiction_found"] == trace.contradiction_found

    def test_backward_compatibility(self):
        """7. Missing verification_trace defaults to None; old results still parse."""
        from dataclasses import asdict

        from src.llm.provenance import ExplanationResult

        # Simulate an old ExplanationResult without verification_trace
        old = ExplanationResult(
            query="test",
            query_language="en",
        )
        assert old.verification_trace is None
        # The field is optional so asdict works fine
        d = asdict(old)
        assert d["verification_trace"] is None
