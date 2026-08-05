"""Vector + graph hybrid retrieval.

Three retrieval signals are fused with configurable weights:
- dense:      Qdrant semantic (multilingual) similarity
- graph:      HHGR graph retrieval from Module 5 (text/citation/hierarchy/structural)
- hierarchy:  evidence propagated from dense matches to ancestors/descendants
              along PART_OF edges (structure-aware context)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.logging_config import get_logger
from src.embeddings.service import EmbeddingService
from src.embeddings.store import QdrantStore
from src.retrieval.context import propagate_hierarchy
from src.retrieval.ranker import retrieve

log = get_logger("retriever")

DEFAULT_HYBRID_WEIGHTS: dict[str, float] = {
    "dense": 0.40,
    "graph": 0.35,
    "hierarchy": 0.25,
}

_SIGNALS = ("dense", "graph", "hierarchy")


@dataclass
class VectorHit:
    """A single dense-similarity hit from Qdrant."""

    node_id: str
    collection: str
    score: float  # normalized to [0, 1]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridHit:
    """A fused retrieval result from dense + graph + hierarchy signals."""

    node_id: str
    score: float
    title: str = ""
    text: str = ""
    label: str = ""
    level: int = 0
    language: str = ""
    collection: str = ""
    dense_score: float = 0.0
    graph_score: float = 0.0
    hierarchy_score: float = 0.0
    sources: list[str] = field(default_factory=list)


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Normalize a weights mapping to sum 1.

    When ``weights`` is None the module defaults are used. When provided, the
    mapping is used exactly (missing signals get weight 0) and normalized so
    the sum equals 1.
    """
    if weights:
        merged = {sig: float(weights.get(sig, 0.0)) for sig in _SIGNALS}
    else:
        merged = {sig: float(DEFAULT_HYBRID_WEIGHTS[sig]) for sig in _SIGNALS}
    total = sum(merged.values()) or 1.0
    return {k: v / total for k, v in merged.items()}


def _normalize_cosine(score: float) -> float:
    """Map cosine similarity in [-1, 1] to [0, 1]."""
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


class VectorRetriever:
    """Fuses dense vector search with graph and hierarchy signals."""

    def __init__(
        self,
        graph,
        store: QdrantStore,
        service: EmbeddingService,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.graph = graph
        self.store = store
        self.service = service
        self.weights = normalize_weights(weights)

    # -- dense ------------------------------------------------------------

    def dense_search(
        self,
        query: str,
        collections: list[str] | None = None,
        top_k: int = 10,
        language: str | None = None,
        query_language: str | None = None,
    ) -> list[VectorHit]:
        """Multilingual dense similarity search across collections.

        ``query_language`` is a hint only — multilingual models embed any language
        into a shared space, so cross-lingual queries work without translation.
        ``language`` optionally filters indexed payloads by document language.
        """
        vector = self.service.embed_query(query)
        names = collections or self.store.collections
        hits = self.store.search_multiple(
            names, vector, top_k=top_k, language=language
        )
        return [
            VectorHit(
                node_id=h["node_id"],
                collection=h["collection"],
                score=_normalize_cosine(h["score"]),
                payload=h["payload"],
            )
            for h in hits
        ]

    def cross_lingual_search(self, query: str, **kwargs) -> list[VectorHit]:
        """Alias emphasizing cross-lingual capability (English -> Hindi, etc.)."""
        return self.dense_search(query, **kwargs)

    # -- graph (HHGR) -----------------------------------------------------

    def graph_retrieval(self, query: str, top_k: int = 10) -> dict[str, float]:
        """Run Module 5 HHGR graph retrieval; return {node_id: score}."""
        results = retrieve(self.graph, query, top_k=top_k)
        return {r.node_id: r.score for r in results}

    # -- hierarchy --------------------------------------------------------

    def hierarchy_retrieval(
        self,
        query: str,
        top_k: int = 10,
        collections: list[str] | None = None,
        language: str | None = None,
    ) -> dict[str, float]:
        """Structure-aware retrieval.

        Dense matches seed evidence propagation over PART_OF edges, so a matched
        section also surfaces its chapter, and vice versa. Returns
        {node_id: evidence strength in [0, 1]}.
        """
        seeds = self.dense_search(
            query, collections=collections, top_k=top_k, language=language
        )
        seed_ids = [h.node_id for h in seeds if h.node_id]
        return propagate_hierarchy(self.graph, seed_ids) if seed_ids else {}

    # -- hybrid -----------------------------------------------------------

    def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 10,
        weights: dict[str, float] | None = None,
        collections: list[str] | None = None,
        language: str | None = None,
    ) -> list[HybridHit]:
        """Fuse dense + graph + hierarchy signals into ranked HybridHits."""
        w = normalize_weights(weights or self.weights)

        dense_hits = self.dense_search(
            query, collections=collections, top_k=top_k, language=language
        )
        dense: dict[str, float] = {}
        dense_payload: dict[str, dict[str, Any]] = {}
        for hit in dense_hits:
            dense[hit.node_id] = max(dense.get(hit.node_id, 0.0), hit.score)
            dense_payload.setdefault(hit.node_id, hit.payload)

        graph_scores = self.graph_retrieval(query, top_k=top_k)
        hierarchy_scores = self.hierarchy_retrieval(
            query, top_k=top_k, collections=collections, language=language
        )

        candidates: set[str] = set(dense) | set(graph_scores) | set(hierarchy_scores)

        results: list[HybridHit] = []
        for node_id in candidates:
            signals = {
                "dense": dense.get(node_id, 0.0),
                "graph": graph_scores.get(node_id, 0.0),
                "hierarchy": hierarchy_scores.get(node_id, 0.0),
            }
            total = sum(w.get(sig, 0.0) * signals[sig] for sig in _SIGNALS)

            payload = dense_payload.get(node_id, {})
            node = self.graph.get_node(node_id)
            title = (node or payload).get("title", "")
            text = (node or payload).get("text", "")
            label = (node or {}).get("label", payload.get("node_type", ""))
            level = node.get(
                "level", node.get("hierarchy_level", payload.get("level", 0))
            ) if node else payload.get("level", 0)
            lang = node.get("language") if node else payload.get("language", "")
            if not lang:
                lang = payload.get("language", "")

            sources = [sig for sig in _SIGNALS if signals[sig] > 0.0]
            results.append(
                HybridHit(
                    node_id=node_id,
                    score=round(total, 6),
                    title=title,
                    text=text,
                    label=label,
                    level=level,
                    language=lang,
                    collection=payload.get("collection", ""),
                    dense_score=signals["dense"],
                    graph_score=signals["graph"],
                    hierarchy_score=signals["hierarchy"],
                    sources=sources,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        top = results[:top_k]
        log.info(
            "retrieval.hybrid_complete",
            query=query,
            candidates=len(candidates),
            returned=len(top),
        )
        return top
