"""Module 10 harness — offline corpus construction.

Builds the deterministic knowledge graph + vector store + retriever + explainer
used by every evaluation run, mirroring the demo wiring so results are fully
reproducible without a network or model download.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
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


@dataclass
class Corpus:
    """Everything needed to run a retrieval system over one document."""

    graph: InMemoryGraph
    store: QdrantStore
    service: EmbeddingService
    retriever: VectorRetriever
    engine: ExplainabilityEngine
    counts: dict[str, int] = field(default_factory=dict)
    hierarchy_file: Path = Path()

    def close(self) -> None:
        self.store.close()

    @property
    def node_count(self) -> int:
        return self.counts.get("nodes_created", 0)

    @property
    def edge_count(self) -> int:
        return self.counts.get("edges_created", 0)

    def all_nodes(self) -> list[dict]:
        return self.graph.all_nodes()


def resolve_hierarchy_file(document_id: str, hierarchy_file: str | None = None) -> Path:
    """Locate a hierarchy JSON for the given document id (config, then data dir)."""
    if hierarchy_file:
        path = Path(hierarchy_file)
        if path.exists():
            return path
    candidate = Path("data/hierarchy") / f"{document_id}.json"
    if candidate.exists():
        return candidate
    fallback_dir = Path("data/hierarchy")
    files = sorted(fallback_dir.glob("*.json")) if fallback_dir.exists() else []
    if files:
        return files[0]
    raise FileNotFoundError(f"no hierarchy file found for document {document_id!r}")


def build_corpus(
    document_id: str,
    hierarchy_file: str | None = None,
    weights: dict[str, float] | None = None,
    confidence_threshold: float | None = None,
    embedding_dim: int = 64,
    seed: int = 42,
) -> Corpus:
    """Deterministic end-to-end corpus: graph -> embeddings -> retriever -> engine."""
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover - numpy is part of the eval env
        pass

    path = resolve_hierarchy_file(document_id, hierarchy_file)

    graph = InMemoryGraph()
    counts = import_hierarchy_json(graph, path)

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
    return Corpus(
        graph=graph,
        store=store,
        service=service,
        retriever=retriever,
        engine=engine,
        counts=counts,
        hierarchy_file=path,
    )
