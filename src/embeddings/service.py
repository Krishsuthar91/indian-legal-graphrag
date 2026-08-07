"""Embedding service — batched text embedding over the configured provider."""

from __future__ import annotations

from src.config.logging_config import get_logger
from src.embeddings.models import DEFAULT_MODEL
from src.embeddings.providers import EmbeddingProvider, get_provider

log = get_logger("embeddings")

DEFAULT_BATCH_SIZE = 32


class EmbeddingService:
    """Facade for embedding text via a pluggable provider."""

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        model_name: str = DEFAULT_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        force_deterministic: bool = False,
    ) -> None:
        self._provider = provider or get_provider(
            model_name=model_name,
            force_deterministic=force_deterministic,
            batch_size=batch_size,
        )
        self._batch_size = batch_size
        self._model_name = self._provider.name

    @property
    def dim(self) -> int:
        """Embedding dimension of the active provider."""
        return int(self._provider.dim)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    def embed(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        """Embed a list of texts in batches."""
        if not texts:
            return []
        size = batch_size or self._batch_size
        log.info("embedding.generate.start", texts=len(texts), model=self._model_name)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), size):
            chunk = texts[start : start + size]
            vectors.extend(self._provider.encode(chunk))
        log.info("embedding.generate.complete", texts=len(texts), vectors=len(vectors))
        return vectors

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.embed([text])[0]

    def embed_query(self, text: str) -> list[float]:
        """Embed a retrieval query.

        bge-m3 and LaBSE use the same representation for queries and documents,
        so no instruction prefix is applied.
        """
        return self.embed_text(text)
