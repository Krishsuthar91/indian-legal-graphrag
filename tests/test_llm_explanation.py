"""Tests for the explainability engine (Module 7)."""


from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from tests.qa_helpers import build_engine, build_graph


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
