"""Deterministic legal query expansion for Indian Contract Act retrieval.

Phase 4: maps ordinary-language expressions in legal queries onto the
canonical concepts the HHGR pipeline understands. For example, "threat" is
expanded into the coercion / free consent / voidable agreement concepts defined
by the Indian Contract Act 1872, plus the sections that define them.

The expansion is intentionally:
- deterministic: a fixed phrase table; no model, no randomness;
- configurable: gated by QA_QUERY_EXPANSION_ENABLED (default False, opt-in);
- auditable: every matched phrase, added term and added concept is recorded so
  the reasoning chain can show exactly what was expanded and why;
- corpus-aware: concept terms are always added, but a section reference is only
  injected when the referenced section actually exists in the currently indexed
  corpus (``available_sections``). References to sections absent from the corpus
  are recorded as omitted rather than injected, so expansion never steers
  retrieval toward sections the index cannot return.

Section references are introduced ONLY through the explicitly verified mapping
``VERIFIED_SECTION_MAPPING`` — never inferred from raw query text.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field

from src.retrieval.query import RetrievalQuery

# Canonical ICA concepts -> the search terms that surface their defining
# sections in the vector store and the graph.
CONCEPT_TERMS: dict[str, tuple[str, ...]] = {
    "coercion": ("coercion",),
    "free_consent": ("free consent",),
    "voidable_agreement": ("voidable agreement", "voidable"),
    "fraud": ("fraud",),
    "misrepresentation": ("misrepresentation",),
    "proposal": ("proposal",),
    "consideration": ("consideration",),
    "capacity": ("capacity", "sound mind", "competent"),
    "undue_influence": ("undue influence",),
}

# Human-readable labels for the reasoning chain / diagnostics.
CONCEPT_DISPLAY: dict[str, str] = {
    "coercion": "coercion",
    "free_consent": "free consent",
    "voidable_agreement": "voidable agreement",
    "fraud": "fraud",
    "misrepresentation": "misrepresentation",
    "proposal": "proposal",
    "consideration": "consideration",
    "capacity": "capacity",
    "undue_influence": "undue influence",
}

# Explicit, verified ICA 1872 section numbers per concept. Never extended
# heuristically.
VERIFIED_SECTION_MAPPING: dict[str, tuple[int, ...]] = {
    "coercion": (15,),
    "free_consent": (14,),
    "voidable_agreement": (19, 2),
    "fraud": (17,),
    "misrepresentation": (18,),
    "proposal": (2,),
    "consideration": (25, 2),
    "capacity": (11, 12),
    "undue_influence": (16,),
}

# Surface phrases -> expanded concepts. More specific phrases (e.g.
# "forced to sign") are listed before their shorter forms so their concepts are
# always included when both match.
SURFACE_PHRASES: dict[str, tuple[str, ...]] = {
    # coercion / free consent / voidable agreement (ss. 14-15, 19)
    "forced to sign": ("coercion", "free_consent", "voidable_agreement"),
    "forced to": ("coercion", "free_consent", "voidable_agreement"),
    "threatened": ("coercion", "free_consent", "voidable_agreement"),
    "threatening": ("coercion", "free_consent", "voidable_agreement"),
    "threat": ("coercion", "free_consent", "voidable_agreement"),
    "threats": ("coercion", "free_consent", "voidable_agreement"),
    "duress": ("coercion", "free_consent", "voidable_agreement"),
    "coercion": ("coercion", "free_consent", "voidable_agreement"),
    # fraud / misrepresentation (ss. 17-18)
    "false statements": ("fraud", "misrepresentation"),
    "false statement": ("fraud", "misrepresentation"),
    "lied": ("fraud", "misrepresentation"),
    "lies": ("fraud", "misrepresentation"),
    "lying": ("fraud", "misrepresentation"),
    "deceived": ("fraud", "misrepresentation"),
    "deceit": ("fraud", "misrepresentation"),
    "fraud": ("fraud",),
    # proposal (s. 2)
    "offered": ("proposal",),
    "offers": ("proposal",),
    "offer": ("proposal",),
    "proposal": ("proposal",),
    # consideration (ss. 25, 2)
    "without consideration": ("consideration",),
    "no consideration": ("consideration",),
    "consideration": ("consideration",),
    # capacity (ss. 11-12)
    "unable to understand": ("capacity",),
    "capacity to contract": ("capacity",),
    "sound mind": ("capacity",),
    "unsound mind": ("capacity",),
    "incompetent": ("capacity",),
    "minor": ("capacity",),
    # undue influence (s. 16)
    "position to dominate": ("undue_influence",),
    "undue influence": ("undue_influence",),
    "dominant party": ("undue_influence",),
    "fiduciary": ("undue_influence",),
    "pressured": ("undue_influence",),
    "pressure": ("undue_influence",),
}


# Embedded section numbers in node numbering/title text, e.g. ``124.`` from
# ``124. "Contract of indemnity" defined`` or ``294A``. Four-digit numbers
# (such as the 1872 year) are intentionally excluded. Mirrors the extraction
# used by the evaluation pipeline (``src/evaluation/sections.py``) so that the
# "available" set matches the section keys the evaluator would recognize.
_EMBEDDED_SECTION_RE = re.compile(
    r"(?<![\d.])"
    r"(\d{1,3}(?:[a-z](?![\w.])|(?:\([a-z0-9]+\)))?)"
    r"(?![\d])",
    re.IGNORECASE,
)


def _phrase_in(text: str, phrase: str) -> bool:
    """Match a surface phrase against lowercased query text.

    Multi-word phrases match as substrings (so "forced to sign" also matches
    "forced to"); single-word phrases match at word boundaries so e.g. "lie"
    does not fire inside "belief" and "threat" does not fire inside "threatens".
    """
    if " " in phrase:
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def section_keys_from_text(text: str) -> set[str]:
    """Extract section keys embedded in node numbering/title text.

    ``124. "Contract of indemnity" defined`` -> ``{"124"}``, ``53`` ->
    ``{"53"}``, ``294A`` -> ``{"294a"}``.
    """
    if not text:
        return set()
    return {m.group(1).lower() for m in _EMBEDDED_SECTION_RE.finditer(text)}


def available_section_keys(nodes: Collection[dict]) -> set[str]:
    """Union of section keys present across the given corpus graph nodes.

    Each node is a properties dict; section keys are read from the ``numbering``
    and ``title`` fields, matching the keys the evaluator extracts from the same
    nodes. This is the set that makes a verified section reference "available"
    for injection.
    """
    keys: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        keys.update(section_keys_from_text(node.get("numbering", "")))
        keys.update(section_keys_from_text(node.get("title", "")))
    return {key for key in keys if key}


_SECTION_REF_RE = re.compile(
    r"(?:section|sec\.?|s\.?)\s*(\d{1,3}(?:[a-z]|(?:\([a-z0-9]+\)))?)",
    re.IGNORECASE,
)


def _ref_to_section_key(ref: str) -> str:
    """Extract the section key from a reference.

    ``section 15`` -> ``15``, ``section 294A`` -> ``294a``.
    """
    match = _SECTION_REF_RE.search(ref or "")
    return match.group(1).lower() if match else re.sub(r"[^a-z0-9]", "", (ref or "").lower())


@dataclass
class ExpansionResult:
    """Result of deterministic legal query expansion.

    ``section_refs`` holds ONLY the references that exist in the indexed corpus
    (they are the ones injected into the search text). The considered /
    available / omitted breakdown is kept for provenance so the reasoning chain
    can explain why a reference was or was not injected.
    """

    enabled: bool
    matched_phrases: list[str] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    expanded_concepts: list[str] = field(default_factory=list)
    section_refs: list[str] = field(default_factory=list)
    section_refs_considered: list[str] = field(default_factory=list)
    section_refs_available: list[str] = field(default_factory=list)
    section_refs_omitted: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.matched_phrases)

    def build_search_text(self, query: str) -> str:
        """The query plus canonical concept terms and available section refs."""
        if not self.active:
            return query
        extras = [*self.expanded_terms, *self.section_refs]
        return " ".join([query, *extras]).strip()


def expand_query(
    query: str | RetrievalQuery,
    *,
    enabled: bool = True,
    available_sections: Collection[str] | None = None,
) -> ExpansionResult:
    """Deterministically expand a legal query with canonical ICA concepts.

    Concept terms are always added when a surface phrase matches. A verified
    section reference is injected ONLY when its section key is present in
    ``available_sections`` (the sections of the currently indexed corpus).
    Without corpus knowledge (``available_sections`` is None or empty) no
    reference can be verified, so no section reference is injected — all
    considered references are reported as omitted.

    Returns an ``ExpansionResult``. When ``enabled`` is False or no surface
    phrase matches, the result is inactive and ``build_search_text`` returns
    the original query unchanged (backward compatible).
    """
    if not enabled:
        return ExpansionResult(enabled=False, reason="expansion disabled")
    raw = query.raw if isinstance(query, RetrievalQuery) else (query or "")
    lowered = raw.lower().strip()
    if not lowered:
        return ExpansionResult(enabled=True, reason="empty query")

    matched: list[str] = []
    concepts: set[str] = set()
    for phrase, targets in SURFACE_PHRASES.items():
        if _phrase_in(lowered, phrase):
            matched.append(phrase)
            concepts.update(targets)

    if not concepts:
        return ExpansionResult(
            enabled=True,
            matched_phrases=matched,
            reason="no legal concept phrases matched",
        )

    ordered = sorted(concepts)
    terms: list[str] = []
    for concept in ordered:
        for term in CONCEPT_TERMS[concept]:
            if term not in terms:
                terms.append(term)

    seen_refs: set[str] = set()
    considered: list[str] = []
    for ref in sorted(
        f"section {n}"
        for concept in ordered
        for n in VERIFIED_SECTION_MAPPING.get(concept, ())
    ):
        if ref not in seen_refs:
            seen_refs.add(ref)
            considered.append(ref)

    available = {str(key).strip().lower() for key in (available_sections or ()) if str(key).strip()}
    available_refs = [ref for ref in considered if _ref_to_section_key(ref) in available]
    omitted_refs = [ref for ref in considered if _ref_to_section_key(ref) not in available]

    reason = (
        f"expanded {len(matched)} phrase(s) into {len(ordered)} legal concept(s): "
        + ", ".join(CONCEPT_DISPLAY[c] for c in ordered)
    )
    if omitted_refs:
        reason += (
            f"; omitted {len(omitted_refs)} section reference(s) not present in "
            f"the indexed corpus (e.g. {omitted_refs[0]})"
        )
    return ExpansionResult(
        enabled=True,
        matched_phrases=matched,
        expanded_terms=terms,
        expanded_concepts=ordered,
        section_refs=available_refs,
        section_refs_considered=considered,
        section_refs_available=available_refs,
        section_refs_omitted=omitted_refs,
        reason=reason,
    )
