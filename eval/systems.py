"""Module 10, Part 5 — Retrieval systems and baselines.

Every system exposes the same :class:`RetrievalSystem` protocol so retrieval
metrics are computed identically:

- ``hhgr``       — Hybrid HHGR (dense + graph + hierarchy + explainability)
- ``dense``      — Dense-only multilingual vector retrieval
- ``bm25``       — Lexical BM25 keyword retrieval
- ``graph``      — Module 5 hybrid hierarchical graph retrieval (no vectors)
- ``naive_rag``  — Dense-only retrieval + naive LLM answer (no provenance)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from eval.corpus import Corpus
from src.embeddings.retriever import VectorRetriever
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from src.llm.llm import MockLLMClient
from src.llm.provenance import ExplanationResult, ProvenanceStore
from src.llm.service import QueryService
from src.retrieval.ranker import retrieve

_BM25_K1 = 1.5
_BM25_B = 0.75


@dataclass
class RankedHit:
    """Canonical ranked hit shared across all systems."""

    node_id: str
    score: float
    label: str = ""
    title: str = ""
    numbering: str = ""
    text: str = ""
    path: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    @classmethod
    def from_evidence(cls, ev: Any) -> RankedHit:
        return cls(
            node_id=ev.node_id,
            score=float(ev.final_score),
            label=ev.label,
            title=ev.title,
            numbering=ev.numbering,
            text=ev.text,
            path=list(ev.path),
            sources=list(ev.sources),
        )

    @classmethod
    def from_vector_hit(cls, hit: Any) -> RankedHit:
        payload = getattr(hit, "payload", {}) or {}
        return cls(
            node_id=hit.node_id,
            score=float(hit.score),
            label=payload.get("label", ""),
            title=payload.get("title", ""),
            numbering=payload.get("numbering", ""),
            text=payload.get("text", ""),
        )

    @classmethod
    def from_retrieval_result(cls, result: Any) -> RankedHit:
        return cls(
            node_id=result.node_id,
            score=float(result.score),
            label=result.label,
            title=result.title,
            numbering=result.numbering,
            text=result.text,
            path=list(result.path),
            sources=list(result.signals),
        )


@dataclass
class SystemResult:
    """The output of one retrieval system for one query."""

    system: str
    query: str
    hits: list[RankedHit] = field(default_factory=list)
    explanation: ExplanationResult | None = None
    answer: str = ""
    duration_ms: float = 0.0

    @property
    def retrieved_ids(self) -> list[str]:
        return [hit.node_id for hit in self.hits]

    def to_dict(self, k: int | None = None) -> dict[str, Any]:
        return {
            "system": self.system,
            "query": self.query,
            "retrieved_ids": self.retrieved_ids[:k] if k else self.retrieved_ids,
            "duration_ms": round(self.duration_ms, 3),
            "answer": self.answer,
        }


class RetrievalSystem(Protocol):
    name: str
    kind: str

    def run(self, query: str, top_k: int = 5) -> SystemResult:
        """Retrieve ranked hits for a query."""


class _BaseSystem:
    name = "base"
    kind = "base"

    def _measure(self, query: str, top_k: int, fn) -> SystemResult:
        start = time.perf_counter()
        result = fn(query, top_k)
        result.duration_ms = round((time.perf_counter() - start) * 1000.0, 3)
        return result


class HhgrSystem(_BaseSystem):
    """Full Hybrid HHGR: fused retrieval + explainability (+ optional LLM answer)."""

    name = "hhgr"
    kind = "hhgr"

    def __init__(
        self,
        engine: ExplainabilityEngine,
        llm: MockLLMClient | None = None,
        language: str | None = None,
    ) -> None:
        self.engine = engine
        self.language = language
        self._service: QueryService | None = None
        if llm is not None:
            self._service = QueryService(engine, llm, ProvenanceStore())

    def run(self, query: str, top_k: int = 5) -> SystemResult:
        def _inner(q: str, k: int) -> SystemResult:
            if self._service is not None:
                answer = self._service.answer(q, top_k=k, language=self.language)
                explanation = answer.explanation
                result = SystemResult(
                    system=self.name,
                    query=q,
                    explanation=explanation,
                    answer=answer.answer,
                )
            else:
                explanation = self.engine.explain(q, top_k=k, language=self.language)
                result = SystemResult(
                    system=self.name, query=q, explanation=explanation
                )
            result.hits = [RankedHit.from_evidence(ev) for ev in explanation.evidence]
            return result

        return self._measure(query, top_k, _inner)


class HybridSystem(_BaseSystem):
    """Fused dense + graph + hierarchy retrieval WITHOUT explainability enrichment.

    Used for the ``no_explainability`` ablation arm: the same signals are fused
    but no citations, hierarchy paths, or counter-authority detection are built.
    """

    name = "hybrid"
    kind = "hybrid"

    def __init__(
        self,
        retriever: VectorRetriever,
        weights: dict[str, float] | None = None,
        language: str | None = None,
    ) -> None:
        self.retriever = retriever
        self.weights = weights
        self.language = language

    def run(self, query: str, top_k: int = 5) -> SystemResult:
        def _inner(q: str, k: int) -> SystemResult:
            hits = self.retriever.hybrid_retrieve(
                q, top_k=k, language=self.language, weights=self.weights
            )
            return SystemResult(
                system=self.name,
                query=q,
                hits=[
                    RankedHit(
                        node_id=h.node_id,
                        score=float(h.score),
                        label=h.label,
                        title=h.title,
                        numbering="",
                        text=h.text,
                        sources=list(h.sources),
                    )
                    for h in hits
                ],
            )

        return self._measure(query, top_k, _inner)


class DenseSystem(_BaseSystem):
    """Dense-only multilingual vector retrieval."""

    name = "dense"
    kind = "dense"

    def __init__(self, retriever: VectorRetriever) -> None:
        self.retriever = retriever

    def run(self, query: str, top_k: int = 5) -> SystemResult:
        def _inner(q: str, k: int) -> SystemResult:
            hits = self.retriever.dense_search(q, top_k=k)
            return SystemResult(
                system=self.name,
                query=q,
                hits=[RankedHit.from_vector_hit(h) for h in hits],
            )

        return self._measure(query, top_k, _inner)


class GraphSystem(_BaseSystem):
    """Module 5 graph-only HHGR retrieval (no embeddings)."""

    name = "graph"
    kind = "graph"

    def __init__(self, graph: InMemoryGraph) -> None:
        self.graph = graph

    def run(self, query: str, top_k: int = 5) -> SystemResult:
        def _inner(q: str, k: int) -> SystemResult:
            results = retrieve(self.graph, q, top_k=k)
            return SystemResult(
                system=self.name,
                query=q,
                hits=[RankedHit.from_retrieval_result(r) for r in results],
            )

        return self._measure(query, top_k, _inner)


class Bm25System(_BaseSystem):
    """Classic BM25 lexical retrieval over the corpus node texts."""

    name = "bm25"
    kind = "bm25"

    def __init__(self, graph: InMemoryGraph) -> None:
        self._docs: list[tuple[str, list[str]]] = []
        doc_freq: dict[str, int] = {}
        total_len = 0
        for node in graph.all_nodes():
            node_id = node.get("node_id", "")
            if not node_id:
                continue
            tokens = _tokenize(f"{node.get('title', '')} {node.get('text', '')}")
            self._docs.append((node_id, tokens))
            total_len += len(tokens)
            for token in set(tokens):
                doc_freq[token] = doc_freq.get(token, 0) + 1
        self._doc_freq = doc_freq
        self._avgdl = (total_len / len(self._docs)) if self._docs else 1.0
        self._n = len(self._docs)

    def _score(self, query_tokens: set[str], tokens: list[str]) -> float:
        if not tokens:
            return 0.0
        n = self._n or 1
        avgdl = self._avgdl or 1.0
        dl = len(tokens)
        score = 0.0
        term_counts: dict[str, int] = {}
        for token in tokens:
            term_counts[token] = term_counts.get(token, 0) + 1
        for token in query_tokens:
            if token not in term_counts:
                continue
            tf = term_counts[token]
            df = self._doc_freq.get(token, 0)
            idf = max(0.0, (n - df + 0.5) / (df + 0.5) + 1.0)
            denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / avgdl)
            score += idf * (tf * (_BM25_K1 + 1)) / denom
        return score

    def run(self, query: str, top_k: int = 5) -> SystemResult:
        def _inner(q: str, k: int) -> SystemResult:
            query_tokens = set(_tokenize(q))
            scored = sorted(
                ((node_id, self._score(query_tokens, tokens)) for node_id, tokens in self._docs),
                key=lambda item: item[1],
                reverse=True,
            )
            hits = [
                RankedHit(node_id=node_id, score=round(score, 4))
                for node_id, score in scored[:k]
            ]
            return SystemResult(system=self.name, query=q, hits=hits)

        return self._measure(query, top_k, _inner)


class NaiveRagSystem(_BaseSystem):
    """Dense-only retrieval + naive LLM answer without provenance/explainability."""

    name = "naive_rag"
    kind = "naive_rag"

    def __init__(
        self,
        retriever: VectorRetriever,
        llm: MockLLMClient | None = None,
        max_context_chars: int = 1600,
    ) -> None:
        self.retriever = retriever
        self.llm = llm or MockLLMClient()
        self.max_context_chars = max_context_chars

    def run(self, query: str, top_k: int = 5) -> SystemResult:
        def _inner(q: str, k: int) -> SystemResult:
            hits = self.retriever.dense_search(q, top_k=k)
            passages: list[str] = []
            for i, hit in enumerate(hits, 1):
                payload = getattr(hit, "payload", {}) or {}
                text = payload.get("text", "") or ""
                if text:
                    passages.append(f"[{i}] {text[:400]}")
            user_prompt = "\n".join(passages)
            if len(user_prompt) > self.max_context_chars:
                user_prompt = user_prompt[: self.max_context_chars]
            user_prompt += f"\n\nQUESTION: {q}\n\n[SOURCE 1]\n[SOURCE 2]"
            messages = [
                {
                    "role": "system",
                    "content": "You are a legal assistant. Answer using only the passages.",
                },
                {"role": "user", "content": user_prompt},
            ]
            response = self.llm.complete(messages)
            return SystemResult(
                system=self.name,
                query=q,
                hits=[RankedHit.from_vector_hit(h) for h in hits],
                answer=response.text,
            )

        return self._measure(query, top_k, _inner)


def _tokenize(text: str) -> list[str]:
    """Lightweight lowercased tokenization for BM25."""
    tokens: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isalnum() or char in "_-'":
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return [token for token in tokens if token not in _STOPWORDS]


_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "does",
        "how",
        "under",
        "with",
        "that",
        "this",
    }
)


def build_systems(
    corpus: Corpus,
    weights: dict[str, float] | None = None,
    with_answers: bool = True,
) -> dict[str, RetrievalSystem]:
    """Instantiate the five retrieval systems over a corpus."""
    llm = MockLLMClient()
    systems: dict[str, RetrievalSystem] = {}
    if weights:
        from src.embeddings.retriever import normalize_weights

        corpus.engine.weights = normalize_weights(weights)
    systems["hhgr"] = HhgrSystem(corpus.engine, llm=llm if with_answers else None)
    systems["dense"] = DenseSystem(corpus.retriever)
    systems["bm25"] = Bm25System(corpus.graph)
    systems["graph"] = GraphSystem(corpus.graph)
    systems["naive_rag"] = NaiveRagSystem(corpus.retriever, llm=llm if with_answers else None)
    return systems
