"""Embedding service — batched text embedding over the configured provider."""

from __future__ import annotations

import time

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

    @property
    def device(self) -> str:
        """Device the active provider runs on (cpu / cuda / ...)."""
        return str(getattr(self._provider, "device", "cpu"))

    def embed(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        """Embed a list of texts in batches.

        Texts are length-stratified (longest first) before chunking so each
        batch is padded only to its own longest text instead of the corpus
        maximum — this removes wasted CPU attention over padding without
        changing a single vector. Output order matches the input order.
        Progress is logged per batch so long cold-start embeddings never look
        like a hang. Memory stays bounded because the provider only ever sees
        ``batch_size`` texts at a time.
        """
        if not texts:
            return []
        size = batch_size or self._batch_size
        order: list[int] | None = None
        work = texts
        if len(texts) > size:
            order = sorted(range(len(texts)), key=lambda i: len(texts[i]), reverse=True)
            work = [texts[i] for i in order]
        batches = (len(work) + size - 1) // size
        log.info(
            "embedding.generate.start",
            texts=len(texts),
            model=self._model_name,
            batch_size=size,
            batches=batches,
            stratified=order is not None,
        )
        vectors: list[list[float]] = []
        started = time.perf_counter()
        for start in range(0, len(work), size):
            chunk = work[start : start + size]
            chunk_started = time.perf_counter()
            chunk_vectors = self._provider.encode(chunk)
            vectors.extend(chunk_vectors)
            if batches > 1:
                log.info(
                    "embedding.batch.progress",
                    index=start // size + 1,
                    of=batches,
                    texts=len(chunk),
                    elapsed_s=round(time.perf_counter() - chunk_started, 2),
                    cumulative_s=round(time.perf_counter() - started, 2),
                )
        if order is not None:
            restored: list[list[float]] = [vectors[0]] * len(vectors)
            for position, original_index in enumerate(order):
                restored[original_index] = vectors[position]
            vectors = restored
        log.info(
            "embedding.generate.complete",
            texts=len(texts),
            vectors=len(vectors),
            elapsed_s=round(time.perf_counter() - started, 2),
        )
        return vectors

    def _prefixed_encode(
        self, texts: list[str], prefix: str, batch_size: int | None
    ) -> list[list[float]]:
        if not texts:
            return []
        if prefix:
            texts = [t if t.startswith(prefix) else f"{prefix}{t}" for t in texts]
        return self.embed(texts, batch_size=batch_size)

    def embed_documents(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        """Embed documents/placements, applying the provider's passage prefix."""
        return self._prefixed_encode(
            texts, getattr(self._provider, "passage_prefix", ""), batch_size
        )

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.embed([text])[0]

    def embed_query(self, text: str) -> list[float]:
        """Embed a retrieval query.

        bge-m3 and bge-large-en use the same representation for queries and
        documents, so no instruction prefix is applied. Models that require a
        query prefix (e.g. e5-large-v2, ``query: ``) get it here so index and
        query vectors remain in the same space.
        """
        return self._prefixed_encode([text], getattr(self._provider, "query_prefix", ""), None)[0]
