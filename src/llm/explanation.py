"""Explainability engine — turns retrieval into a structured, verifiable explanation.

Reuses the existing layers:
- Module 5 HHGR (``retrieve``, ``propagate_hierarchy``, ``get_ancestor_chain``)
- Module 6 vector retrieval (``VectorRetriever.dense_search`` / ``hybrid_retrieve``)

Produces: retrieval provenance, a graph reasoning chain, hierarchy paths, source
citations, counter-authority detection, confidence scoring, and validity flags.
"""

from __future__ import annotations

from dataclasses import dataclass

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
from src.retrieval.query import parse_query
from src.retrieval.ranker import retrieve
from src.retrieval.scorer import citation_score, text_score

log = get_logger("explanation")

SNIPPET_CHARS = 240
MAX_PATHS = 6

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
    ) -> None:
        self.graph = graph
        self.vr = vector_retriever
        self.weights = weights or dict(DEFAULT_HYBRID_WEIGHTS)
        self.threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.QA_CONFIDENCE_THRESHOLD
        )

    # -- public API --------------------------------------------------------

    def explain(
        self,
        query: str,
        top_k: int = 5,
        language: str | None = None,
    ) -> ExplanationResult:
        """Run retrieval and assemble a full ExplanationResult for the query."""
        parsed = parse_query(query)
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
                },
            )
        )

        # 2. Dense (multilingual) retrieval
        dense_ids: list[str] = []
        if self.vr is not None:
            for hit in self.vr.dense_search(query, top_k=top_k, language=language):
                if hit.node_id:
                    dense_ids.append(hit.node_id)
        chain.append(
            ReasoningStep(
                step=2,
                kind="dense",
                description=(
                    f"Semantic vector search returned {len(dense_ids)} candidate(s)."
                ),
                node_ids=dense_ids[:top_k],
                detail={"count": len(dense_ids)},
            )
        )

        # 3. Graph (HHGR) retrieval
        graph_results = retrieve(self.graph, query, top_k=top_k)
        graph_map = {r.node_id: r for r in graph_results}
        chain.append(
            ReasoningStep(
                step=3,
                kind="graph",
                description=(
                    f"Hybrid hierarchical graph retrieval returned "
                    f"{len(graph_results)} candidate(s)."
                ),
                node_ids=list(graph_map)[:top_k],
                detail={
                    "seeds": [r.node_id for r in graph_results if r.is_seed],
                    "count": len(graph_results),
                },
            )
        )

        # 4. Hierarchy propagation over graph-present dense seeds
        seed_ids = [nid for nid in dense_ids if self.graph.get_node(nid) is not None]
        propagated = propagate_hierarchy(self.graph, seed_ids) if seed_ids else {}
        chain.append(
            ReasoningStep(
                step=4,
                kind="hierarchy",
                description=(
                    f"Hierarchical evidence propagated from {len(seed_ids)} seed(s) "
                    f"to {len(propagated)} ancestor/descendant node(s)."
                ),
                node_ids=list(propagated)[:top_k],
                detail={"seed_ids": seed_ids, "count": len(propagated)},
            )
        )

        # 5. Fusion + ranking
        signals, candidates = self._fuse(
            query, top_k=top_k, language=language, graph_results=graph_results,
            propagated=propagated,
        )
        ranked_ids = sorted(candidates, key=lambda n: (-signals[n].final, n))[:top_k]
        chain.append(
            ReasoningStep(
                step=5,
                kind="fusion",
                description=(
                    f"Fused dense/graph/hierarchy signals into {len(ranked_ids)} "
                    f"ranked evidence node(s) using weights "
                    f"{self._weights_label()}."
                ),
                node_ids=ranked_ids,
                detail={
                    "weights": self.weights,
                    "candidates": len(candidates),
                    "returned": len(ranked_ids),
                },
            )
        )

        evidence = self._build_evidence(ranked_ids, signals, parsed)
        paths = self._build_paths(evidence)
        citations = self._build_citations(evidence)
        counter = self._detect_counter_authorities(evidence)
        confidence = self._score_confidence(evidence, parsed)
        validity = self._assess_validity(evidence, counter, confidence)

        chain.append(
            ReasoningStep(
                step=6,
                kind="verification",
                description=(
                    f"Confidence {confidence.score:.2f} ({confidence.label}); "
                    f"valid={validity.is_valid}; "
                    f"counter-authorities detected: {len(counter)}."
                ),
                detail={"confidence": confidence.score, "validity": validity.is_valid},
            )
        )

        summary = RetrievalSummary(
            keywords=parsed.keywords,
            section_refs=parsed.section_refs,
            dense_hits=len(dense_ids),
            graph_hits=len(graph_results),
            hierarchy_propagated=len(propagated),
            candidates=len(candidates),
            returned=len(ranked_ids),
        )

        log.info(
            "explanation.complete",
            query=query,
            candidates=len(candidates),
            returned=len(ranked_ids),
            confidence=confidence.score,
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

        return signals, set(signals)

    def _weights_label(self) -> str:
        return ", ".join(f"{k}={v:.2f}" for k, v in sorted(self.weights.items()))

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
