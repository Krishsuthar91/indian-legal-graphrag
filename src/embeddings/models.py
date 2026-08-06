"""Embedding model registry and vector collection definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EmbeddingModel(StrEnum):
    """Supported embedding models."""

    BGE_M3 = "BAAI/bge-m3"
    LABSE = "sentence-transformers/LaBSE"
    MURIL = "google/muril-base-cased"
    INDIC_BERT = "ai4bharat/indic-bert"


@dataclass(frozen=True)
class ModelSpec:
    """Metadata for an embedding model."""

    name: str
    dim: int
    max_seq: int
    provider: str  # "sentence_transformers" | "transformers"
    description: str


MODEL_REGISTRY: dict[str, ModelSpec] = {
    EmbeddingModel.BGE_M3.value: ModelSpec(
        name=EmbeddingModel.BGE_M3.value,
        dim=1024,
        max_seq=8192,
        provider="sentence_transformers",
        description="Multilingual dense retriever supporting 100+ languages (default)",
    ),
    EmbeddingModel.LABSE.value: ModelSpec(
        name=EmbeddingModel.LABSE.value,
        dim=768,
        max_seq=256,
        provider="sentence_transformers",
        description="Language-agnostic BERT sentence embedding for 109 languages",
    ),
    EmbeddingModel.MURIL.value: ModelSpec(
        name=EmbeddingModel.MURIL.value,
        dim=768,
        max_seq=512,
        provider="transformers",
        description="Multilingual Representations for Indian Languages (12 languages)",
    ),
    EmbeddingModel.INDIC_BERT.value: ModelSpec(
        name=EmbeddingModel.INDIC_BERT.value,
        dim=768,
        max_seq=512,
        provider="transformers",
        description="IndicBERT — multilingual model covering 12 major Indian languages",
    ),
}

DEFAULT_MODEL = EmbeddingModel.BGE_M3.value


def get_model_spec(model_name: str) -> ModelSpec | None:
    """Look up model metadata by hub id."""
    return MODEL_REGISTRY.get(model_name)


class CollectionName(StrEnum):
    """Vector collections, one per hierarchy granularity."""

    DOCUMENTS = "documents"
    CHAPTERS = "chapters"
    SECTIONS = "sections"
    CLAUSES = "clauses"


DEFAULT_COLLECTIONS: list[str] = [c.value for c in CollectionName]

# Maps hierarchy node_type -> vector collection
HIERARCHY_TO_COLLECTION: dict[str, str] = {
    "document": CollectionName.DOCUMENTS.value,
    "act_title": CollectionName.DOCUMENTS.value,
    "preamble": CollectionName.DOCUMENTS.value,
    "chapter": CollectionName.CHAPTERS.value,
    "part": CollectionName.CHAPTERS.value,
    "section": CollectionName.SECTIONS.value,
    "sub_section": CollectionName.SECTIONS.value,
    "explanation": CollectionName.SECTIONS.value,
    "illustration": CollectionName.SECTIONS.value,
    "proviso": CollectionName.SECTIONS.value,
    "clause": CollectionName.CLAUSES.value,
    "sub_clause": CollectionName.CLAUSES.value,
    "schedule": CollectionName.CLAUSES.value,
    "appendix": CollectionName.CLAUSES.value,
}


def collection_for(node_type: str) -> str:
    """Map a hierarchy node_type to its vector collection."""
    return HIERARCHY_TO_COLLECTION.get(node_type, CollectionName.SECTIONS.value)


# Maps graph node label -> vector collection (labels produced by the KG importer)
NODE_LABEL_TO_COLLECTION: dict[str, str] = {
    "Document": CollectionName.DOCUMENTS.value,
    "Chapter": CollectionName.CHAPTERS.value,
    "Part": CollectionName.CHAPTERS.value,
    "Section": CollectionName.SECTIONS.value,
    "Clause": CollectionName.CLAUSES.value,
    "Schedule": CollectionName.CLAUSES.value,
}


def collection_for_label(label: str) -> str | None:
    """Map a graph node label to its vector collection, or None to skip."""
    return NODE_LABEL_TO_COLLECTION.get(label)
