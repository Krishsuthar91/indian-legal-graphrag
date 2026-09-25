"""Query service — orchestrates retrieval, prompt building, LLM generation,
and provenance storage. Also provides a lazily-built default service wired to
the project's data directory for the FastAPI endpoints and demos.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from pathlib import Path
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
from src.knowledge_graph.canonical import canonical_doc_ids
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
from src.retrieval.query import parse_query

log = get_logger("qa_service")

# Grounded guard answer returned when retrieval validation finds the indexed
# evidence insufficient. The LLM is never invoked in that case, so it cannot
# fabricate a section or assert that a provision "does not exist".
INSUFFICIENT_EVIDENCE_ANSWER = "The indexed evidence is insufficient to answer this question."
INSUFFICIENT_EVIDENCE_MODEL = "grounding-guard"

# ---------------------------------------------------------------------------
# Grounding guard (Task 15): thresholds enforced by _should_generate_answer
# before the LLM is ever called. The LLM is skipped whenever any required
# grounding condition is unmet, so the system never fabricates a legal answer.
# ---------------------------------------------------------------------------
GUARD_MIN_RELEVANCE = 0.30
GUARD_MIN_SUFFICIENCY = 0.45
GUARD_MIN_CONFIDENCE = 0.30

GROUNDED_GUARD_ANSWER = (
    "I could not verify this answer from the indexed legal corpus. "
    "The retrieved evidence is insufficient to provide a reliable legal response."
)


class QueryService:
    """End-to-end explainable answer generation."""

    def __init__(
        self,
        engine: ExplainabilityEngine,
        llm: LLMClient,
        provenance_store: ProvenanceStore,
        top_k: int = 5,
        confidence_threshold: float | None = None,
        require_sufficient_evidence: bool | None = None,
        grounding_guard_enabled: bool | None = None,
    ) -> None:
        self.engine = engine
        self.llm = llm
        self.provenance = provenance_store
        self.top_k = top_k
        if confidence_threshold is not None:
            self.engine.threshold = confidence_threshold
        self.require_sufficient_evidence = (
            settings.QA_REQUIRE_SUFFICIENT_EVIDENCE
            if require_sufficient_evidence is None
            else require_sufficient_evidence
        )
        self.grounding_guard_enabled = (
            settings.QA_GROUNDING_GUARD_ENABLED
            if grounding_guard_enabled is None
            else grounding_guard_enabled
        )

    # -- API ---------------------------------------------------------------

    def answer(
        self,
        query: str,
        top_k: int | None = None,
        language: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        deadline: float | None = None,
    ) -> AnswerResult:
        """Run the full pipeline: retrieve -> explain -> prompt -> generate -> store.

        ``deadline`` is a monotonic-clock timestamp bounding the LLM call
        (including its retries); the API layer passes the QA request deadline.
        """
        query = (query or "").strip()
        if not query:
            raise ValueError("query must not be empty")

        start = time.perf_counter()
        if top_k is None and not self.engine.adaptive:
            top_k = self.top_k
        explanation = self.engine.explain(query, top_k=top_k, language=language)

        # Resolve LLM-generation parameters up front so both generation branches
        # (grounding guard pass-through and legacy path) stay identical.
        gen_temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        gen_max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

        needs_legacy_guard = (
            self.require_sufficient_evidence and explanation.validity.insufficient_evidence
        )
        # Task 15 grounding guard: enforced before any LLM generation. When
        # enabled it replaces the coarse legacy insufficiency check with a
        # granular set of grounding thresholds. When disabled, the system
        # behaves exactly as before.
        grounding_blocked = False
        generated = False
        if self.grounding_guard_enabled:
            grounding_blocked = not self._should_generate_answer(explanation)
            if grounding_blocked:
                response_text = self._grounding_guard_response(explanation)
                response_model = INSUFFICIENT_EVIDENCE_MODEL
            else:
                messages = build_messages(
                    query, explanation, system_prompt=self._system_prompt(explanation)
                )
                response = self.llm.complete(
                    messages,
                    temperature=gen_temperature,
                    max_tokens=gen_max_tokens,
                    deadline=deadline,
                )
                response_text = response.text
                response_model = response.model
                generated = True
        elif needs_legacy_guard:
            response_text = INSUFFICIENT_EVIDENCE_ANSWER
            response_model = INSUFFICIENT_EVIDENCE_MODEL
            log.info(
                "qa.answer_guard_insufficient",
                query=query,
                evidence=len(explanation.evidence),
                confidence=explanation.confidence.score,
                threshold=self.engine.threshold,
            )
        else:
            messages = build_messages(
                query, explanation, system_prompt=self._system_prompt(explanation)
            )
            response = self.llm.complete(
                messages,
                temperature=gen_temperature,
                max_tokens=gen_max_tokens,
                deadline=deadline,
            )
            response_text = response.text
            response_model = response.model
            generated = True
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)

        # Task 20: after a real generated answer exists, re-score confidence and
        # the verification badge with the actual citation-entailment result. This
        # is skipped when no answer text or no evidence is present, and when the
        # grounding guard / legacy guard blocked generation (no real answer).
        if generated:
            self._score_with_citation_entailment(explanation, response_text, query)

        provenance_id = uuid.uuid4().hex
        result = AnswerResult(
            provenance_id=provenance_id,
            query=query,
            answer=response_text,
            model=response_model,
            explanation=explanation,
            duration_ms=duration_ms,
        )
        self.provenance.save(result)

        log.info(
            "qa.answer_complete",
            provenance_id=provenance_id,
            query=query,
            model=response_model,
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
        if top_k is None and not self.engine.adaptive:
            top_k = self.top_k
        return self.engine.explain(query, top_k=top_k, language=language)

    def _score_with_citation_entailment(
        self, explanation: ExplanationResult, answer: str, query: str
    ) -> ExplanationResult:
        """Run citation entailment on a generated answer and re-score the result.

        Task 20: ``explain()`` computes confidence before an answer exists, so it
        cannot evaluate citation entailment (the 0.35 entailment weight is
        silently redistributed). Once ``answer()`` has generated text we re-run
        the existing entailment implementation and feed the *real* entailment
        score back into the existing confidence formula and verification badge.
        This reuses ``_compute_citation_entailment``, ``_score_confidence``,
        ``_assess_validity`` and ``_build_verification_trace`` unchanged — no
        verification logic is redesigned.

        1. Skip entailment when there is no answer text or no retrieved evidence.
        2. Entailment is only evaluated after a generated answer, citations, and
           evidence all exist.
        """
        if not (answer or "").strip():
            return explanation
        if not explanation.evidence:
            return explanation
        if not (
            hasattr(self.engine, "_compute_citation_entailment")
            and hasattr(self.engine, "_score_confidence")
            and hasattr(self.engine, "_assess_validity")
            and hasattr(self.engine, "_build_verification_trace")
        ):
            return explanation

        entailment = self.engine._compute_citation_entailment(
            answer, explanation.evidence, explanation.citations
        )
        parsed = parse_query(query)
        evidence_relevance = explanation.evidence_relevance
        confidence = self.engine._score_confidence(
            explanation.evidence,
            parsed,
            query,
            evidence_relevance=evidence_relevance,
            citation_entailment=entailment,
            contradiction_found=entailment.contradiction_found,
        )
        validity = self.engine._assess_validity(
            explanation.evidence,
            explanation.counter_authorities,
            confidence,
            query,
            evidence_relevance=evidence_relevance,
        )
        explanation.confidence = confidence
        explanation.validity = validity
        explanation.verification_trace = self.engine._build_verification_trace(confidence)
        explanation.citation_entailment = entailment
        return explanation

    def get_provenance(self, provenance_id: str) -> dict[str, Any] | None:
        """Fetch a stored provenance record."""
        return self.provenance.get(provenance_id)

    # -- Grounding guard (Task 15) ------------------------------------------

    @staticmethod
    def _should_generate_answer(explanation: ExplanationResult) -> bool:
        """Return True only if every required grounding condition is met.

        Evaluates the retrieval and verification outputs *before* any LLM call.
        If any threshold is unmet the LLM must not be invoked, because
        generating from insufficient evidence risks fabricating a legal answer.
        """
        if not explanation.evidence:
            return False

        verification_status = explanation.validity.status
        if verification_status != "supported":
            return False

        if explanation.evidence_relevance.score < GUARD_MIN_RELEVANCE:
            return False

        if explanation.validity.sufficiency_score < GUARD_MIN_SUFFICIENCY:
            return False

        if explanation.confidence.score < GUARD_MIN_CONFIDENCE:
            return False

        return True

    def _grounding_guard_response(self, explanation: ExplanationResult) -> str:
        """Build the deterministic blocked response and emit the guard log."""
        n_evidence = len(explanation.evidence)
        log.info(
            "Grounding guard triggered",
            reason=self._grounding_guard_reason(explanation),
            confidence=round(explanation.confidence.score, 4),
            relevance=round(explanation.evidence_relevance.score, 4),
            sufficiency=round(explanation.validity.sufficiency_score, 4),
            verification_status=explanation.validity.status,
            node_count=n_evidence,
        )
        return GROUNDED_GUARD_ANSWER

    @staticmethod
    def _grounding_guard_reason(explanation: ExplanationResult) -> str:
        """Return a human-readable reason for the guard blocking generation."""
        if not explanation.evidence:
            return "no retrieved evidence"
        if explanation.validity.status != "supported":
            return f"verification status '{explanation.validity.status}'"
        if explanation.evidence_relevance.score < GUARD_MIN_RELEVANCE:
            return "evidence relevance below threshold"
        if explanation.validity.sufficiency_score < GUARD_MIN_SUFFICIENCY:
            return "evidence sufficiency below threshold"
        if explanation.confidence.score < GUARD_MIN_CONFIDENCE:
            return "confidence below threshold"
        return "unknown"

    def _system_prompt(self, explanation: ExplanationResult) -> str:
        return build_system_prompt(language=explanation.query_language)


# ---------------------------------------------------------------------------
# Default service wiring (data directory -> graph -> embeddings -> retriever)
# ---------------------------------------------------------------------------

_default_lock = threading.RLock()
_default_service: QueryService | None = None
_default_graph: InMemoryGraph | None = None
_default_store: QdrantStore | None = None
_default_embedding: EmbeddingService | None = None

# True while a corpus build owns ``_default_lock`` (including a cold-start
# build that outlived the startup prewarm window). The API layers check this to
# return a normal 503 JSON "warming" response instead of blocking on the lock
# or surfacing ECONNREFUSED/timeouts to the frontend.
_build_in_progress = False


def is_default_corpus_ready() -> bool:
    """True when the shared corpus has finished building and is queryable."""
    return _default_graph is not None


def corpus_build_in_progress() -> bool:
    """True when a corpus build owns the build lock but is not done yet."""
    return _build_in_progress and not is_default_corpus_ready()


def _embedding_cache_key(provider, dim: int) -> str:
    """Stable snapshot cache key: model + dim + sequence cap.

    Vectors only depend on the model, dimension and truncation cap, so a key
    change naturally invalidates the cache after any of those change.
    """
    raw = f"{provider.name}_{dim}d_{settings.EMBEDDING_MAX_SEQUENCE_LENGTH or 'max'}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def build_default_graph(data_dir: str | None = None) -> InMemoryGraph:
    """Import every hierarchy JSON into a fresh in-memory graph."""
    graph = InMemoryGraph()
    import_all(graph)
    return graph


def build_default_corpus() -> tuple[InMemoryGraph, QdrantStore, EmbeddingService]:
    """Build the graph + vector corpus over data/hierarchy once (thread-safe)."""
    log.info("qa_service.corpus_build_start")
    graph = build_default_graph()

    provider = get_provider(
        model_name=settings.EMBEDDING_MODEL,
        force_deterministic=settings.EMBEDDING_FORCE_DETERMINISTIC,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
        allow_fallback=settings.EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK,
        max_seq=settings.EMBEDDING_MAX_SEQUENCE_LENGTH,
    )
    embedding_service = EmbeddingService(
        provider=provider, batch_size=settings.EMBEDDING_BATCH_SIZE
    )
    log.info(
        "embedding.runtime_init",
        provider=provider.name,
        model=settings.EMBEDDING_MODEL,
        dimension=embedding_service.dim,
        force_deterministic=settings.EMBEDDING_FORCE_DETERMINISTIC,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
        device=getattr(provider, "device", "cpu"),
    )
    store = QdrantStore(
        dim=embedding_service.dim,
        in_memory=settings.QA_INDEX_IN_MEMORY,
        url=settings.QDRANT_URL or None,
        api_key=settings.QDRANT_API_KEY or None,
    )
    log.info("qa_service.collections_ensure_start", in_memory=settings.QA_INDEX_IN_MEMORY)
    store.ensure_collections()
    log.info("qa_service.collections_ensure_complete")
    log.info("qa_service.index_graph_start", nodes=len(graph.all_nodes()))
    hierarchy_dir = Path(__file__).resolve().parent.parent.parent / "data" / "hierarchy"
    canonical_ids = canonical_doc_ids(hierarchy_dir)
    indexer = HierarchyIndexer(graph, store, embedding_service)
    if settings.QA_INDEX_IN_MEMORY:
        # In-memory mode recreates its collections every startup, so a full
        # canonical (re)index keeps current behaviour exactly. Since the
        # semantic migration, CPU embedding is the dominant startup cost: a
        # snapshot of previously computed vectors is restored first and
        # ``index_graph`` skips any text whose hash is already fresh, so only
        # new/changed texts are re-embedded (V3.0 startup repair).
        cache_key = _embedding_cache_key(provider, embedding_service.dim)
        if settings.EMBEDDING_SNAPSHOT_ENABLED:
            restored = store.load_snapshot(cache_key)
            log.info("qa_service.snapshot_restored", points=restored, key=cache_key)
        index_started = time.perf_counter()
        indexer.index_graph(canonical_doc_ids=canonical_ids)
        log.info(
            "qa_service.index_graph_complete",
            elapsed_s=round(time.perf_counter() - index_started, 2),
        )
        if settings.EMBEDDING_SNAPSHOT_ENABLED:
            saved = store.save_snapshot(cache_key)
            log.info("qa_service.snapshot_saved", points=saved, key=cache_key)
    else:
        # Persistent mode keeps vectors across restarts: synchronize the
        # collections with the current corpus instead (insert missing, update
        # changed, delete stale, recreate on dimension change — Issue #13 V2.8).
        log.info("qa_service.sync_graph_start")
        indexer.sync_graph(recreate_on_dimension_mismatch=True)
        log.info("qa_service.sync_graph_complete")
    log.info(
        "qa_service.indexed",
        nodes=len(graph.all_nodes()),
        points=sum(store.count(c) for c in store.collections),
    )
    log.info("qa_service.corpus_build_complete")
    return graph, store, embedding_service


def get_default_corpus() -> tuple[InMemoryGraph, QdrantStore, EmbeddingService]:
    """Return the cached shared corpus used by both QA and document uploads.

    The corpus is built exactly once. A reentrant lock (``RLock``) plus the
    check-then-act pattern keeps concurrent first calls safe without ever
    nesting the lock across separate public functions.
    """
    global _default_graph, _default_store, _default_embedding, _build_in_progress
    if _default_graph is None:
        log.info("corpus.load.start")
        with _default_lock:
            if _default_graph is None:
                _build_in_progress = True
                try:
                    _default_graph, _default_store, _default_embedding = build_default_corpus()
                finally:
                    _build_in_progress = False
        log.info("corpus.load.complete")
    return _default_graph, _default_store, _default_embedding


def build_default_service() -> QueryService:
    """Build a fully wired QueryService over the project's data/hierarchy corpus."""
    graph, store, embedding_service = get_default_corpus()

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
    """Return a lazily-built, cached default QueryService (thread-safe).

    Never nests ``_default_lock``: the corpus is built first (under the corpus
    lock only), then the service is built using the already-cached corpus. The
    inner ``get_default_corpus()`` call inside ``build_default_service()``
    takes the fast path (corpus present), so no lock is acquired a second time
    in the same thread.
    """
    global _default_service
    if _default_service is None:
        get_default_corpus()
        with _default_lock:
            if _default_service is None:
                _default_service = build_default_service()
    return _default_service
