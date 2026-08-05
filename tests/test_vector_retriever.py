"""Tests for the vector/graph hybrid retriever."""

import re

import pytest

from src.embeddings.indexer import HierarchyIndexer
from src.embeddings.providers import DeterministicEmbeddingProvider
from src.embeddings.retriever import (
    DEFAULT_HYBRID_WEIGHTS,
    VectorRetriever,
    normalize_weights,
)
from src.embeddings.service import EmbeddingService
from src.embeddings.store import QdrantStore
from src.knowledge_graph.neo4j_driver import InMemoryGraph


class CrossLingualProvider(DeterministicEmbeddingProvider):
    """Maps English/Hindi equivalents onto the same token before hashing.

    Simulates the language-agnostic behaviour of bge-m3 / LaBSE: semantically
    equivalent phrases in different languages embed to near-identical vectors.
    """

    SYNONYMS = {
        "contract": "concept_contract",
        "contracts": "concept_contract",
        "अनुबंध": "concept_contract",
        "performance": "concept_performance",
        "प्रदर्शन": "concept_performance",
        "agreement": "concept_agreement",
        "समझौता": "concept_agreement",
    }

    def encode(self, texts):
        return [self._embed_syn(t) for t in texts]

    def _embed_syn(self, text: str) -> list[float]:
        tokens = re.split(r"\s+", text.lower().strip())
        mapped = " ".join(self.SYNONYMS.get(t, t) for t in tokens)
        return super()._embed(mapped)


def _build_graph():
    g = InMemoryGraph()
    g.create_node("Document", "doc1", {
        "document_id": "doc1", "title": "THE INDIAN CONTRACT ACT, 1892", "language": "en",
    })
    g.create_node("Chapter", "ch1", {
        "title": "CHAPTER I", "text": "Preliminary", "hierarchy_level": 4,
    })
    g.create_node("Chapter", "ch2", {
        "title": "CHAPTER II", "text": "Of Contracts", "hierarchy_level": 4,
    })
    g.create_node("Section", "s1", {
        "title": "Short title", "numbering": "1", "hierarchy_level": 5,
        "text": "This Act may be called the Indian Contract Act.",
    })
    g.create_node("Section", "s2", {
        "title": "Definitions", "numbering": "2", "hierarchy_level": 5,
        "text": "contract means an agreement enforceable by law.",
    })
    g.create_node("Section", "s4", {
        "title": "Performance of contracts", "numbering": "4", "hierarchy_level": 5,
        "text": "Performance of contracts. (a) where the contract provides "
               "(b) where no provision is made.",
    })
    g.create_edge("ch1", "doc1", "PART_OF")
    g.create_edge("ch2", "doc1", "PART_OF")
    g.create_edge("s1", "ch1", "PART_OF")
    g.create_edge("s2", "ch1", "PART_OF")
    g.create_edge("s4", "ch2", "PART_OF")
    return g


@pytest.fixture()
def graph():
    return _build_graph()


@pytest.fixture()
def store():
    s = QdrantStore(dim=32, in_memory=True)
    s.ensure_collections()
    yield s
    s.close()


@pytest.fixture()
def service():
    return EmbeddingService(provider=DeterministicEmbeddingProvider(dim=32))


def _index(graph, store, service):
    HierarchyIndexer(graph, store, service).index_graph()


def _retriever(graph, store, service):
    return VectorRetriever(graph, store, service)


class TestDenseSearch:
    def test_surfaces_matching_section(self, graph, store, service):
        _index(graph, store, service)
        hits = _retriever(graph, store, service).dense_search("performance of contracts", top_k=5)
        assert hits
        assert "s4" in [h.node_id for h in hits]

    def test_exact_match_ranks_first(self):
        store = QdrantStore(dim=64, in_memory=True)
        store.ensure_collections()
        g = InMemoryGraph()
        g.create_node("Document", "d", {"document_id": "d", "language": "en"})
        g.create_node("Section", "sx", {
            "title": "", "numbering": "1", "hierarchy_level": 5,
            "text": "performance of contracts",
        })
        g.create_edge("sx", "d", "PART_OF")
        service = EmbeddingService(provider=CrossLingualProvider(dim=64))
        HierarchyIndexer(g, store, service).index_graph()
        hits = VectorRetriever(g, store, service).dense_search("performance of contracts", top_k=5)
        store.close()
        assert hits[0].node_id == "sx"
        assert hits[0].score > 0.99

    def test_scores_normalized(self, graph, store, service):
        _index(graph, store, service)
        hits = _retriever(graph, store, service).dense_search("performance of contracts", top_k=5)
        assert all(0.0 <= h.score <= 1.0 for h in hits)

    def test_cross_lingual_alias(self, graph, store, service):
        _index(graph, store, service)
        hits = _retriever(graph, store, service).cross_lingual_search("performance of contracts")
        assert "s4" in [h.node_id for h in hits]

    def test_language_filter(self, graph, store, service):
        _index(graph, store, service)
        hits = _retriever(graph, store, service).dense_search(
            "performance of contracts", language="xx"
        )
        assert hits == []


class TestCrossLingual:
    @pytest.fixture()
    def xl_retriever(self):
        store = QdrantStore(dim=64, in_memory=True)
        store.ensure_collections()
        g = InMemoryGraph()
        g.create_node("Document", "docX", {"document_id": "docX", "language": "hi"})
        g.create_node("Section", "s_hi", {
            "title": "हिंदी खंड", "numbering": "1", "hierarchy_level": 5,
            "text": "अनुबंध प्रदर्शन",
        })
        g.create_node("Section", "s_en", {
            "title": "English section", "numbering": "2", "hierarchy_level": 5,
            "text": "contract performance",
        })
        g.create_edge("s_hi", "docX", "PART_OF")
        g.create_edge("s_en", "docX", "PART_OF")
        service = EmbeddingService(provider=CrossLingualProvider(dim=64))
        HierarchyIndexer(g, store, service).index_graph()
        yield VectorRetriever(g, store, service)
        store.close()

    def test_english_query_finds_hindi_document(self, xl_retriever):
        hits = xl_retriever.cross_lingual_search("performance contract", top_k=5)
        node_ids = [h.node_id for h in hits]
        assert "s_hi" in node_ids
        assert "s_en" in node_ids

    def test_hindi_query_finds_english_document(self, xl_retriever):
        hits = xl_retriever.cross_lingual_search("अनुबंध प्रदर्शन", top_k=5)
        node_ids = [h.node_id for h in hits]
        assert "s_en" in node_ids
        assert "s_hi" in node_ids

    def test_monolingual_provider_does_not_cross_match(self):
        store = QdrantStore(dim=64, in_memory=True)
        store.ensure_collections()
        g = InMemoryGraph()
        g.create_node("Document", "docY", {"document_id": "docY", "language": "hi"})
        g.create_node("Section", "s_hi", {
            "title": "x", "numbering": "1", "hierarchy_level": 5,
            "text": "अनुबंध प्रदर्शन",
        })
        g.create_node("Section", "s_en", {
            "title": "y", "numbering": "2", "hierarchy_level": 5,
            "text": "contract performance",
        })
        g.create_edge("s_hi", "docY", "PART_OF")
        g.create_edge("s_en", "docY", "PART_OF")
        service = EmbeddingService(provider=DeterministicEmbeddingProvider(dim=64))
        HierarchyIndexer(g, store, service).index_graph()
        retriever = VectorRetriever(g, store, service)
        hits = retriever.dense_search("contract performance", top_k=5)
        store.close()
        scores = {h.node_id: h.score for h in hits}
        assert scores["s_en"] > scores["s_hi"]


class TestHierarchyRetrieval:
    def test_propagates_to_ancestors(self, graph, store, service):
        _index(graph, store, service)
        scores = _retriever(graph, store, service).hierarchy_retrieval(
            "performance of contracts", top_k=3
        )
        assert "s4" in scores
        assert "ch2" in scores
        assert scores["s4"] == 1.0
        assert scores["ch2"] >= 0.6

    def test_empty_store_returns_empty(self, graph, store, service):
        scores = _retriever(graph, store, service).hierarchy_retrieval(
            "performance of contracts"
        )
        assert scores == {}


class TestHybrid:
    def test_returns_results(self, graph, store, service):
        _index(graph, store, service)
        results = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=5
        )
        assert results
        assert results[0].node_id == "s4"

    def test_top_result_sources_include_dense(self, graph, store, service):
        _index(graph, store, service)
        results = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=5
        )
        assert "dense" in results[0].sources

    def test_chapter_surfaces_via_hierarchy(self, graph, store, service):
        _index(graph, store, service)
        results = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=10
        )
        node_ids = [r.node_id for r in results]
        assert "ch2" in node_ids

    def test_scores_in_range(self, graph, store, service):
        _index(graph, store, service)
        results = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=10
        )
        assert all(0.0 <= r.score <= 1.0 for r in results)

    def test_graph_results_without_vectors(self, graph, store, service):
        # No vectors indexed — hybrid should still return graph retrieval results
        results = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=5
        )
        assert results
        assert "graph" in results[0].sources

    def test_section_reference_query(self, graph, store, service):
        _index(graph, store, service)
        results = _retriever(graph, store, service).hybrid_retrieve("section 4", top_k=5)
        assert results[0].node_id == "s4"

    def test_hit_metadata(self, graph, store, service):
        _index(graph, store, service)
        results = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=5
        )
        top = results[0]
        assert top.title
        assert top.label == "Section"
        assert top.level == 5


class TestWeights:
    def test_default_weights_normalized(self):
        w = normalize_weights(None)
        assert abs(sum(w.values()) - 1.0) < 1e-9
        assert w["dense"] == pytest.approx(DEFAULT_HYBRID_WEIGHTS["dense"])

    def test_partial_weights_filled(self):
        w = normalize_weights({"dense": 0.5})
        assert "graph" in w and "hierarchy" in w
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_graph_only_weight_uses_graph_score(self, graph, store, service):
        _index(graph, store, service)
        hits = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=5, weights={"graph": 1.0}
        )
        top = hits[0]
        assert top.node_id == "s4"
        assert top.score == pytest.approx(top.graph_score)

    def test_dense_only_weight_uses_dense_score(self, graph, store, service):
        _index(graph, store, service)
        results = _retriever(graph, store, service).hybrid_retrieve(
            "performance of contracts", top_k=5, weights={"dense": 1.0}
        )
        assert results
        top = results[0]
        assert top.score == pytest.approx(top.dense_score)

    def test_ranking_changes_with_weights(self, graph, store, service):
        _index(graph, store, service)
        retriever = _retriever(graph, store, service)
        dense_ranked = [r.node_id for r in retriever.hybrid_retrieve(
            "performance of contracts", top_k=5, weights={"dense": 1.0}
        )]
        graph_ranked = [r.node_id for r in retriever.hybrid_retrieve(
            "performance of contracts", top_k=5, weights={"graph": 1.0}
        )]
        assert dense_ranked != graph_ranked or dense_ranked[:1] != graph_ranked[:1]
