"""Offline corpus + QA service construction for evaluation runs.

Mirrors the production wiring (``src/llm/service.py::build_default_corpus`` /
``build_default_service``) but is fully offline and deterministic:

- one hierarchy document imported into an in-memory graph,
- deterministic embeddings indexed into an in-memory Qdrant store,
- the real ``QueryService`` / ``ExplainabilityEngine`` / ``VectorRetriever``
  classes so the evaluation exercises the exact same code path as the
  frontend ``/query`` endpoint.

The LLM client defaults to the deterministic offline ``MockLLMClient`` (the
project's default provider) but any ``LLMClient`` can be supplied, so the same
runner works against a real provider without changing the pipeline code.
"""

from __future__ import annotations

from pathlib import Path

from src.config.settings import settings
from src.embeddings import (
    EmbeddingService,
    HierarchyIndexer,
    QdrantStore,
    VectorRetriever,
    get_provider,
)
from src.knowledge_graph.importer import import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from src.llm.llm import LLMClient, MockLLMClient
from src.llm.provenance import ProvenanceStore
from src.llm.service import QueryService

DEFAULT_HIERARCHY_DIR = Path("data/hierarchy")

# One of the tracked, byte-equivalent Indian Contract Act, 1872 hierarchy
# documents (root title "The Indian Contract Act, 1872", 46 nodes).
CONTRACT_ACT_1872_DOCUMENT_ID = "0d1934142f67c5f5"


def resolve_hierarchy_file(
    document_id: str, hierarchy_file: str | Path | None = None
) -> Path:
    """Locate the hierarchy JSON for a document id.

    Prefers an explicit path, then ``data/hierarchy/{document_id}.json``, then
    a ``data/hierarchy/{document_id}.json`` under the configured directory.
    """
    if hierarchy_file is not None:
        path = Path(hierarchy_file)
        if path.exists():
            return path
    candidate = DEFAULT_HIERARCHY_DIR / f"{document_id}.json"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"no hierarchy file found for document {document_id!r} "
        f"(looked for {candidate})"
    )


def build_evaluation_graph(
    document_id: str, hierarchy_file: str | Path | None = None
) -> tuple[InMemoryGraph, Path]:
    """Import a hierarchy document into a fresh in-memory graph."""
    path = resolve_hierarchy_file(document_id, hierarchy_file)
    graph = InMemoryGraph()
    import_hierarchy_json(graph, path)
    return graph, path


def build_evaluation_corpus(
    document_id: str = CONTRACT_ACT_1872_DOCUMENT_ID,
    hierarchy_file: str | Path | None = None,
    embedding_dim: int = 64,
    seed: int = 42,
    confidence_threshold: float | None = None,
    weights: dict[str, float] | None = None,
) -> tuple[InMemoryGraph, VectorRetriever, ExplainabilityEngine]:
    """Deterministic graph + vector retriever + explainability engine.

    Mirrors ``eval.corpus.build_corpus`` without depending on the ``eval``
    package so the research framework is self-contained.
    """
    import random

    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover - numpy is optional for eval
        pass

    graph, path = build_evaluation_graph(document_id, hierarchy_file)

    provider = get_provider(
        model_name="deterministic",
        force_deterministic=True,
        deterministic_dim=embedding_dim,
    )
    service = EmbeddingService(provider=provider)
    store = QdrantStore(dim=service.dim, in_memory=True)
    store.ensure_collections()
    HierarchyIndexer(graph, store, service).index_graph()

    retriever = VectorRetriever(graph, store, service, weights=weights)
    engine = ExplainabilityEngine(
        graph,
        vector_retriever=retriever,
        weights=weights,
        confidence_threshold=(
            confidence_threshold
            if confidence_threshold is not None
            else settings.QA_CONFIDENCE_THRESHOLD
        ),
    )
    return graph, retriever, engine


def build_evaluation_service(
    document_id: str = CONTRACT_ACT_1872_DOCUMENT_ID,
    hierarchy_file: str | Path | None = None,
    llm: LLMClient | None = None,
    *,
    top_k: int | None = None,
    confidence_threshold: float | None = None,
    require_sufficient_evidence: bool | None = None,
    seed: int = 42,
    embedding_dim: int = 64,
) -> tuple[QueryService, InMemoryGraph]:
    """Build the full frontend QA service over an offline deterministic corpus.

    Returns ``(service, graph)``. The graph is returned so the runner can map
    expected sections to relevant node ids for retrieval metrics.
    """
    graph, retriever, engine = build_evaluation_corpus(
        document_id=document_id,
        hierarchy_file=hierarchy_file,
        embedding_dim=embedding_dim,
        seed=seed,
        confidence_threshold=confidence_threshold,
    )
    service = QueryService(
        engine,
        llm=llm if llm is not None else MockLLMClient(),
        provenance_store=ProvenanceStore(),
        top_k=top_k if top_k is not None else settings.QA_TOP_K,
        confidence_threshold=confidence_threshold,
        require_sufficient_evidence=require_sufficient_evidence,
    )
    return service, graph
