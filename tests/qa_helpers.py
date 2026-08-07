"""Shared builders for Module 7 tests — deterministic, offline, no network."""

from __future__ import annotations

from src.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingService,
    HierarchyIndexer,
    QdrantStore,
    VectorRetriever,
)
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from src.llm.llm import MockLLMClient
from src.llm.provenance import ProvenanceStore
from src.llm.service import QueryService

DIM = 32


def build_graph() -> InMemoryGraph:
    """Small deterministic knowledge graph mirroring an Indian Contract Act."""
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


def build_retriever(graph) -> VectorRetriever:
    """Deterministic embedding service + in-memory Qdrant store + retriever."""
    provider = DeterministicEmbeddingProvider(dim=DIM)
    service = EmbeddingService(provider=provider)
    store = QdrantStore(dim=DIM, in_memory=True)
    store.ensure_collections()
    HierarchyIndexer(graph, store, service).index_graph()
    return VectorRetriever(graph, store, service)


def build_fast_corpus():
    """A tiny, fully offline (graph, store, embedding) corpus.

    Drop-in replacement for ``service.build_default_corpus`` in tests so the
    lazy default-service/corpus initialization can be exercised quickly.
    """
    graph = build_graph()
    retriever = build_retriever(graph)
    return graph, retriever.store, retriever.service


def build_engine(graph=None, **kwargs) -> ExplainabilityEngine:
    graph = graph or build_graph()
    retriever = kwargs.pop("vector_retriever", None) or build_retriever(graph)
    return ExplainabilityEngine(graph, vector_retriever=retriever, **kwargs)


def build_service(graph=None, **kwargs) -> QueryService:
    graph = graph or build_graph()
    retriever = kwargs.pop("vector_retriever", None) or build_retriever(graph)
    engine = ExplainabilityEngine(graph, vector_retriever=retriever)
    llm = kwargs.pop("llm", None) or MockLLMClient()
    store = kwargs.pop("provenance_store", None) or ProvenanceStore()
    return QueryService(engine, llm, store, **kwargs)
