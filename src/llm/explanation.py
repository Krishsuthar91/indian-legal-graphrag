"""Explainability engine — turns retrieval into a structured, verifiable explanation.

Reuses the existing layers:
- Module 5 HHGR (``retrieve``, ``propagate_hierarchy``, ``get_ancestor_chain``)
- Module 6 vector retrieval (``VectorRetriever.dense_search`` / ``hybrid_retrieve``)

Produces: retrieval provenance, a graph reasoning chain, hierarchy paths, source
citations, counter-authority detection, confidence scoring, and validity flags.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.embeddings.retriever import DEFAULT_HYBRID_WEIGHTS
from src.knowledge_graph.traversal import get_children
from src.llm.provenance import (
    Confidence,
    CounterAuthority,
    Evidence,
    ExplanationResult,
    HierarchyPath,
    HierarchyPathEntry,
    ReasoningStep,
    RetrievalSummary,
    SourceCitation,
    Validity,
)
from src.retrieval.context import get_ancestor_chain, propagate_hierarchy
from src.retrieval.intent import adaptive_top_k, detect_intent
from src.retrieval.query import parse_query
from src.retrieval.query_expansion import available_section_keys, expand_query
from src.retrieval.ranker import retrieve
from src.retrieval.scorer import (
    citation_frequency,
    citation_score,
    keyword_overlap,
    text_score,
)

log = get_logger("explanation")

SNIPPET_CHARS = 240
MAX_PATHS = 6
DEDUP_TEXT_SIMILARITY = 0.95

# Ranking signals (Phase 3): keyword overlap and citation frequency are fused
# with the three existing signals into a separate ranking score used ONLY for
# ordering evidence. It is independent of DEFAULT_HYBRID_WEIGHTS so reported
# per-signal scores and confidence are preserved.
RANKING_SIGNALS: tuple[str, ...] = (
    "dense", "graph", "hierarchy", "keyword", "citation",
)

DEFAULT_RANKING_WEIGHTS: dict[str, float] = {
    "dense": 0.35,
    "graph": 0.25,
    "hierarchy": 0.15,
    "keyword": 0.15,
    "citation": 0.10,
}

# Phase 3 C4: canonical hierarchy-path preference multipliers. Derived purely
# from a node's label (O(1), no graph traversal). Legal leaf nodes are boosted,
# generic wrappers/documents are demoted, everything else is neutral.
_CHAIN_RELEVANCE: dict[str, float] = {
    "section": 1.10,
    "clause": 1.08,
    "article": 1.07,
    "rule": 1.06,
    "chapter": 1.03,
    "part": 1.02,
    "act": 1.00,
    "document": 0.95,
    "wrapper": 0.90,
}

# Phase 3 C5: the adaptive retrieval pipeline runs these stages in order.
# Stages 1-10 are retrieval (intent, adaptive budget, Phase 4 legal query
# expansion, dense, graph, hierarchy, ranking), 11 resolves evidence, 12 builds
# provenance in this engine, and 13 (LLM generation or the retrieval guard)
# runs in the QA service. Exposed as diagnostics for offline research
# evaluation only.
RETRIEVAL_PIPELINE_STAGES: tuple[str, ...] = (
    "intent_detection",
    "adaptive_top_k",
    "legal_expansion",
    "dense_retrieval",
    "graph_retrieval",
    "hierarchy_retrieval",
    "keyword_ranking",
    "citation_ranking",
    "canonical_hierarchy_preference",
    "evidence_deduplication",
    "evidence_resolution",
    "provenance_generation",
    "llm_answer_generation",
)


def retrieval_pipeline_stages(expansion_enabled: bool) -> list[str]:
    """Diagnostic stage list for a run.

    ``legal_expansion`` only runs when query expansion is enabled, so it is
    omitted from the reported pipeline otherwise.
    """
    stages = list(RETRIEVAL_PIPELINE_STAGES)
    if not expansion_enabled:
        stages.remove("legal_expansion")
    return stages


def _default_ranking_weights() -> dict[str, float]:
    """Ranking weights from settings (mirror DEFAULT_RANKING_WEIGHTS)."""
    return {
        "dense": settings.RANKING_WEIGHT_DENSE,
        "graph": settings.RANKING_WEIGHT_GRAPH,
        "hierarchy": settings.RANKING_WEIGHT_HIERARCHY,
        "keyword": settings.RANKING_WEIGHT_KEYWORD,
        "citation": settings.RANKING_WEIGHT_CITATION,
    }


def _normalize_ranking_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize a ranking-weight mapping to sum 1 (missing signals become 0)."""
    merged = {sig: float(weights.get(sig, 0.0)) for sig in RANKING_SIGNALS}
    total = sum(merged.values()) or 1.0
    return {k: v / total for k, v in merged.items()}


def _text_similarity(a: str, b: str) -> float:
    """Dice coefficient over character bigrams, in [0, 1].

    Whitespace is collapsed so paragraph/line breaks do not reduce similarity.
    Used to detect near-identical evidence texts during deduplication.
    """
    a = " ".join((a or "").split())
    b = " ".join((b or "").split())
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    bigrams_a = set(a[i : i + 2] for i in range(len(a) - 1))
    bigrams_b = set(b[i : i + 2] for i in range(len(b) - 1))
    if not bigrams_a or not bigrams_b:
        return 0.0
    overlap = len(bigrams_a & bigrams_b)
    return 2.0 * overlap / (len(bigrams_a) + len(bigrams_b))

# Counter-authority markers: phrase -> human-readable reason.
_COUNTER_MARKERS: dict[str, list[str]] = {
    "overruled": ["overruled", "overrule"],
    "superseded": ["superseded", "supersede"],
    "repealed": ["repealed"],
    "overridden": ["overridden"],
    "invalid": ["void ab initio", "declared void", "not enforceable", "invalid"],
    "inoperative": ["inoperative", "no longer operative"],
    "not_applicable": ["does not apply", "shall not apply", "not applicable"],
}

_STRONG_MARKERS = {"overruled", "superseded", "repealed", "overridden"}

_MARKER_REASONS: dict[str, str] = {
    "overruled": "statement appears to be overruled by a later authority",
    "superseded": "statement may be superseded by a later authority",
    "repealed": "statement references an authority that appears repealed",
    "overridden": "statement may be overridden by a later authority",
    "invalid": "statement is declared invalid, void, or unenforceable",
    "inoperative": "statement is marked inoperative or no longer operative",
    "not_applicable": "statement is expressly declared not to apply",
}


@dataclass
class _Signal:
    """Raw per-signal scores for one candidate node."""

    dense: float = 0.0
    graph: float = 0.0
    hierarchy: float = 0.0
    keyword: float = 0.0
    citation: float = 0.0

    @property
    def final(self) -> float:
        return self.dense + self.graph + self.hierarchy


class ExplainabilityEngine:
    """Computes a complete, transparent explanation for a query."""

    def __init__(
        self,
        graph,
        vector_retriever=None,
        weights: dict[str, float] | None = None,
        confidence_threshold: float | None = None,
        adaptive: bool | None = None,
        top_k_easy: int | None = None,
        top_k_medium: int | None = None,
        top_k_complex: int | None = None,
        ranking_weights: dict[str, float] | None = None,
        expansion_enabled: bool | None = None,
    ) -> None:
        self.graph = graph
        self.vr = vector_retriever
        self.weights = weights or dict(DEFAULT_HYBRID_WEIGHTS)
        self.threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.QA_CONFIDENCE_THRESHOLD
        )
        self.adaptive = settings.QA_ADAPTIVE_TOP_K if adaptive is None else adaptive
        self.top_k_easy = settings.QA_TOP_K_EASY if top_k_easy is None else top_k_easy
        self.top_k_medium = (
            settings.QA_TOP_K_MEDIUM if top_k_medium is None else top_k_medium
        )
        self.top_k_complex = (
            settings.QA_TOP_K_COMPLEX if top_k_complex is None else top_k_complex
        )
        self.ranking_weights = _normalize_ranking_weights(
            ranking_weights or _default_ranking_weights()
        )
        self.expansion_enabled = (
            settings.QA_QUERY_EXPANSION_ENABLED
            if expansion_enabled is None
            else expansion_enabled
        )
        self._corpus_section_keys: set[str] | None = None

    def _corpus_sections(self) -> set[str]:
        """Section keys present in the indexed corpus (cached per engine).

        Verified expansion references are only injected when their section
        exists here, so expansion never points retrieval at sections the index
        cannot return. ``None`` when the corpus is unknown -> expansion falls
        back to concept terms only (all references omitted).
        """
        if self._corpus_section_keys is None:
            try:
                nodes = self.graph.all_nodes()
            except (AttributeError, TypeError):
                nodes = []
            self._corpus_section_keys = available_section_keys(nodes)
        return self._corpus_section_keys

    # -- public API --------------------------------------------------------

    def explain(
        self,
        query: str,
        top_k: int | None = None,
        language: str | None = None,
    ) -> ExplanationResult:
        """Run retrieval and assemble a full ExplanationResult for the query.

        When ``top_k`` is omitted and adaptive retrieval is enabled, the query
        intent decides the evidence budget. An explicit ``top_k`` always wins.
        """
        parsed = parse_query(query)
        latencies: dict[str, float] = {}
        _start = time.perf_counter()
        intent = detect_intent(parsed)
        if top_k is None and self.adaptive:
            budget = adaptive_top_k(
                intent,
                easy=self.top_k_easy,
                medium=self.top_k_medium,
                complex=self.top_k_complex,
            )
            strategy = "adaptive"
            adaptive_k = budget
        else:
            budget = top_k if top_k is not None else 5
            strategy = "fixed"
            adaptive_k = None
        latencies["intent_detection"] = self._ms_since(_start)
        chain: list[ReasoningStep] = []

        # 1. Query parsing
        chain.append(
            ReasoningStep(
                step=1,
                kind="query_parse",
                description="Parsed the query into keywords and legal references.",
                detail={
                    "keywords": parsed.keywords,
                    "section_refs": parsed.section_refs,
                    "intent": intent,
                },
            )
        )

        # 1b. Phase 4: deterministic legal query expansion. Runs AFTER intent
        # detection so the expanded section references can never change the
        # classified intent or its adaptive budget. When active, the expanded
        # search text drives dense + graph retrieval and the re-parsed query
        # (with concept terms + verified section refs) drives ranking, evidence
        # resolution and confidence.
        _start = time.perf_counter()
        expansion = expand_query(
            query,
            enabled=self.expansion_enabled,
            available_sections=self._corpus_sections(),
        )
        search_text = expansion.build_search_text(query)
        effective_parsed = parse_query(search_text) if expansion.active else parsed
        latencies["legal_expansion"] = self._ms_since(_start)
        if expansion.active:
            expansion_description = (
                f"Expanded {len(expansion.matched_phrases)} phrase(s) into "
                f"{len(expansion.expanded_concepts)} legal concept(s) and "
                f"{len(expansion.section_refs)} verified section reference(s) "
                f"present in the corpus; omitted {len(expansion.section_refs_omitted)} "
                f"reference(s) not present in the indexed corpus."
            )
        else:
            expansion_description = (
                "Legal query expansion matched no legal concept phrases."
            )
        chain.append(
            ReasoningStep(
                step=2,
                kind="query_expansion",
                description=expansion_description,
                detail={
                    "enabled": expansion.enabled,
                    "active": expansion.active,
                    "matched_phrases": expansion.matched_phrases,
                    "expanded_terms": expansion.expanded_terms,
                    "expanded_concepts": expansion.expanded_concepts,
                    "section_refs": expansion.section_refs,
                    "section_refs_considered": expansion.section_refs_considered,
                    "section_refs_available": expansion.section_refs_available,
                    "section_refs_omitted": expansion.section_refs_omitted,
                    "reason": expansion.reason,
                },
            )
        )

        # 2. Dense (multilingual) retrieval
        _start = time.perf_counter()
        dense_ids: list[str] = []
        if self.vr is not None:
            for hit in self.vr.dense_search(search_text, top_k=budget, language=language):
                if hit.node_id:
                    dense_ids.append(hit.node_id)
        latencies["dense_retrieval"] = self._ms_since(_start)
        chain.append(
            ReasoningStep(
                step=3,
                kind="dense",
                description=(
                    f"Semantic vector search returned {len(dense_ids)} candidate(s)."
                ),
                node_ids=dense_ids[:budget],
                detail={"count": len(dense_ids)},
            )
        )

        # 3. Graph (HHGR) retrieval
        _start = time.perf_counter()
        graph_results = retrieve(self.graph, search_text, top_k=budget)
        graph_map = {r.node_id: r for r in graph_results}
        latencies["graph_retrieval"] = self._ms_since(_start)
        chain.append(
            ReasoningStep(
                step=4,
                kind="graph",
                description=(
                    f"Hybrid hierarchical graph retrieval returned "
                    f"{len(graph_results)} candidate(s)."
                ),
                node_ids=list(graph_map)[:budget],
                detail={
                    "seeds": [r.node_id for r in graph_results if r.is_seed],
                    "count": len(graph_results),
                },
            )
        )

        # 4. Hierarchy propagation over graph-present dense seeds
        _start = time.perf_counter()
        seed_ids = [nid for nid in dense_ids if self.graph.get_node(nid) is not None]
        propagated = propagate_hierarchy(self.graph, seed_ids) if seed_ids else {}
        latencies["hierarchy_retrieval"] = self._ms_since(_start)
        chain.append(
            ReasoningStep(
                step=5,
                kind="hierarchy",
                description=(
                    f"Hierarchical evidence propagated from {len(seed_ids)} seed(s) "
                    f"to {len(propagated)} ancestor/descendant node(s)."
                ),
                node_ids=list(propagated)[:budget],
                detail={"seed_ids": seed_ids, "count": len(propagated)},
            )
        )

        # 5. Fusion + ranking
        _start = time.perf_counter()
        signals, candidates = self._fuse(
            search_text, top_k=budget, language=language, graph_results=graph_results,
            propagated=propagated, parsed=effective_parsed,
        )
        latencies["fusion"] = self._ms_since(_start)

        _start = time.perf_counter()
        rank: dict[str, float] = {}
        chain_info: dict[str, dict[str, Any]] = {}
        for nid in candidates:
            sig = signals[nid]
            node = self.graph.get_node(nid)
            multiplier = self._chain_relevance(node)
            rank[nid] = self._rank(sig, multiplier=multiplier)
            chain_info[nid] = {
                "chain_relevance": multiplier,
                "effective_hierarchy_score": round(sig.hierarchy * multiplier, 4),
                "ranking_reason": self._chain_reason(node),
            }
        ranked_ids = sorted(candidates, key=lambda n: (-rank[n], n))[:budget]
        ranking_breakdown = {
            nid: {
                "dense": round(signals[nid].dense, 4),
                "graph": round(signals[nid].graph, 4),
                "hierarchy": round(signals[nid].hierarchy, 4),
                "keyword": round(signals[nid].keyword, 4),
                "citation": round(signals[nid].citation, 4),
                "rank": round(rank[nid], 4),
            }
            for nid in ranked_ids
        }
        latencies["ranking"] = self._ms_since(_start)
        ranked_before_dedup = len(ranked_ids)

        # 5b. Deduplicate ranked evidence before evidence construction.
        _start = time.perf_counter()
        ranked_ids, duplicate_details = self._dedupe_evidence(
            ranked_ids, signals, effective_parsed
        )
        duplicates_removed = len(duplicate_details)
        # C4 diagnostics for the retained (surviving) nodes only.
        chain_ranking = {nid: chain_info[nid] for nid in ranked_ids}
        latencies["deduplication"] = self._ms_since(_start)

        chain.append(
            ReasoningStep(
                step=6,
                kind="fusion",
                description=(
                    f"Fused dense/graph/hierarchy signals into {len(ranked_ids)} "
                    f"ranked evidence node(s) using weights "
                    f"{self._weights_label()}."
                ),
                node_ids=ranked_ids,
                detail={
                    "weights": self.weights,
                    "ranking_weights": self.ranking_weights,
                    "intent": intent,
                    "strategy": strategy,
                    "top_k": budget,
                    "candidates": len(candidates),
                    "returned": len(ranked_ids),
                    "duplicates_removed": duplicates_removed,
                },
            )
        )

        _start = time.perf_counter()
        evidence = self._build_evidence(ranked_ids, signals, effective_parsed)
        latencies["evidence_resolution"] = self._ms_since(_start)
        paths = self._build_paths(evidence)
        citations = self._build_citations(evidence)
        counter = self._detect_counter_authorities(evidence)
        confidence = self._score_confidence(evidence, effective_parsed)
        validity = self._assess_validity(evidence, counter, confidence)

        chain.append(
            ReasoningStep(
                step=7,
                kind="verification",
                description=(
                    f"Confidence {confidence.score:.2f} ({confidence.label}); "
                    f"valid={validity.is_valid}; "
                    f"counter-authorities detected: {len(counter)}."
                ),
                detail={"confidence": confidence.score, "validity": validity.is_valid},
            )
        )

        retrieval_latency_ms = round(
            sum(
                latencies[k]
                for k in (
                    "intent_detection",
                    "legal_expansion",
                    "dense_retrieval",
                    "graph_retrieval",
                    "hierarchy_retrieval",
                    "fusion",
                )
            ),
            3,
        )
        ranking_latency_ms = round(
            latencies["ranking"] + latencies["deduplication"], 3
        )
        total_retrieval_latency_ms = round(
            retrieval_latency_ms
            + ranking_latency_ms
            + latencies["evidence_resolution"],
            3,
        )

        summary = RetrievalSummary(
            keywords=parsed.keywords,
            section_refs=parsed.section_refs,
            dense_hits=len(dense_ids),
            graph_hits=len(graph_results),
            hierarchy_propagated=len(propagated),
            candidates=len(candidates),
            returned=len(ranked_ids),
            intent=intent,
            adaptive_top_k=adaptive_k,
            retrieval_strategy=strategy,
            ranking_breakdown=ranking_breakdown,
            duplicates_removed=duplicates_removed,
            duplicate_details=duplicate_details,
            chain_ranking=chain_ranking,
            retrieval_pipeline=retrieval_pipeline_stages(self.expansion_enabled),
            query_intent=intent,
            retrieved_candidates=len(candidates),
            ranked_candidates=ranked_before_dedup,
            ranking_weights=dict(self.ranking_weights),
            retrieval_latency_ms=retrieval_latency_ms,
            ranking_latency_ms=ranking_latency_ms,
            total_retrieval_latency_ms=total_retrieval_latency_ms,
            latency_breakdown={k: round(v, 3) for k, v in latencies.items()},
            query_expansion_enabled=expansion.enabled,
            expanded_terms=expansion.expanded_terms,
            expanded_concepts=expansion.expanded_concepts,
            expansion_reason=expansion.reason,
            section_refs_considered=expansion.section_refs_considered,
            section_refs_available=expansion.section_refs_available,
            section_refs_omitted=expansion.section_refs_omitted,
        )

        log.info(
            "explanation.complete",
            query=query,
            candidates=len(candidates),
            returned=len(ranked_ids),
            duplicates_removed=duplicates_removed,
            confidence=confidence.score,
            intent=intent,
            strategy=strategy,
            retrieval_latency_ms=retrieval_latency_ms,
            total_retrieval_latency_ms=total_retrieval_latency_ms,
        )

        return ExplanationResult(
            query=query,
            query_language=parsed.language,
            retrieval=summary,
            evidence=evidence,
            reasoning_chain=chain,
            hierarchy_paths=paths,
            citations=citations,
            counter_authorities=counter,
            confidence=confidence,
            validity=validity,
            retrieval_weights=dict(self.weights),
        )

    # -- fusion ------------------------------------------------------------

    def _fuse(
        self,
        query: str,
        top_k: int,
        language: str | None,
        graph_results,
        propagated: dict[str, float],
        parsed,
    ) -> tuple[dict[str, _Signal], set[str]]:
        """Compute per-signal scores for the candidate set."""
        signals: dict[str, _Signal] = {}
        graph_scores = {r.node_id: r.score for r in graph_results}

        if self.vr is not None:
            hybrid = self.vr.hybrid_retrieve(
                query, top_k=top_k, language=language, weights=self.weights
            )
            for hit in hybrid:
                sig = signals.setdefault(hit.node_id, _Signal())
                sig.dense = max(sig.dense, hit.dense_score)
                sig.graph = max(sig.graph, hit.graph_score)
                sig.hierarchy = max(sig.hierarchy, hit.hierarchy_score)
        else:
            # Graph-only fallback: Module 5 score + propagated hierarchy strength.
            for node_id, g_score in graph_scores.items():
                sig = signals.setdefault(node_id, _Signal())
                sig.graph = g_score
                sig.hierarchy = propagated.get(node_id, 0.0)

        # Scale fused scores back into [0,1] via the configured weights.
        w = self.weights
        total = w.get("dense", 0.0) + w.get("graph", 0.0) + w.get("hierarchy", 0.0) or 1.0
        for node_id, sig in signals.items():
            sig.dense *= w.get("dense", 0.0) / total
            sig.graph *= w.get("graph", 0.0) / total
            sig.hierarchy *= w.get("hierarchy", 0.0) / total

        # Keyword-overlap and citation-frequency signals (both in [0, 1]).
        self._fill_ranking_signals(signals, parsed)

        return signals, set(signals)

    def _fill_ranking_signals(
        self, signals: dict[str, _Signal], parsed
    ) -> None:
        """Fill keyword-overlap + citation-frequency signals for every candidate."""
        citation_counts: dict[str, float] = {}
        max_citations = 0.0
        for node_id, sig in signals.items():
            node = self.graph.get_node(node_id)
            if node:
                sig.keyword = keyword_overlap(node, parsed)
            count = citation_frequency(self.graph, node_id)
            citation_counts[node_id] = count
            max_citations = max(max_citations, count)
        if max_citations > 0:
            for node_id, count in citation_counts.items():
                signals[node_id].citation = count / max_citations

    def _rank(self, sig: _Signal, multiplier: float = 1.0) -> float:
        """Weighted 5-signal score used only for ordering retrieved evidence.

        ``multiplier`` is the canonical hierarchy-path preference (C4): it
        scales ONLY the hierarchy term so legal leaf nodes (Section/Clause/
        Article/Rule) are preferred over wrappers, documents, and intermediate
        hierarchy nodes. Reported per-signal scores, ``final``, confidence and
        provenance are untouched — this value is used solely for ordering.
        """
        w = self.ranking_weights
        return (
            w.get("dense", 0.0) * sig.dense
            + w.get("graph", 0.0) * sig.graph
            + w.get("hierarchy", 0.0) * sig.hierarchy * multiplier
            + w.get("keyword", 0.0) * sig.keyword
            + w.get("citation", 0.0) * sig.citation
        )

    def _chain_relevance(self, node) -> float:
        """Canonical hierarchy-path preference multiplier for a node's label.

        O(1) — a plain dict lookup on the node's label, no graph traversal and
        no recursion. Unknown or missing labels are neutral (1.0).
        """
        if not node:
            return 1.0
        label = str(node.get("label", "")).strip().lower()
        return _CHAIN_RELEVANCE.get(label, 1.0)

    def _chain_reason(self, node) -> str:
        """Ranking reason for a node's canonical label (e.g. canonical:section)."""
        if not node:
            return "unknown"
        label = str(node.get("label", "")).strip().lower()
        if label in _CHAIN_RELEVANCE:
            return f"canonical:{label}"
        return "unknown"

    def _dedupe_evidence(
        self,
        ranked_ids: list[str],
        signals: dict[str, _Signal],
        parsed=None,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Remove duplicate ranked evidence, keeping the highest-ranked copy.

        ``ranked_ids`` is ordered best-first, so the first occurrence of a
        duplicate is the highest-ranked one and is always retained; later
        occurrences are dropped. Retention order of the survivors is unchanged.

        Three duplicate criteria are checked, in this order:
        - ``duplicate_node_id``: the same ranked node id appears again;
        - ``duplicate_path``: the resolved hierarchy path (root -> resolved
          node) was already retained, e.g. an empty-text ancestor wrapper and
          the text-bearing descendant it resolves to both rank;
        - ``duplicate_text``: resolved text is near-identical (Dice coefficient
          >= DEDUP_TEXT_SIMILARITY) to an already-retained node's text.

        Returns ``(deduplicated_ids, details)`` where each detail entry carries
        ``removed_node``, ``duplicate_reason`` and ``retained_node``.
        """
        retained: list[str] = []
        details: list[dict[str, Any]] = []
        seen_node_ids: dict[str, str] = {}
        seen_paths: dict[tuple[str, ...], str] = {}
        seen_texts: list[tuple[str, str]] = []

        for node_id in ranked_ids:
            node, resolved_id = self._resolve_evidence_node(node_id, parsed)

            reason: str | None = None
            if node_id in seen_node_ids:
                reason = "duplicate_node_id"
                retained_node = seen_node_ids[node_id]
            elif node is not None:
                path = tuple(self._root_to_node(resolved_id))
                if path in seen_paths:
                    reason = "duplicate_path"
                    retained_node = seen_paths[path]
                else:
                    text = (node.get("text") or "").strip()
                    for prev_text, prev_node in seen_texts:
                        if _text_similarity(text, prev_text) >= DEDUP_TEXT_SIMILARITY:
                            reason = "duplicate_text"
                            retained_node = prev_node
                            break

            if reason is not None:
                details.append(
                    {
                        "removed_node": node_id,
                        "duplicate_reason": reason,
                        "retained_node": retained_node,
                    }
                )
                continue

            retained.append(node_id)
            seen_node_ids[node_id] = node_id
            if node is not None:
                seen_paths[tuple(self._root_to_node(resolved_id))] = node_id
                text = (node.get("text") or "").strip()
                if text:
                    seen_texts.append((text, node_id))

        return retained, details

    def _weights_label(self) -> str:
        return ", ".join(f"{k}={v:.2f}" for k, v in sorted(self.weights.items()))

    @staticmethod
    def _ms_since(start: float) -> float:
        """Milliseconds elapsed since ``start`` (monotonic clock)."""
        return (time.perf_counter() - start) * 1000.0

    # -- evidence assembly -------------------------------------------------

    def _build_evidence(
        self,
        ranked_ids: list[str],
        signals: dict[str, _Signal],
        parsed=None,
    ) -> list[Evidence]:
        evidence: list[Evidence] = []
        seen: set[str] = set()
        for node_id in ranked_ids:
            node, resolved_id = self._resolve_evidence_node(node_id, parsed)
            if not node:
                continue
            if resolved_id in seen:
                continue
            seen.add(resolved_id)
            text = node.get("text", "") or ""
            sig = signals[node_id]
            evidence.append(
                Evidence(
                    node_id=resolved_id,
                    title=node.get("title", ""),
                    text=text,
                    label=node.get("label", ""),
                    numbering=node.get("numbering", ""),
                    collection="",
                    language=node.get("language", "") or "",
                    level=int(node.get("hierarchy_level", node.get("level", 0))),
                    dense_score=round(sig.dense, 4),
                    graph_score=round(sig.graph, 4),
                    hierarchy_score=round(sig.hierarchy, 4),
                    final_score=round(sig.final, 4),
                    sources=self._active_signals(sig),
                    path=self._root_to_node(resolved_id),
                    snippet=text[:SNIPPET_CHARS],
                )
            )
        return evidence

    def _resolve_evidence_node(self, node_id: str, parsed) -> tuple[dict | None, str]:
        """Return the node to surface as evidence for ``node_id``.

        If the ranked node itself carries text it is used as-is. Otherwise the
        descendant subtree is walked breadth-first and the text-bearing
        descendant with the strongest lexical/citation match against the parsed
        query is chosen — e.g. a Section supplies the text for an otherwise
        empty-text parent Document node. The ranked node's fused scores are kept.
        """
        node = self.graph.get_node(node_id)
        if not node:
            return None, node_id
        if (node.get("text") or "").strip():
            return node, node_id

        best: dict | None = None
        best_id: str = node_id
        best_key: tuple[float, float, int] | None = None
        visited: set[str] = {node_id}
        frontier = [node_id]
        while frontier:
            nxt: list[str] = []
            for current in frontier:
                for child in get_children(self.graph, current):
                    child_id = child["node_id"]
                    if child_id in visited:
                        continue
                    visited.add(child_id)
                    child_node = self.graph.get_node(child_id)
                    if not child_node:
                        continue
                    if (child_node.get("text") or "").strip():
                        if parsed is not None:
                            key = (
                                text_score(child_node, parsed),
                                citation_score(child_node, parsed),
                                len(child_node.get("text", "")),
                            )
                        else:
                            key = (0.0, 0.0, len(child_node.get("text", "")))
                        if best_key is None or key > best_key:
                            best = child_node
                            best_id = child_node["node_id"]
                            best_key = key
                    nxt.append(child_id)
            frontier = nxt
        return best, best_id

    @staticmethod
    def _active_signals(sig: _Signal) -> list[str]:
        active = []
        if sig.dense > 0.0:
            active.append("dense")
        if sig.graph > 0.0:
            active.append("graph")
        if sig.hierarchy > 0.0:
            active.append("hierarchy")
        return active

    def _root_to_node(self, node_id: str) -> list[str]:
        chain = get_ancestor_chain(self.graph, node_id)
        return [a["node_id"] for a in reversed(chain)] + [node_id]

    # -- hierarchy paths ---------------------------------------------------

    def _build_paths(self, evidence: list[Evidence]) -> list[HierarchyPath]:
        paths: list[HierarchyPath] = []
        for ev in evidence[:MAX_PATHS]:
            chain = get_ancestor_chain(self.graph, ev.node_id)
            nodes = list(reversed(chain)) + [
                self.graph.get_node(ev.node_id)
            ]
            entries: list[HierarchyPathEntry] = []
            for node in nodes:
                if not node:
                    continue
                entries.append(
                    HierarchyPathEntry(
                        node_id=node["node_id"],
                        title=node.get("title", ""),
                        label=node.get("label", ""),
                        level=int(node.get("hierarchy_level", node.get("level", 0))),
                        numbering=node.get("numbering", ""),
                    )
                )
            paths.append(HierarchyPath(node_id=ev.node_id, entries=entries))
        return paths

    # -- citations ---------------------------------------------------------

    def _build_citations(self, evidence: list[Evidence]) -> list[SourceCitation]:
        citations: list[SourceCitation] = []
        for i, ev in enumerate(evidence, 1):
            citations.append(
                SourceCitation(
                    index=i,
                    node_id=ev.node_id,
                    title=ev.title,
                    label=ev.label,
                    numbering=ev.numbering,
                    score=ev.final_score,
                    citation_text=self._citation_text(ev),
                    snippet=ev.snippet,
                )
            )
        return citations

    @staticmethod
    def _citation_text(ev: Evidence) -> str:
        parts: list[str] = []
        if ev.label and ev.numbering:
            parts.append(f"{ev.label} {ev.numbering}")
        elif ev.numbering:
            parts.append(f"Section {ev.numbering}")
        if ev.title:
            parts.append(f'"{ev.title}"')
        return ", ".join(parts) or ev.node_id

    # -- counter-authority detection --------------------------------------

    def _detect_counter_authorities(
        self, evidence: list[Evidence]
    ) -> list[CounterAuthority]:
        results: list[CounterAuthority] = []
        for ev in evidence:
            haystack = f"{ev.title} {ev.text}".lower()
            for marker, phrases in _COUNTER_MARKERS.items():
                for phrase in phrases:
                    if phrase in haystack:
                        idx = haystack.find(phrase)
                        context = ev.text[max(0, idx - 40): idx + 80].strip()
                        results.append(
                            CounterAuthority(
                                node_id=ev.node_id,
                                title=ev.title,
                                reason=_MARKER_REASONS[marker],
                                marker=phrase,
                                evidence_text=context or ev.snippet,
                            )
                        )
                        break
        return results

    # -- confidence scoring ------------------------------------------------

    @staticmethod
    def _score_confidence(
        evidence: list[Evidence], parsed
    ) -> Confidence:
        if not evidence:
            return Confidence(
                score=0.0,
                label="low",
                factors={"reason": "no_evidence"},
            )

        rank_weights = [1.0, 0.85, 0.7, 0.55, 0.4]
        top = evidence[: len(rank_weights)]
        weights = rank_weights[: len(top)]
        base = sum(ev.final_score * w for ev, w in zip(top, weights)) / sum(weights)

        keywords = set(parsed.keywords)
        matched: set[str] = set()
        for ev in evidence:
            haystack = f"{ev.title} {ev.text} {ev.numbering}".lower()
            for kw in keywords:
                if kw in haystack:
                    matched.add(kw)
        coverage = len(matched) / len(keywords) if keywords else 1.0

        sufficiency = min(1.0, len(evidence) / 3.0)

        citation_bonus = 0.0
        if parsed.section_refs:
            for ev in evidence:
                haystack = f"{ev.title} {ev.text} {ev.numbering}".lower()
                if any(ref in haystack for ref in parsed.section_refs) or any(
                    num in ev.numbering.lower() for num in parsed.section_numbers
                ):
                    citation_bonus = 0.1
                    break

        score = min(
            1.0, max(0.0, 0.6 * base + 0.25 * coverage + 0.15 * sufficiency + citation_bonus)
        )
        score = round(score, 4)
        label = "high" if score >= 0.7 else ("medium" if score >= 0.45 else "low")

        return Confidence(
            score=score,
            label=label,
            factors={
                "base_score": round(base, 4),
                "keyword_coverage": round(coverage, 4),
                "sufficiency": round(sufficiency, 4),
                "citation_bonus": citation_bonus,
                "n_evidence": len(evidence),
                "matched_keywords": sorted(matched),
            },
        )

    # -- validity flags ----------------------------------------------------

    def _assess_validity(
        self,
        evidence: list[Evidence],
        counter: list[CounterAuthority],
        confidence: Confidence,
    ) -> Validity:
        supported = len(evidence) >= 1 and confidence.score >= self.threshold
        insufficient = not supported
        has_conflicts = len(counter) > 0
        cites_counter_authority = any(
            c.marker in _STRONG_MARKERS for c in counter
        )
        is_valid = supported and not has_conflicts

        reasons: list[str] = []
        if supported:
            reasons.append("answer supported by retrieved evidence")
        else:
            reasons.append(
                "insufficient evidence to support the answer "
                f"(confidence {confidence.score:.2f} below threshold {self.threshold:.2f})"
            )
        if has_conflicts:
            reasons.append(
                "conflicting or qualifying statements detected in retrieved evidence"
            )
        if cites_counter_authority:
            reasons.append(
                "evidence may be overruled, superseded, repealed, or overridden"
            )

        return Validity(
            is_valid=is_valid,
            supported=supported,
            has_conflicts=has_conflicts,
            cites_counter_authority=cites_counter_authority,
            insufficient_evidence=insufficient,
            reasons=reasons,
        )
