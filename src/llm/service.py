"""Query service — orchestrates retrieval, prompt building, LLM generation,
and provenance storage. Also provides a lazily-built default service wired to
the project's data directory for the FastAPI endpoints and demos.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.embeddings import (
    EmbeddingService,
    HierarchyIndexer,
    QdrantStore,
    VectorRetriever,
    get_provider,
)
from src.knowledge_graph.importer import import_all
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from src.llm.llm import LLMClient, get_llm_client
from src.llm.prompts import build_messages, build_system_prompt
from src.llm.provenance import (
    AnswerResult,
    ExplanationResult,
    ProvenanceStore,
)

log = get_logger("qa_service")


class QueryService:
    """End-to-end explainable answer generation."""

    def __init__(
        self,
        engine: ExplainabilityEngine,
        llm: LLMClient,
        provenance_store: ProvenanceStore,
        top_k: int = 5,
        confidence_threshold: float | None = None,
    ) -> None:
        self.engine = engine
        self.llm = llm
        self.provenance = provenance_store
        self.top_k = top_k
        if confidence_threshold is not None:
            self.engine.threshold = confidence_threshold

    # -- API ---------------------------------------------------------------

    def answer(
        self,
        query: str,
        top_k: int | None = None,
        language: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AnswerResult:
        """Run the full pipeline: retrieve -> explain -> prompt -> generate -> store."""
        query = (query or "").strip()
        if not query:
            raise ValueError("query must not be empty")

        start = time.perf_counter()
        explanation = self.engine.explain(query, top_k=top_k or self.top_k, language=language)

        messages = build_messages(
            query, explanation, system_prompt=self._system_prompt(explanation)
        )
        response = self.llm.complete(
            messages,
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_tokens=max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
        )
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)

        provenance_id = uuid.uuid4().hex
        result = AnswerResult(
            provenance_id=provenance_id,
            query=query,
            answer=response.text,
            model=response.model,
            explanation=explanation,
            duration_ms=duration_ms,
        )
        self.provenance.save(result)

        log.info(
            "qa.answer_complete",
            provenance_id=provenance_id,
            query=query,
            model=response.model,
            evidence=len(explanation.evidence),
            confidence=explanation.confidence.score,
            duration_ms=duration_ms,
        )
        return result

    def explain(
        self,
        query: str,
        top_k: int | None = None,
        language: str | None = None,
    ) -> ExplanationResult:
        """Return the explanation without calling the LLM."""
        query = (query or "").strip()
        return self.engine.explain(query, top_k=top_k or self.top_k, language=language)

    def get_provenance(self, provenance_id: str) -> dict[str, Any] | None:
        """Fetch a stored provenance record."""
        return self.provenance.get(provenance_id)

    def _system_prompt(self, explanation: ExplanationResult) -> str:
        return build_system_prompt(language=explanation.query_language)


# ---------------------------------------------------------------------------
# Default service wiring (data directory -> graph -> embeddings -> retriever)
# ---------------------------------------------------------------------------

_default_lock = threading.Lock()
_default_service: QueryService | None = None


def build_default_graph(data_dir: str | None = None) -> InMemoryGraph:
    """Import every hierarchy JSON into a fresh in-memory graph."""
    graph = InMemoryGraph()
    import_all(graph)
    return graph


def build_default_service() -> QueryService:
    """Build a fully wired QueryService over the project's data/hierarchy corpus."""
    graph = build_default_graph()

    provider = get_provider(
        model_name=settings.EMBEDDING_MODEL, force_deterministic=True
    )
    embedding_service = EmbeddingService(provider=provider)
    store = QdrantStore(
        dim=embedding_service.dim,
        in_memory=settings.QA_INDEX_IN_MEMORY,
        url=settings.QDRANT_URL or None,
        api_key=settings.QDRANT_API_KEY or None,
    )
    store.ensure_collections()
    HierarchyIndexer(graph, store, embedding_service).index_graph()
    log.info(
        "qa_service.indexed",
        nodes=len(graph.all_nodes()),
        points=sum(store.count(c) for c in store.collections),
    )

    vector_retriever = VectorRetriever(graph, store, embedding_service)
    engine = ExplainabilityEngine(
        graph,
        vector_retriever=vector_retriever,
        confidence_threshold=settings.QA_CONFIDENCE_THRESHOLD,
    )
    llm = get_llm_client()
    provenance = ProvenanceStore(settings.QA_PROVENANCE_DIR)
    return QueryService(
        engine,
        llm,
        provenance,
        top_k=settings.QA_TOP_K,
        confidence_threshold=settings.QA_CONFIDENCE_THRESHOLD,
    )


def get_default_service() -> QueryService:
    """Return a lazily-built, cached default QueryService (thread-safe)."""
    global _default_service
    if _default_service is None:
        with _default_lock:
            if _default_service is None:
                _default_service = build_default_service()
    return _default_service
