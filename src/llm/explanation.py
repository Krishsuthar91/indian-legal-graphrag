"""Explainability engine — turns retrieval into a structured, verifiable explanation.

Reuses the existing layers:
- Module 5 HHGR (``retrieve``, ``propagate_hierarchy``, ``get_ancestor_chain``)
- Module 6 vector retrieval (``VectorRetriever.dense_search`` / ``hybrid_retrieve``)

Produces: retrieval provenance, a graph reasoning chain, hierarchy paths, source
citations, counter-authority detection, confidence scoring, and validity flags.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.embeddings.retriever import DEFAULT_HYBRID_WEIGHTS
from src.knowledge_graph.traversal import get_children
from src.llm.provenance import (
    CitationEntailment,
    ClaimResult,
    Confidence,
    CounterAuthority,
    Evidence,
    EvidenceRelevance,
    ExplanationResult,
    HierarchyPath,
    HierarchyPathEntry,
    ReasoningStep,
    RetrievalSummary,
    SourceCitation,
    Validity,
    VerificationTrace,
)
from src.retrieval.context import get_ancestor_chain, propagate_hierarchy
from src.retrieval.intent import adaptive_top_k, detect_intent
from src.retrieval.query import _ACT_NAME_TO_DOC_ID, parse_query, tokenize
from src.retrieval.query_expansion import available_section_keys, expand_query
from src.retrieval.ranker import retrieve
from src.retrieval.scorer import (
    LEAF_LABELS,
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
    "citation": 0.30,
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

# Task 21 definition-first promotion: matches a section title that *declares* a
# definition, e.g. `"Coercion" defined`, `"fraud defined`, `"Misrepresentation"
# defined -`, `"Contingent contract" defined`. The captured group is the defined
# term (possibly quoted). Used to promote the defining section of a bare-concept
# query above sections that merely mention the term.
_DEFINITION_RE: re.Pattern = re.compile(
    r'"([^"]+)"\s+defined|^\s*"?([A-Za-z][\w \-]*?)\s+defined',
    re.IGNORECASE,
)
DEFINITION_BONUS = 0.12
FRAGMENT_DEMOTION = 0.55

# Task 24 — canonical document routing. The QA corpus contains exactly two
# canonical documents: the Indian Contract Act (ICA) and the Indian Penal Code
# (IPC). When a query does not name a resolved canonical Act, retrieval would
# otherwise run cross-document and contaminate ICA-targeted evidence with IPC
# nodes (and vice-versa). The engineering below infers the document target so
# retrieval stays within the correct canonical document, while keeping
# genuinely out-of-corpus (foreign-act / fictitious) queries unresolved so the
# grounding guard still blocks them.
#
# Foreign-act / foreign-jurisdiction markers. A query whose legal instrument is
# *not* one of the two canonical Indian documents is out-of-corpus: it must stay
# unresolved (generic) so it cannot pull ICA/IPC evidence and is reliably
# blocked by the grounding guard. This lexicon is the auditable list of
# instruments/jurisdictions outside the ICA/IPC pair.
_FOREIGN_ACT_MARKERS: tuple[str, ...] = (
    # Named non-canonical / foreign legislation.
    "british columbia", "california civil code", "german civil code", "bgb",
    "new york general obligations", "paris convention", "gdpr", "crpc",
    "criminal procedure code", "reserve bank of india", "master direction",
    "central goods and services tax", "motor vehicles act", "arbitration and "
    "conciliation act", "income tax act", "limitation act", "specific relief act",
    "partnerships act", "negotiable instruments act", "employees provident funds",
    "united states bankruptcy", "us bankruptcy", "bankruptcy code",
    "australian consumer law", "uk companies", "english companies",
    "companies act 2006", "indian constitution",
    # Jurisdictions / legal systems that are not the ICA/IPC domain.
    "australia", "australian", "united states", "u.s.", "u.k.", "uk ", "british",
    "germany", "german", "france", "french", "canada", "canadian", "california",
    "new york", "england", "american", "usa ",
)

# Fictitious / self-invalidating act names that must never resolve to a doc.
_FICTITIOUS_ACT_MARKERS: tuple[str, ...] = (
    "act that does not exist",
    "does not exist",
    "not in it",
)

# Default document used when a query is in the ICA/IPC domain but does not
# explicitly name an Act and has no section that is unique to the other
# canonical document. The QA domain is the Indian Contract Act, so ICA is the
# natural fallback; the grounding guard still blocks genuinely unsupported
# queries routed here.
_ICA_DOC_ID = _ACT_NAME_TO_DOC_ID["indian contract act"]

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


def _parse_relevance_json(raw: str) -> dict[str, Any]:
    """Extract the JSON object from an LLM judge response, tolerating prose."""
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])  # noqa: E203
        except json.JSONDecodeError:
            pass
    return {"score": 0.0, "label": "unknown", "reason": "Failed to parse LLM response."}


def _parse_entailment_json(raw: str) -> dict[str, Any]:
    """Extract the entailment JSON object from an LLM judge response."""
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])  # noqa: E203
        except json.JSONDecodeError:
            pass
    return {"entailment": 0.0, "contradicts": False, "reason": "Failed to parse."}


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
        llm_client=None,
    ) -> None:
        self.graph = graph
        self.vr = vector_retriever
        self.llm_client = llm_client
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
        self._doc_section_sets: dict[str | None, set[str]] | None = None

    # -- document-target inference (Task 24) --------------------------------

    def _doc_section_sets_by_document(self) -> dict[str | None, set[str]]:
        """``document_id -> set of section numbering keys`` for the corpus."""
        if self._doc_section_sets is not None:
            return self._doc_section_sets
        result: dict[str | None, set[str]] = {}
        try:
            nodes = self.graph.all_nodes()
        except (AttributeError, TypeError):
            nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            doc = node.get("document_id")
            number = str(node.get("numbering", "")).strip()
            if number:
                result.setdefault(doc, set()).add(number)
        self._doc_section_sets = result
        return result

    def _document_ids_in_corpus(self) -> set[str]:
        """The set of document ids that exist in the loaded graph.

        Drawn from every ``document_id`` property plus the id of every
        ``Document``-labeled node. Canonical document routing (Task 24) is only
        meaningful when the loaded corpus actually contains the canonical Act,
        so this guard prevents the ICA/IPC target from being applied to an
        unrelated corpus (which would otherwise filter every dense hit away).
        """
        ids: set[str] = set()
        try:
            nodes = self.graph.all_nodes()
        except (AttributeError, TypeError):
            nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            doc = node.get("document_id")
            if doc:
                ids.add(str(doc))
            if node.get("label") == "Document" and node.get("node_id"):
                ids.add(str(node.get("node_id")))
        return ids

    def _infer_document_id(self, parsed) -> tuple[str | None, str]:
        """Infer the canonical document target for ``parsed`` (Task 24).

        Returns ``(document_id | None, reason)``. A ``None`` document_id means
        retrieval runs generically (no document filter), which is correct for
        out-of-corpus (foreign-act / fictitious / purely-generic) queries so the
        grounding guard keeps blocking them.

        Decision order (foreign context is always respected first, so an
        out-of-corpus query is never force-routed to a canonical document):

        1. Explicit canonical Act already resolved by ``parse_query`` -> use it,
           but only when that canonical document is actually present in the
           loaded corpus (otherwise fall through to legacy generic behaviour).
        2. A non-canonical (foreign / fictitious) Act is named -> stay generic.
        3. A cited section number exists in exactly one canonical document ->
           use that document (unambiguous section-targeted query). Only applies
           when that canonical document is present in the corpus.
        4. Otherwise -> default to the primary domain Act (ICA), but only when
           the ICA document is present in the corpus; for any other corpus (e.g.
           unit-test fixtures) routing stays generic so retrieval is unchanged.
           The grounding guard still blocks queries routed here for which the
           ICA evidence is genuinely insufficient.
        """
        if parsed.document_id:
            doc_id = parsed.document_id
            if doc_id in self._document_ids_in_corpus():
                return doc_id, "explicit-canonical-act"

        raw_lower = (parsed.raw or "").lower()
        if any(marker in raw_lower for marker in _FOREIGN_ACT_MARKERS):
            return None, "foreign-act"
        if any(marker in raw_lower for marker in _FICTITIOUS_ACT_MARKERS):
            return None, "fictitious-act"
        # A non-canonical Act name was extracted by the parser but didn't
        # resolve (e.g. "an act that does not exist") -> out of corpus.
        if parsed.act_name:
            normalized = parsed.act_name.lower().strip()
            if not any(
                pattern in normalized or normalized in pattern
                for pattern in _ACT_NAME_TO_DOC_ID
            ):
                return None, "non-canonical-act"

        corpus_doc_ids = self._document_ids_in_corpus()
        section_sets = self._doc_section_sets_by_document()
        ica_present = _ICA_DOC_ID in corpus_doc_ids
        ipc_doc_id = _ACT_NAME_TO_DOC_ID["indian penal code"]
        ipc_present = ipc_doc_id in corpus_doc_ids
        ica_nums = section_sets.get(_ICA_DOC_ID, set())
        ipc_nums = section_sets.get(ipc_doc_id, set())
        unique_docs: set[str] = set()
        for num in parsed.section_numbers:
            if ica_present and num in ica_nums and num not in ipc_nums:
                unique_docs.add(_ICA_DOC_ID)
            elif ipc_present and num in ipc_nums and num not in ica_nums:
                unique_docs.add(ipc_doc_id)
        if len(unique_docs) == 1:
            return next(iter(unique_docs)), "unique-section"

        if ica_present:
            return _ICA_DOC_ID, "ica-default"
        return None, "no-canonical-corpus"

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
        if not effective_parsed.document_id and parsed.document_id:
            effective_parsed.document_id = parsed.document_id
            effective_parsed.act_name = parsed.act_name

        # Task 24 — cross-document isolation. When no canonical Act was resolved
        # (and expansion didn't inject one), infer the document target so
        # ICA-targeted queries retrieve only ICA nodes instead of leaking IPC
        # content across documents. Foreign-act / fictitious queries stay
        # unresolved ("generic") so the grounding guard still blocks them.
        inferred_doc, doc_reason = self._infer_document_id(effective_parsed)
        if inferred_doc and not effective_parsed.document_id:
            effective_parsed.document_id = inferred_doc
        elif not inferred_doc:
            effective_parsed.document_id = ""
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
                    "document_id": effective_parsed.document_id,
                    "document_target_reason": doc_reason,
                },
            )
        )

        # 2. Dense (multilingual) retrieval
        _start = time.perf_counter()
        dense_ids: list[str] = []
        if self.vr is not None:
            for hit in self.vr.dense_search(
                search_text, top_k=budget, language=language,
                document_id=effective_parsed.document_id or None,
            ):
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
        graph_results = retrieve(
            self.graph, search_text, top_k=budget,
            document_id=effective_parsed.document_id or None,
        )
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

        # Task 21 recall: guarantee that every node whose *numbering* exactly
        # matches an explicitly-requested section number enters the candidate
        # set. Such nodes may otherwise score too low in dense/graph/hierarchy to
        # reach the fused candidate set, so a bare "Section 10" query would never
        # surface Section 10 (Category A misses). The existing C7 exact-number
        # promotion then ranks it first. Applied only to the user's own section
        # references (not expansion-injected terms).
        signals, candidates = self._ensure_exact_section_candidates(
            signals, candidates, effective_parsed
        )

        _start = time.perf_counter()
        rank: dict[str, float] = {}
        chain_info: dict[str, dict[str, Any]] = {}
        for nid in candidates:
            sig = signals[nid]
            node = self.graph.get_node(nid)
            multiplier = self._chain_relevance(node)
            definition_bonus = self._definition_promotion(node, effective_parsed)
            frag_mult = self._fragment_demotion_multiplier(node)
            rank[nid] = (
                self._rank(sig, multiplier=multiplier) * frag_mult
            ) + definition_bonus
            chain_info[nid] = {
                "chain_relevance": multiplier,
                "fragment_demotion": frag_mult,
                "definition_bonus": round(definition_bonus, 4),
                "effective_hierarchy_score": round(sig.hierarchy * multiplier, 4),
                "ranking_reason": self._chain_reason(node),
            }
        ranked_ids = sorted(candidates, key=lambda n: (-rank[n], n))[:budget]

        # C7: Promote exact section-number citation matches to rank first.
        # When the user references a specific section (e.g. "Section 10") and a
        # candidate node's numbering matches that reference exactly (respecting
        # any document filter imposed by a named Act), that node must outrank
        # semantic-only matches.  Without this, dense hits whose text merely
        # resembles the query can out-rank the literally-referenced section.
        # Only exact *numbering* matches qualify — text-content mention of a
        # section number (which citation_score also rewards) must not promote an
        # unrelated node to the top.
        def _exact_numbering_match(nid):
            node = self.graph.get_node(nid)
            if not node:
                return False
            if effective_parsed.document_id:
                node_doc = node.get("document_id")
                if node_doc and node_doc != effective_parsed.document_id:
                    return False
            numbering = str(node.get("numbering", "")).strip()
            for num in effective_parsed.section_numbers:
                if not num or not numbering:
                    continue
                if numbering == num:
                    return True
                if (num.isdigit() and numbering.isdigit()
                        and numbering.lstrip("0") == num.lstrip("0")):
                    return True
            return False

        exact_matches = [
            nid for nid in candidates
            if _exact_numbering_match(nid)
        ]
        if exact_matches and (effective_parsed.section_refs or effective_parsed.section_numbers):
            rest = [nid for nid in ranked_ids if nid not in exact_matches]
            ranked_ids = exact_matches + rest
            exact_matches_sorted = True
        else:
            exact_matches_sorted = False

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
        if exact_matches_sorted:
            ranking_breakdown["_promoted_exact_matches"] = list(exact_matches)
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
        evidence_relevance = self._compute_evidence_relevance(query, evidence)
        confidence = self._score_confidence(
            evidence, effective_parsed, query, evidence_relevance=evidence_relevance,
        )
        validity = self._assess_validity(
            evidence, counter, confidence, query, evidence_relevance,
        )
        verification_trace = self._build_verification_trace(confidence)

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
            evidence_relevance=evidence_relevance.score,
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
            evidence_relevance=evidence_relevance,
            verification_trace=verification_trace,
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
                query, top_k=top_k, language=language, weights=self.weights,
                document_id=parsed.document_id or None,
            )
            for hit in hybrid:
                sig = signals.setdefault(hit.node_id, _Signal())
                sig.dense = max(sig.dense, hit.dense_score)
                sig.graph = max(sig.graph, hit.graph_score)
                sig.hierarchy = max(sig.hierarchy, hit.hierarchy_score)
            # Merge the standalone graph-ranked results into the candidate set.
            # Dense-only hits can otherwise crowd out a high-certainty graph
            # match (e.g. an explicit section reference) before it reaches the
            # final ranking, because the graph signal alone may rank below the
            # top-k dense hits.
            for node_id, g_score in graph_scores.items():
                sig = signals.setdefault(node_id, _Signal())
                if not sig.graph:
                    sig.graph = g_score
                if not sig.hierarchy:
                    sig.hierarchy = propagated.get(node_id, 0.0)
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

    def _ensure_exact_section_candidates(
        self,
        signals: dict[str, _Signal],
        candidates: set[str],
        parsed,
    ) -> tuple[dict[str, _Signal], set[str]]:
        """Ensure every exact-numbering section node is a candidate.

        For a query that explicitly references a section number (e.g. "Section
        10"), any graph node whose ``numbering`` equals that number is an
        authoritative retrieval target. If such a node was fused out (because
        dense/graph/hierarchy scored too low), inject it into ``candidates``
        with ``citation`` set to full so the C7 exact-number promotion can rank
        it first. Respects ``parsed.document_id`` when the query names an Act.

        Only the original user section references are honoured; expansion-injected
        references are deliberately excluded so expansion cannot steer retrieval.
        """
        user_numbers = [n for n in parsed.section_numbers if n]
        user_refs = list(parsed.section_refs or [])
        section_numbers = user_numbers or [n for n in user_refs if n.strip().isdigit()]
        if not section_numbers:
            return signals, candidates

        doc_id = parsed.document_id or None
        for node in self.graph.all_nodes():
            if not node.get("node_id"):
                continue
            nid = node["node_id"]
            num = str(node.get("numbering", "")).strip()
            if not num:
                continue
            if doc_id:
                node_doc = node.get("document_id")
                if node_doc and node_doc != doc_id:
                    continue
            matched = any(
                num == requested
                or (requested.isdigit() and num.isdigit()
                    and num.lstrip("0") == requested.lstrip("0"))
                for requested in section_numbers
            )
            if not matched:
                continue
            sig = signals.get(nid)
            if sig is None:
                sig = _Signal()
                signals[nid] = sig
                candidates.add(nid)
            if not sig.citation:
                sig.citation = 1.0
        return signals, candidates

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
                # An explicit query section reference that exactly matches this
                # node's numbering is the strongest citation signal: award it
                # the full citation score regardless of citation edge counts.
                if citation_score(node, parsed) == 1.0:
                    sig.citation = 1.0
            count = citation_frequency(self.graph, node_id)
            citation_counts[node_id] = count
            max_citations = max(max_citations, count)
        if max_citations > 0:
            for node_id, count in citation_counts.items():
                if not signals[node_id].citation:
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

    def _definition_promotion(self, node, parsed) -> float:
        """Definition-first ranking bonus for bare-concept queries.

        When the query asks about a concept (e.g. "What is coercion?"), the
        section that *defines* the term should outrank sections that merely
        mention it. Award a bounded bonus to a legal leaf whose title declares a
        definition (``"Coercion" defined``, ``"fraud defined``) and whose defined
        term overlaps the query keywords. The bonus is bounded and only used to
        order evidence — confidence/verification are untouched.
        """
        if not node or not parsed:
            return 0.0
        label = str(node.get("label", "")).lower()
        if label not in LEAF_LABELS:
            return 0.0
        keywords = set(parsed.keywords or [])
        if not keywords:
            return 0.0
        title = str(node.get("title", "") or "")
        match = _DEFINITION_RE.search(title)
        if not match:
            return 0.0
        term = (match.group(1) or match.group(2) or "").strip().lower()
        if set(tokenize(term)) & keywords:
            return float(DEFINITION_BONUS)
        return 0.0

    def _fragment_demotion_multiplier(self, node) -> float:
        """Demote illustration/explanation fragments that are not real sections.

        Some corpora store an illustration or explanation as a bare ``Section``
        leaf whose ``numbering`` field holds the entire body prose (e.g. ``s (a)
        A, by falsely pretending...``) instead of a clean section identifier.
        Such fragments are never a valid numbered answer, yet their dense text
        overlap lets them win the top rank. This returns a demotion multiplier
        for prose-numbered leaves so real, clean-numbered sections surface
        instead. Nodes with a canonical identifier (numbers, clause markers) are
        unaffected (multiplier 1.0).
        """
        num = str(node.get("numbering", "") or "").strip()
        if not num:
            return 1.0
        if num.lower() in (
            "illustration", "illustrations", "explanation", "explanations",
        ):
            return float(FRAGMENT_DEMOTION)
        if len(num) <= 20 and not re.search(r"\s", num):
            return 1.0
        return float(FRAGMENT_DEMOTION)

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

    # -- evidence sufficiency ------------------------------------------------

    @staticmethod
    def _compute_evidence_sufficiency(
        query: str,
        evidence: list[Evidence],
        keyword_coverage: float,
    ) -> float:
        """Query-aware evidence sufficiency score in [0, 1].

        Composed of three signals:
        - 70% semantic similarity (Dice coefficient of query vs concatenated evidence)
        - 20% keyword coverage (fraction of query keywords found in evidence)
        - 10% evidence diversity (small bonus for multiple independent chunks,
          capped at 3 so irrelevant chunks never inflate the score).
        """
        import re as _re

        evidence_text = " ".join(
            f"{ev.title} {ev.text} {ev.numbering}" for ev in evidence
        )
        # Strip question boilerplate so similarity measures content, not syntax.
        cleaned_query = _re.sub(
            r"^(what|how|when|where|who|why|which)\s+(does|do|is|are|was|were|"
            r"has|have|had|shall|should|can|could|may|might)\s+",
            "",
            query.lower(),
            count=1,
        )
        similarity = _text_similarity(cleaned_query, evidence_text.lower())
        diversity = min(len(evidence), 3) / 3.0
        return min(1.0, 0.7 * similarity + 0.20 * keyword_coverage + 0.10 * diversity)

    # -- evidence relevance (LLM judge) -----------------------------------

    _RELEVANCE_JUDGE_SYSTEM = (
        "You are an evidence relevance evaluator for a legal question answering "
        "system. Given a user question and retrieved evidence, determine how well "
        "the evidence answers the question.\n"
        "Scoring:\n"
        "1.0 = Evidence directly answers the question.\n"
        "0.75 = Evidence mostly answers the question but misses minor details.\n"
        "0.50 = Evidence is only partially relevant.\n"
        "0.25 = Evidence is topically related but does not answer the question.\n"
        "0.0 = Evidence is unrelated.\n"
        "Return ONLY JSON: {\"score\": float, \"label\": \"...\", \"reason\": \"...\"}"
    )

    def _compute_evidence_relevance(
        self, query: str, evidence: list[Evidence]
    ) -> EvidenceRelevance:
        """Score how well retrieved evidence answers the query.

        Uses an LLM judge when a client is available; falls back to a
        deterministic similarity-based estimate otherwise.
        """
        if not evidence:
            return EvidenceRelevance(score=0.0, label="none", explanation="No evidence retrieved.")

        # Attempt LLM judge when a client is wired in.
        if self.llm_client is not None:
            try:
                evidence_block = "\n\n".join(
                    f"[{ev.title}] {ev.text}" for ev in evidence
                )
                user_msg = f"Question: {query}\n\nRetrieved Evidence:\n{evidence_block}"
                response = self.llm_client.chat(
                    system=self._RELEVANCE_JUDGE_SYSTEM,
                    user=user_msg,
                    temperature=0.0,
                    max_tokens=200,
                )
                parsed = _parse_relevance_json(response.text)
                return EvidenceRelevance(
                    score=float(parsed.get("score", 0.0)),
                    label=str(parsed.get("label", "unknown")),
                    explanation=str(parsed.get("reason", "")),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("evidence_relevance.llm_failed", error=str(exc))

        # Fallback: deterministic similarity-based estimate.
        return self._relevance_fallback(query, evidence)

    @staticmethod
    def _relevance_fallback(
        query: str, evidence: list[Evidence]
    ) -> EvidenceRelevance:
        """Deterministic fallback for evidence relevance (no LLM required)."""
        import re as _re

        evidence_text = " ".join(
            f"{ev.title} {ev.text} {ev.numbering}" for ev in evidence
        )
        cleaned_query = _re.sub(
            r"^(what|how|when|where|who|why|which)\s+(does|do|is|are|was|were|"
            r"has|have|had|shall|should|can|could|may|might)\s+",
            "",
            query.lower(),
            count=1,
        )
        similarity = _text_similarity(cleaned_query, evidence_text.lower())

        if similarity >= 0.70:
            label, reason = "direct", "High text similarity to query."
        elif similarity >= 0.45:
            label, reason = "partial", "Moderate text overlap with query."
        elif similarity >= 0.20:
            label, reason = "tangential", "Low text overlap; topically related."
        else:
            label, reason = "unrelated", "Minimal text overlap with query."

        return EvidenceRelevance(score=similarity, label=label, explanation=reason)

    # -- citation entailment (LLM judge) -----------------------------------

    _ENTAILMENT_JUDGE_SYSTEM = (
        "You are a citation verification judge for a legal QA system. "
        "You will receive one claim and the cited evidence passage. "
        "Judge whether the cited passage actually supports the claim.\n"
        "Scoring:\n"
        "1.0 = Directly supported\n"
        "0.5 = Partially supported\n"
        "0.0 = Not supported\n"
        "Also determine contradicts = true if the evidence explicitly conflicts "
        "with the claim. Be strict. Topical similarity is NOT enough. The cited "
        "passage must actually contain the asserted rule or fact.\n"
        'Return ONLY JSON: {"entailment": float, "contradicts": bool, "reason": "..."}'
    )

    @staticmethod
    def _extract_claims(answer: str) -> list[str]:
        """Split a generated answer into independent factual claims.

        Ignores headings, bullet titles, and citation markers.  Each sentence
        becomes one claim.
        """
        import re as _re

        lines = answer.strip().splitlines()
        claims: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Skip markdown headings, bullet titles (lines ending with ':')
            if stripped.startswith("#") or (
                len(stripped) < 80 and stripped.endswith(":")
            ):
                continue
            # Split into sentences on '. ', '? ', '! '
            sentences = _re.split(r"(?<=[.!?])\s+", stripped)
            for sent in sentences:
                cleaned = sent.strip()
                # Strip inline citation markers like [1], [2], (Section 72)
                cleaned = _re.sub(r"\[\d+\]", "", cleaned)
                cleaned = _re.sub(r"\(Section\s+\d+\)", "", cleaned, flags=_re.IGNORECASE)
                cleaned = cleaned.strip(" .")
                if len(cleaned) > 10:
                    claims.append(cleaned)
        return claims

    @staticmethod
    def _find_citation_for_claim(
        claim: str, evidence: list[Evidence], citations: list
    ) -> Evidence | None:
        """Find the best evidence chunk for a claim using citation overlap."""
        claim_lower = claim.lower()
        best: Evidence | None = None
        best_overlap = 0
        for ev in evidence:
            ev_lower = f"{ev.title} {ev.text}".lower()
            claim_tokens = set(claim_lower.split())
            ev_tokens = set(ev_lower.split())
            overlap = len(claim_tokens & ev_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best = ev
        return best

    def _compute_citation_entailment(
        self,
        answer: str,
        evidence: list[Evidence],
        citations: list | None = None,
    ) -> CitationEntailment:
        """Verify whether cited evidence supports claims in the generated answer.

        Uses an LLM judge when a client is available; falls back to a
        deterministic similarity-based estimate otherwise.
        """
        if not answer or not answer.strip():
            return CitationEntailment(
                overall_score=0.0,
                contradiction_found=False,
                summary="No answer to evaluate.",
            )

        claims = self._extract_claims(answer)
        if not claims:
            return CitationEntailment(
                overall_score=0.0,
                contradiction_found=False,
                summary="No factual claims extracted from answer.",
            )

        claim_results: list[ClaimResult] = []

        if self.llm_client is not None:
            for claim in claims:
                ev = self._find_citation_for_claim(
                    claim, evidence, citations or []
                )
                ev_text = (
                    f"{ev.title}: {ev.text}" if ev else "No matching evidence found."
                )
                try:
                    user_msg = (
                        f"Claim: {claim}\n\nCited Evidence:\n{ev_text}"
                    )
                    response = self.llm_client.chat(
                        system=self._ENTAILMENT_JUDGE_SYSTEM,
                        user=user_msg,
                        temperature=0.0,
                        max_tokens=200,
                    )
                    parsed = _parse_entailment_json(response.text)
                    claim_results.append(
                        ClaimResult(
                            claim=claim,
                            citation=ev.node_id if ev else "",
                            entailment=float(parsed.get("entailment", 0.0)),
                            contradicts=bool(parsed.get("contradicts", False)),
                            reason=str(parsed.get("reason", "")),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("citation_entailment.llm_failed", error=str(exc))
                    claim_results.append(
                        self._entailment_fallback(claim, ev)
                    )
        else:
            for claim in claims:
                ev = self._find_citation_for_claim(
                    claim, evidence, citations or []
                )
                claim_results.append(self._entailment_fallback(claim, ev))

        scores = [cr.entailment for cr in claim_results]
        overall = sum(scores) / len(scores) if scores else 0.0
        contradiction_found = any(cr.contradicts for cr in claim_results)

        return CitationEntailment(
            overall_score=overall,
            contradiction_found=contradiction_found,
            claim_results=claim_results,
            summary=self._entailment_summary(overall, contradiction_found, len(claims)),
        )

    @staticmethod
    def _entailment_fallback(
        claim: str, evidence: Evidence | None
    ) -> ClaimResult:
        """Deterministic fallback for entailment (no LLM required)."""
        if evidence is None:
            return ClaimResult(
                claim=claim,
                citation="",
                entailment=0.0,
                contradicts=False,
                reason="No matching evidence found.",
            )
        similarity = _text_similarity(claim.lower(), evidence.text.lower())
        return ClaimResult(
            claim=claim,
            citation=evidence.node_id,
            entailment=round(min(1.0, similarity * 1.5), 4),
            contradicts=False,
            reason="Fallback: similarity-based estimate.",
        )

    @staticmethod
    def _entailment_summary(
        overall: float, contradiction: bool, n_claims: int
    ) -> str:
        parts = [f"{n_claims} claim(s) evaluated."]
        if contradiction:
            parts.append("CONTRADICTION detected.")
        if overall >= 0.8:
            parts.append("Claims are well-supported.")
        elif overall >= 0.4:
            parts.append("Partial support found.")
        else:
            parts.append("Claims are poorly supported.")
        return " ".join(parts)

    # -- verification trace (Task 6) ---------------------------------------

    @staticmethod
    def _build_verification_trace(confidence: Confidence) -> VerificationTrace:
        """Build a structured VerificationTrace from the computed Confidence.

        The trace captures every decision the verification pipeline made so
        callers (UI, provenance store, API) can expose the full reasoning
        path without re-implementing the logic.
        """
        f = confidence.factors
        status: str = f.get("verification_status", "unknown")
        reason: str = f.get("verification_reason", "")
        relevance: float = f.get("evidence_relevance", 0.0)
        sufficiency: float = f.get("evidence_sufficiency", 0.0)
        entailment: float = f.get("citation_entailment", 0.0)
        base: float = f.get("retrieval_base", 0.0)
        contradiction: bool = f.get("contradiction_found", False)
        adjustment: str = f.get("final_adjustment", "none")
        n_evidence: int = f.get("n_evidence", 0)

        # Relevance label
        if relevance >= 0.70:
            rel_label = "high"
        elif relevance >= 0.40:
            rel_label = "medium"
        elif relevance >= 0.20:
            rel_label = "low"
        else:
            rel_label = "very_low"

        # Build the step-by-step decision path
        path: list[str] = []

        if n_evidence == 0:
            path.append("No evidence retrieved")
            path.append("Confidence set to 0.0 (no_evidence)")
            path.append(f"Final confidence = {confidence.score:.4f}")
            return VerificationTrace(
                verification_status=status,
                verification_reason=reason,
                confidence_score=confidence.score,
                confidence_label=confidence.label,
                evidence_relevance_score=relevance,
                evidence_relevance_label=rel_label,
                evidence_sufficiency_score=sufficiency,
                citation_entailment_score=entailment,
                contradiction_found=contradiction,
                retrieval_base_score=base,
                final_adjustment=adjustment,
                decision_path=path,
            )

        # Check each verification rule in priority order
        if contradiction:
            path.append(
                f"Contradiction detected in evidence "
                f"(relevance={relevance:.4f})"
            )
            path.append("Verification set to CONFLICTS")
        elif entailment >= 0 and entailment < 0.35:
            path.append(
                f"Citation entailment below threshold ({entailment:.4f} < 0.35)"
            )
            path.append("Verification set to INSUFFICIENT")
        elif relevance < 0.30:
            path.append(
                f"Evidence relevance below threshold ({relevance:.4f} < 0.30)"
            )
            path.append("Verification set to INSUFFICIENT")
        elif sufficiency < 0.45:
            path.append(
                f"Evidence sufficiency below threshold ({sufficiency:.4f} < 0.45)"
            )
            path.append("Verification set to INSUFFICIENT")
        else:
            path.append("Evidence relevance passed")
            if entailment >= 0:
                path.append("Citation entailment passed")
            path.append("Evidence sufficiency passed")
            path.append(f"Verification = {status.upper()}")

        # Confidence caps
        if adjustment == "contradiction_cap":
            path.append("Confidence capped at 0.20 (contradiction)")
        elif adjustment == "insufficient_cap":
            path.append("Confidence capped at 0.45 (insufficient evidence)")
        elif adjustment == "no_answer":
            path.append("Confidence set to 0.0 (no_answer)")
        elif adjustment == "no_evidence":
            path.append("Confidence set to 0.0 (no_evidence)")
        else:
            path.append("Confidence calculated without caps")

        path.append(f"Final confidence = {confidence.score:.4f}")

        return VerificationTrace(
            verification_status=status,
            verification_reason=reason,
            confidence_score=confidence.score,
            confidence_label=confidence.label,
            evidence_relevance_score=relevance,
            evidence_relevance_label=rel_label,
            evidence_sufficiency_score=sufficiency,
            citation_entailment_score=entailment,
            contradiction_found=contradiction,
            retrieval_base_score=base,
            final_adjustment=adjustment,
            decision_path=path,
        )

    # -- confidence scoring ------------------------------------------------

    def _score_confidence(
        self,
        evidence: list[Evidence],
        parsed,
        query: str = "",
        evidence_relevance: EvidenceRelevance | None = None,
        citation_entailment: CitationEntailment | None = None,
        contradiction_found: bool = False,
        no_answer: bool = False,
    ) -> Confidence:
        """Compute confidence using the verification-aware formula.

        ``confidence = 0.35 * entailment + 0.30 * relevance``
        ``+ 0.20 * sufficiency + 0.15 * retrieval_base``

        When *citation_entailment* is ``None`` (e.g. during ``explain()`` before
        an answer exists) its weight is redistributed proportionally to the
        three remaining signals so the total is still 1.0.

        The verification badge is computed inside this method so that hard
        rules (contradiction cap, insufficient cap) apply to the final score.
        """
        # Rule 3: no evidence -> 0.0
        if not evidence:
            return Confidence(
                score=0.0,
                label="very_low",
                factors={
                    "retrieval_base": 0.0,
                    "evidence_relevance": 0.0,
                    "evidence_sufficiency": 0.0,
                    "citation_entailment": 0.0,
                    "verification_status": "insufficient",
                    "contradiction_found": contradiction_found,
                    "final_adjustment": "no_evidence",
                    "n_evidence": 0,
                    "matched_keywords": [],
                },
            )

        # Rule 4: answer generation failed -> 0.0
        if no_answer:
            return Confidence(
                score=0.0,
                label="very_low",
                factors={
                    "retrieval_base": 0.0,
                    "evidence_relevance": 0.0,
                    "evidence_sufficiency": 0.0,
                    "citation_entailment": 0.0,
                    "verification_status": "supported",
                    "contradiction_found": contradiction_found,
                    "final_adjustment": "no_answer",
                    "n_evidence": len(evidence),
                    "matched_keywords": [],
                },
            )

        # --- Component 1: retrieval base (rank-weighted average of top-5 scores) ---
        rank_weights = [1.0, 0.85, 0.7, 0.55, 0.4]
        top = evidence[: len(rank_weights)]
        weights = rank_weights[: len(top)]
        retrieval_base = sum(ev.final_score * w for ev, w in zip(top, weights)) / sum(weights)

        # --- Component 2: keyword coverage ---
        keywords = set(parsed.keywords)
        matched: set[str] = set()
        for ev in evidence:
            haystack = f"{ev.title} {ev.text} {ev.numbering}".lower()
            for kw in keywords:
                if kw in haystack:
                    matched.add(kw)
        coverage = len(matched) / len(keywords) if keywords else 1.0

        # --- Component 3: evidence sufficiency (shared computation) ---
        sufficiency = self._compute_evidence_sufficiency(query, evidence, coverage)

        # --- Component 4: evidence relevance ---
        relevance = evidence_relevance.score if evidence_relevance is not None else 0.0

        # --- Component 5: citation entailment ---
        entailment_available = citation_entailment is not None
        if entailment_available:
            entailment = citation_entailment.overall_score
        else:
            entailment = 0.0

        # --- Weighted formula with dynamic redistribution ---
        if entailment_available:
            # Full formula: 0.35 * entailment + 0.30 * relevance
            # + 0.20 * sufficiency + 0.15 * base
            score = (
                0.35 * entailment
                + 0.30 * relevance
                + 0.20 * sufficiency
                + 0.15 * retrieval_base
            )
        else:
            # Redistribute entailment weight (0.35) proportionally to the
            # other three components.  Sum of remaining weights = 0.65;
            # each component's share of that 0.65 is scaled by 0.35/0.65.
            r = 0.30 + 0.35 * (0.30 / 0.65)
            s = 0.20 + 0.35 * (0.20 / 0.65)
            b = 0.15 + 0.35 * (0.15 / 0.65)
            score = r * relevance + s * sufficiency + b * retrieval_base

        score = min(1.0, max(0.0, score))

        # --- Verification badge (computed here for hard rules) ---
        # During explain(), entailment is not yet evaluated -> sentinel -1.0.
        entailment_for_badge = -1.0 if not entailment_available else entailment
        status, _badge_reason = self._compute_verification_badge(
            relevance, sufficiency, entailment_for_badge, contradiction_found,
        )

        adjustment = "none"

        # Rule 1: contradiction_found -> cap at 0.20
        if contradiction_found:
            score = min(score, 0.20)
            adjustment = "contradiction_cap"

        # Rule 2: verification status "insufficient" -> cap at 0.45
        if status == "insufficient":
            capped = min(score, 0.45)
            if capped < score:
                adjustment = "insufficient_cap"
            score = capped

        score = round(score, 4)

        # --- Label (5 tiers) ---
        if score >= 0.85:
            label = "very_high"
        elif score >= 0.70:
            label = "high"
        elif score >= 0.50:
            label = "medium"
        elif score >= 0.30:
            label = "low"
        else:
            label = "very_low"

        return Confidence(
            score=score,
            label=label,
            factors={
                "retrieval_base": round(retrieval_base, 4),
                "evidence_relevance": round(relevance, 4),
                "evidence_sufficiency": round(sufficiency, 4),
                "citation_entailment": round(entailment, 4),
                "verification_status": status,
                "contradiction_found": contradiction_found,
                "final_adjustment": adjustment,
                "n_evidence": len(evidence),
                "matched_keywords": sorted(matched),
            },
        )

    # -- verification badge (Task 4) ----------------------------------------

    @staticmethod
    def _compute_verification_badge(
        evidence_relevance_score: float,
        evidence_sufficiency_score: float,
        citation_entailment_overall: float,
        citation_contradiction_found: bool,
    ) -> tuple[str, str]:
        """Determine verification status and reason using priority rules.

        Returns ``(status, reason)`` where *status* is one of
        ``"supported"``, ``"insufficient"``, or ``"conflicts"``.

        When *citation_entailment_overall* is negative (default -1.0 meaning
        "not yet evaluated"), the entailment priority is skipped.
        """
        if citation_contradiction_found:
            return (
                "conflicts",
                "Retrieved evidence contradicts one or more generated claims.",
            )
        # Skip entailment check when not yet evaluated (score < 0 means no
        # answer has been generated to judge against).
        if citation_entailment_overall >= 0 and citation_entailment_overall < 0.35:
            return (
                "insufficient",
                "Retrieved evidence does not support the generated answer.",
            )
        if evidence_relevance_score < 0.30:
            return (
                "insufficient",
                "Retrieved evidence is not relevant to the user question.",
            )
        if evidence_sufficiency_score < 0.45:
            return (
                "insufficient",
                "Retrieved evidence is insufficient.",
            )
        return (
            "supported",
            "Generated answer is supported by retrieved evidence.",
        )

    def _assess_validity(
        self,
        evidence: list[Evidence],
        counter: list[CounterAuthority],
        confidence: Confidence,
        query: str = "",
        evidence_relevance: EvidenceRelevance | None = None,
    ) -> Validity:
        # Counter-authority flags (preserved from old logic for diagnostics).
        has_conflicts = len(counter) > 0
        cites_counter_authority = any(
            c.marker in _STRONG_MARKERS for c in counter
        )

        # Derive verification framework scores from the new confidence factors.
        sufficiency_score = confidence.factors.get("evidence_sufficiency", 0.0)
        relevance_score = (
            evidence_relevance.score if evidence_relevance is not None
            else confidence.factors.get("evidence_relevance", 0.0)
        )
        # Use the verification status already computed by _score_confidence.
        status = confidence.factors.get("verification_status", "supported")
        reason = {
            "supported": "Generated answer is supported by retrieved evidence.",
            "insufficient": "Retrieved evidence is insufficient.",
            "conflicts": "Retrieved evidence contradicts one or more generated claims.",
        }.get(status, "Generated answer is supported by retrieved evidence.")

        # Derive legacy boolean fields from the new status so downstream code
        # that still reads ``supported`` / ``insufficient_evidence`` keeps working.
        contradiction_found = confidence.factors.get("contradiction_found", False)
        supported = status == "supported"
        insufficient = status == "insufficient"
        is_valid = supported and not has_conflicts

        reasons: list[str] = [reason]
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
            status=status,
            reason=reason,
            support_score=sufficiency_score,
            relevance_score=relevance_score,
            sufficiency_score=sufficiency_score,
            contradiction_found=contradiction_found,
        )
