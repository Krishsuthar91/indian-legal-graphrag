"""Deterministic embedding helpers for semantic RAGAS surrogate metrics."""

from __future__ import annotations

import math

from src.embeddings.providers import DeterministicEmbeddingProvider
from src.embeddings.service import EmbeddingService

DEFAULT_DIM = 64


class EmbeddingCache:
    """Cached deterministic embedder + cosine similarity."""

    def __init__(self, dim: int = DEFAULT_DIM, seed: int = 42) -> None:
        self._seed = seed
        self.dim = dim
        self._service = EmbeddingService(provider=DeterministicEmbeddingProvider(dim=dim))
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        key = text.strip().lower()
        if key not in self._cache:
            self._cache[key] = self._service.embed_query(text)
        return self._cache[key]

    def cosine(self, a: str, b: str) -> float:
        va = self.embed(a)
        vb = self.embed(b)
        dot = sum(x * y for x, y in zip(va, vb))
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(y * y for y in vb))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def relevance(self, query: str, text: str) -> float:
        """0.0 when irrelevant, cosine similarity otherwise (kept in [0, 1])."""
        return max(0.0, self.cosine(query, text))
