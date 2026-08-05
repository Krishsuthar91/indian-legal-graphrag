"""Embedding providers — real model backends plus an offline deterministic fallback.

Only the deterministic provider is required at runtime. The sentence-transformers
and transformers providers are imported lazily so tests and offline demos run
without torch/model downloads.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

from src.config.logging_config import get_logger

log = get_logger("embeddings")

DETERMINISTIC_PROVIDER = "deterministic"


class EmbeddingProvider(Protocol):
    """Common embedding interface."""

    name: str
    dim: int

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts into L2-normalized vectors."""
        ...


class DeterministicEmbeddingProvider:
    """Hash-based deterministic embeddings.

    Projects token bag-of-words into a fixed dimension using a feature-hashing
    trick (sign trick). Identical text -> identical vector, overlapping text ->
    higher cosine similarity. Used for tests and offline operation when no model
    weights are available.
    """

    def __init__(self, dim: int = 64, name: str = DETERMINISTIC_PROVIDER) -> None:
        self.dim = dim
        self.name = name

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:8], "big") % self.dim
            sign = 1.0 if int.from_bytes(digest[4:], "big") % 2 == 0 else -1.0
            vector[idx] += sign
        # L2 normalize
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]


class SentenceTransformerProvider:
    """Wrapper around sentence-transformers models (bge-m3, LaBSE)."""

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.batch_size = batch_size
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


class TransformersProvider:
    """Wrapper around raw HF models (MuRIL, IndicBERT) using mean pooling."""

    def __init__(self, model_name: str, max_seq: int = 512, batch_size: int = 32) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.name = model_name
        self.max_seq = max_seq
        self.batch_size = batch_size
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)
        self.dim = int(self._model.config.hidden_size)

    def encode(self, texts: list[str]) -> list[list[float]]:
        torch = self._torch
        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_seq,
            return_tensors="pt",
        )
        with torch.no_grad():
            output = self._model(**encoded)
        last_hidden = output.last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).float()
        pooled = (last_hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        pooled = pooled / torch.norm(pooled, dim=1, keepdim=True).clamp(min=1e-9)
        return pooled.tolist()


def get_provider(
    model_name: str | None = None,
    force_deterministic: bool = False,
    deterministic_dim: int | None = None,
    batch_size: int = 32,
) -> EmbeddingProvider:
    """Create an embedding provider for the given model.

    Falls back to the deterministic provider when model weights cannot be loaded
    (e.g. offline, torch not installed).
    """
    from src.embeddings.models import get_model_spec

    name = (model_name or "").strip() or "BAAI/bge-m3"

    if force_deterministic or name.lower() == DETERMINISTIC_PROVIDER:
        spec = get_model_spec(name) if name.lower() != DETERMINISTIC_PROVIDER else None
        dim = deterministic_dim or (spec.dim if spec else 64)
        return DeterministicEmbeddingProvider(dim=dim, name=DETERMINISTIC_PROVIDER)

    spec = get_model_spec(name)
    if spec is None:
        log.warning("unknown_embedding_model", model=name, using="deterministic")
        return DeterministicEmbeddingProvider(dim=deterministic_dim or 64, name=name)

    try:
        if spec.provider == "sentence_transformers":
            provider = SentenceTransformerProvider(name, batch_size=batch_size)
        else:
            provider = TransformersProvider(name, max_seq=spec.max_seq, batch_size=batch_size)
        log.info("embedding.provider_ready", model=name, dim=provider.dim)
        return provider
    except Exception as exc:  # pragma: no cover - depends on environment
        log.warning(
            "embedding.model_unavailable",
            model=name,
            error=str(exc),
            using="deterministic",
        )
        return DeterministicEmbeddingProvider(dim=deterministic_dim or spec.dim, name=name)
