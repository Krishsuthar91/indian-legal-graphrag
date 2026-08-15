"""Integration tests for Phase 4 legal query expansion end-to-end.

Shows that a natural-language "threat" query retrieves the coercion-family
sections (s. 14 free consent, s. 15 coercion, s. 19 voidability) ONLY when
expansion is enabled, while the pipeline otherwise behaves exactly as before.

Two complementary angles:
- graph-only engines (``vector_retriever=None``) give a deterministic,
  embedding-noise-free control proving the gating semantics of the feature;
- the full pipeline (deterministic vector retriever + HHGR) proves the feature
  integrates end to end with dense + graph retrieval.

The corpus-aware contract is also covered: on the real ICA 1872 corpus (which
does NOT contain sections 14/15/16/17/18/25), expansion injects only the
references that exist (e.g. "section 2") and records the rest as omitted, so
the engine never steers retrieval toward sections the index cannot return.
"""

import json
from pathlib import Path

from src.config.settings import Settings
from src.knowledge_graph.importer import import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from tests.qa_helpers import build_engine

THREAT_QUERY = "A signs under threat. Is the contract valid?"

COERCION_SECTIONS = {"s14", "s15", "s19"}

REAL_CORPUS = Path(__file__).resolve().parents[1] / "data" / "hierarchy" / "0d1934142f67c5f5.json"


def _real_corpus_graph() -> InMemoryGraph:
    g = InMemoryGraph()
    import_hierarchy_json(g, REAL_CORPUS)
    return g


def _threat_graph() -> InMemoryGraph:
    """Contract Act graph with a coercion chapter isolated from the contract
    chapter. The coercion sections share no lexical tokens with the unexpanded
    query, so without expansion (and its concept terms + verified section
    references) they are never retrieved."""
    g = InMemoryGraph()
    g.create_node("Document", "docT", {"title": "EXPLAINTEST", "language": "en"})
    g.create_node("Chapter", "chA", {
        "title": "CHAPTER II", "text": "Of Contracts", "hierarchy_level": 4,
    })
    g.create_node("Chapter", "chC", {
        "title": "CHAPTER IV", "text": "Consent and coercion", "hierarchy_level": 4,
    })
    g.create_node("Section", "s2", {
        "title": "Definitions", "numbering": "2", "hierarchy_level": 5,
        "text": "Contract means an agreement enforceable by law.",
    })
    g.create_node("Section", "s3", {
        "title": "Communication", "numbering": "3", "hierarchy_level": 5,
        "text": "Communication of a contract is complete when it comes to knowledge.",
    })
    g.create_node("Section", "s4", {
        "title": "Performance", "numbering": "4", "hierarchy_level": 5,
        "text": "Performance under a valid contract is a duty of the promisor.",
    })
    g.create_node("Section", "s5", {
        "title": "Writing", "numbering": "5", "hierarchy_level": 5,
        "text": "A contract may be valid without writing.",
    })
    g.create_node("Section", "s10", {
        "title": "What agreements are contracts", "numbering": "10", "hierarchy_level": 5,
        "text": "All agreements are contracts if made by free consent of parties.",
    })
    g.create_node("Section", "s12", {
        "title": "Sound mind", "numbering": "12", "hierarchy_level": 5,
        "text": "A person is of sound mind for contracting if capable of understanding it.",
    })
    g.create_node("Section", "s14", {
        "title": "Free consent", "numbering": "14", "hierarchy_level": 5,
        "text": "Consent free when not caused by coercion, undue influence, fraud, "
               "misrepresentation, or mistake.",
    })
    g.create_node("Section", "s15", {
        "title": "Coercion", "numbering": "15", "hierarchy_level": 5,
        "text": "Committing coercion as permitted in the Indian Penal Code renders "
               "consent voidable.",
    })
    g.create_node("Section", "s19", {
        "title": "Voidability", "numbering": "19", "hierarchy_level": 5,
        "text": "Consent caused by coercion voidable at option of coerced party.",
    })
    for chapter, sections in (("chA", ("s2", "s3", "s4", "s5", "s10", "s12")),
                              ("chC", ("s14", "s15", "s19"))):
        g.create_edge(chapter, "docT", "PART_OF")
        for section in sections:
            g.create_edge(section, chapter, "PART_OF")
    return g


def _evidence_ids(result) -> set[str]:
    return {ev.node_id for ev in result.evidence}


class TestGraphOnlySemantics:
    """Deterministic control: with graph retrieval only, expansion is what
    surfaces the coercion sections — nothing else can."""

    def test_coercion_sections_missing_when_disabled(self):
        graph = _threat_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None, expansion_enabled=False)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert _evidence_ids(result) & COERCION_SECTIONS == set()

    def test_coercion_sections_retrieved_when_enabled(self):
        graph = _threat_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert COERCION_SECTIONS <= _evidence_ids(result)


class TestFullPipelineWithExpansion:
    """End-to-end dense + graph retrieval with expansion enabled."""

    def test_coercion_sections_retrieved_when_enabled(self):
        graph = _threat_graph()
        engine = build_engine(graph, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert COERCION_SECTIONS <= _evidence_ids(result)

    def test_expansion_defaults_to_disabled(self):
        graph = _threat_graph()
        engine = build_engine(graph)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert result.retrieval.query_expansion_enabled is False
        assert result.retrieval.expanded_concepts == []
        assert result.retrieval.expanded_terms == []
        assert result.retrieval.expansion_reason == "expansion disabled"
        step = next(st for st in result.reasoning_chain if st.kind == "query_expansion")
        assert step.detail["active"] is False
        assert step.detail["enabled"] is False

    def test_expansion_diagnostics_populated(self):
        graph = _threat_graph()
        engine = build_engine(graph, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        s = result.retrieval
        assert s.query_expansion_enabled is True
        assert set(s.expanded_concepts) >= {
            "coercion", "free_consent", "voidable_agreement",
        }
        assert s.expanded_terms
        assert s.expansion_reason
        assert s.section_refs_considered == [
            "section 14", "section 15", "section 19", "section 2",
        ]
        assert s.section_refs_available == [
            "section 14", "section 15", "section 19", "section 2",
        ]
        assert s.section_refs_omitted == []
        assert "legal_expansion" in s.latency_breakdown
        assert s.latency_breakdown["legal_expansion"] >= 0.0

    def test_reasoning_chain_records_expansion(self):
        graph = _threat_graph()
        engine = build_engine(graph, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        step = next(st for st in result.reasoning_chain if st.kind == "query_expansion")
        assert step.step == 2
        assert step.detail["active"] is True
        assert "threat" in step.detail["matched_phrases"]
        assert "section 15" in step.detail["section_refs"]
        assert step.detail["section_refs_omitted"] == []
        assert "section 14" in step.detail["section_refs_considered"]

    def test_disabled_reports_no_expansion(self):
        graph = _threat_graph()
        engine = build_engine(graph, expansion_enabled=False)
        result = engine.explain(THREAT_QUERY, top_k=5)
        s = result.retrieval
        assert s.query_expansion_enabled is False
        assert s.expanded_terms == []
        assert s.expanded_concepts == []
        assert s.section_refs == []
        assert s.expansion_reason == "expansion disabled"
        assert "legal_expansion" in s.latency_breakdown
        step = next(st for st in result.reasoning_chain if st.kind == "query_expansion")
        assert step.detail["active"] is False


class TestExpansionBackwardCompatibility:
    def test_unrelated_query_unchanged(self):
        graph = _threat_graph()
        engine = build_engine(graph, expansion_enabled=True)
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence
        assert result.retrieval.expanded_concepts == []
        step = next(st for st in result.reasoning_chain if st.kind == "query_expansion")
        assert step.detail["active"] is False
        assert step.detail["reason"] == "no legal concept phrases matched"

    def test_standard_corpus_behavior_unchanged(self):
        engine = build_engine()
        result = engine.explain("performance of contracts", top_k=5)
        assert result.evidence[0].node_id == "s4"
        assert result.retrieval.expanded_concepts == []


class TestCorpusAwareExpansion:
    """The real ICA 1872 corpus lacks ss. 14/15/16/17/18/25, so expansion must
    inject only references the corpus actually contains."""

    def test_threat_query_injects_only_available_section(self):
        graph = _real_corpus_graph()
        engine = build_engine(graph, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        s = result.retrieval
        assert s.query_expansion_enabled is True
        assert set(s.expanded_concepts) == {
            "coercion", "free_consent", "voidable_agreement",
        }
        assert s.section_refs_available == ["section 2"]
        assert s.section_refs_omitted == [
            "section 14", "section 15", "section 19",
        ]
        assert "not present in the indexed corpus" in s.expansion_reason

    def test_threat_query_still_retrieves_evidence(self):
        graph = _real_corpus_graph()
        engine = build_engine(graph, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert result.evidence
        step = next(st for st in result.reasoning_chain if st.kind == "query_expansion")
        assert step.detail["active"] is True
        assert all(
            ref in step.detail["section_refs_omitted"]
            for ref in ("section 14", "section 15", "section 19")
        )
        assert step.detail["section_refs"] == ["section 2"]

    def test_graph_only_engine_omits_absent_sections(self):
        graph = _real_corpus_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert result.retrieval.section_refs_available == ["section 2"]
        assert result.retrieval.section_refs_omitted == [
            "section 14", "section 15", "section 19",
        ]

    def test_real_corpus_json_contains_no_phantom_sections(self):
        with REAL_CORPUS.open(encoding="utf-8") as f:
            data = json.load(f)
        numbering = {node.get("numbering") for node in data["nodes"]}
        assert not {"14", "15", "16", "17", "18", "25"} & numbering


class TestExpansionFeatureFlag:
    """The default is OFF; the flag must still enable/disable explicitly."""

    def test_default_config_disables_expansion(self):
        assert Settings().QA_QUERY_EXPANSION_ENABLED is False

    def test_env_var_true_enables_expansion(self, monkeypatch):
        monkeypatch.setenv("QA_QUERY_EXPANSION_ENABLED", "true")
        assert Settings().QA_QUERY_EXPANSION_ENABLED is True

    def test_env_var_false_disables_expansion(self, monkeypatch):
        monkeypatch.setenv("QA_QUERY_EXPANSION_ENABLED", "false")
        assert Settings().QA_QUERY_EXPANSION_ENABLED is False

    def test_explicit_true_enables_expansion_end_to_end(self):
        graph = _threat_graph()
        engine = build_engine(graph, expansion_enabled=True)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert COERCION_SECTIONS <= _evidence_ids(result)
        assert result.retrieval.query_expansion_enabled is True
        assert result.retrieval.section_refs_available == [
            "section 14", "section 15", "section 19", "section 2",
        ]
        assert result.retrieval.section_refs_omitted == []
        step = next(st for st in result.reasoning_chain if st.kind == "query_expansion")
        assert step.detail["active"] is True

    def test_explicit_false_preserves_original_query(self):
        graph = _threat_graph()
        engine = build_engine(graph, expansion_enabled=False)
        result = engine.explain(THREAT_QUERY, top_k=5)
        assert result.retrieval.query_expansion_enabled is False
        assert result.retrieval.expanded_concepts == []
        assert result.retrieval.expanded_terms == []
        assert result.retrieval.expansion_reason == "expansion disabled"
        step = next(st for st in result.reasoning_chain if st.kind == "query_expansion")
        assert step.detail["active"] is False
        assert step.detail["reason"] == "expansion disabled"
        assert "legal_expansion" in result.retrieval.latency_breakdown
