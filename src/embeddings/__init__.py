"""Embedding & Vector Retrieval Layer — Qdrant + multilingual embeddings + hybrid retrieval."""

from src.embeddings.benchmark import BenchmarkReport, benchmark_retrieval, format_report
from src.embeddings.indexer import HierarchyIndexer
from src.embeddings.models import (
    DEFAULT_COLLECTIONS,
    DEFAULT_MODEL,
    MODEL_REGISTRY,
    CollectionName,
    EmbeddingModel,
)
from src.embeddings.providers import (
    DETERMINISTIC_PROVIDER,
    DeterministicEmbeddingProvider,
    get_provider,
)
from src.embeddings.retriever import (
    DEFAULT_HYBRID_WEIGHTS,
    HybridHit,
    VectorHit,
    VectorRetriever,
    normalize_weights,
)
from src.embeddings.service import EmbeddingService
from src.embeddings.store import QdrantStore

__all__ = [
    "CollectionName",
    "DEFAULT_COLLECTIONS",
    "DEFAULT_MODEL",
    "EmbeddingModel",
    "MODEL_REGISTRY",
    "DETERMINISTIC_PROVIDER",
    "DeterministicEmbeddingProvider",
    "get_provider",
    "EmbeddingService",
    "QdrantStore",
    "HierarchyIndexer",
    "VectorRetriever",
    "VectorHit",
    "HybridHit",
    "DEFAULT_HYBRID_WEIGHTS",
    "normalize_weights",
    "BenchmarkReport",
    "benchmark_retrieval",
    "format_report",
]
