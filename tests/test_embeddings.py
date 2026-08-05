"""Tests for embedding models, providers, and the embedding service."""

import math

from src.embeddings.models import (
    DEFAULT_MODEL,
    MODEL_REGISTRY,
    EmbeddingModel,
    get_model_spec,
)
from src.embeddings.providers import (
    DETERMINISTIC_PROVIDER,
    DeterministicEmbeddingProvider,
    get_provider,
)
from src.embeddings.service import EmbeddingService


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb)


class TestModelRegistry:
    def test_contains_all_supported_models(self):
        assert set(MODEL_REGISTRY) == {
            EmbeddingModel.BGE_M3.value,
            EmbeddingModel.LABSE.value,
            EmbeddingModel.MURIL.value,
            EmbeddingModel.INDIC_BERT.value,
        }

    def test_bge_m3_dimensions(self):
        spec = get_model_spec(EmbeddingModel.BGE_M3.value)
        assert spec.dim == 1024
        assert spec.max_seq == 8192
        assert spec.provider == "sentence_transformers"

    def test_labse_dimensions(self):
        spec = get_model_spec(EmbeddingModel.LABSE.value)
        assert spec.dim == 768
        assert spec.provider == "sentence_transformers"

    def test_muril_dimensions(self):
        spec = get_model_spec(EmbeddingModel.MURIL.value)
        assert spec.dim == 768
        assert spec.provider == "transformers"

    def test_indic_bert_dimensions(self):
        spec = get_model_spec(EmbeddingModel.INDIC_BERT.value)
        assert spec.dim == 768
        assert spec.provider == "transformers"

    def test_default_model(self):
        assert DEFAULT_MODEL == EmbeddingModel.BGE_M3.value


class TestDeterministicProvider:
    def test_configured_dim(self):
        p = DeterministicEmbeddingProvider(dim=1024)
        assert p.dim == 1024

    def test_default_dim(self):
        assert DeterministicEmbeddingProvider().dim == 64

    def test_deterministic(self):
        p = DeterministicEmbeddingProvider()
        assert p.encode(["hello world"]) == p.encode(["hello world"])

    def test_l2_normalized(self):
        p = DeterministicEmbeddingProvider(dim=128)
        vec = p.encode(["the indian contract act"])[0]
        norm = math.sqrt(sum(v * v for v in vec))
        assert math.isclose(norm, 1.0, abs_tol=1e-6)

    def test_identical_text_high_similarity(self):
        p = DeterministicEmbeddingProvider(dim=128)
        a = p.encode(["performance of contracts"])[0]
        b = p.encode(["performance of contracts"])[0]
        assert _cosine(a, b) > 0.999

    def test_similar_text_more_similar_than_disjoint(self):
        p = DeterministicEmbeddingProvider(dim=256)
        similar = p.encode(["contract law india"])[0]
        overlap = p.encode(["contract law in india"])[0]
        disjoint = p.encode(["quantum physics astronomy"])[0]
        assert _cosine(similar, overlap) > _cosine(similar, disjoint)

    def test_batch_encode(self):
        p = DeterministicEmbeddingProvider()
        vectors = p.encode(["one", "two", "three"])
        assert len(vectors) == 3
        assert all(len(v) == p.dim for v in vectors)


class TestGetProvider:
    def test_force_deterministic(self):
        provider = get_provider(force_deterministic=True)
        assert provider.name == DETERMINISTIC_PROVIDER

    def test_deterministic_name(self):
        provider = get_provider(model_name="deterministic")
        assert provider.name == DETERMINISTIC_PROVIDER

    def test_unknown_model_falls_back(self):
        provider = get_provider(model_name="no/such-model")
        assert provider.name == "no/such-model"

    def test_registry_dim_used_when_forced(self):
        provider = get_provider(
            model_name=EmbeddingModel.BGE_M3.value, force_deterministic=True
        )
        assert provider.dim == 1024


class TestEmbeddingService:
    def test_dimension_from_provider(self):
        service = EmbeddingService(
            provider=DeterministicEmbeddingProvider(dim=32), force_deterministic=True
        )
        assert service.dim == 32

    def test_default_service_uses_deterministic(self):
        service = EmbeddingService(force_deterministic=True)
        assert service.model_name == DETERMINISTIC_PROVIDER
        # deterministic fallback keeps the configured model's dimension
        assert service.dim == 1024

    def test_embed_text(self):
        service = EmbeddingService(force_deterministic=True)
        vec = service.embed_text("section 4 performance")
        assert len(vec) == 1024

    def test_embed_query_equals_embed_text(self):
        service = EmbeddingService(force_deterministic=True)
        assert service.embed_query("performance") == service.embed_text("performance")

    def test_embed_batch_respects_batch_size(self):
        service = EmbeddingService(force_deterministic=True, batch_size=2)
        texts = [f"text {i}" for i in range(5)]
        vectors = service.embed(texts, batch_size=2)
        assert len(vectors) == 5

    def test_embed_empty(self):
        service = EmbeddingService(force_deterministic=True)
        assert service.embed([]) == []

    def test_provider_exposed(self):
        provider = DeterministicEmbeddingProvider(dim=16)
        service = EmbeddingService(provider=provider)
        assert service.provider is provider
