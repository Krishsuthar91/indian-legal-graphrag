"""Deterministic legal query expansion for Indian legal corpus retrieval.

Phase 4: maps ordinary-language expressions in legal queries onto the
canonical concepts the HHGR pipeline understands. For example, "threat" is
expanded into the coercion / free consent / voidable agreement concepts defined
by the Indian Contract Act 1872, and "theft" into the IPC theft concept (s.
378). Expanded concepts also carry verified section references (ICA ss. 1-238,
IPC ss. 239-511 are distinct; IPC concept refs are therefore unambiguous).

Enabled by default since V2.4.1 so open-ended legal concept queries
("What is theft?", "What is an offer?") are not blocked behind a disabled flag.

The expansion is intentionally:
- deterministic: a fixed phrase table; no model, no randomness;
- configurable: gated by QA_QUERY_EXPANSION_ENABLED (default True);
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

# Canonical concepts -> the search terms that surface their defining sections
# in the vector store and the graph. Each concept carries multiple synonyms so
# open-ended queries ("What is an offer?", "What is theft?") collide with the
# statutory language of their defining section. ICA concepts use Contract Act
# terminology; IPC concepts use Penal Code terminology.
CONCEPT_TERMS: dict[str, tuple[str, ...]] = {
    # ICA: coercion / free consent / voidability (ss. 14-16, 19)
    "coercion": ("coercion", "coerced", "threatened", "threat", "duress", "compulsion"),
    "free_consent": ("free consent", "consent given freely", "freely consenting"),
    "voidable_agreement": ("voidable agreement", "voidable"),
    "fraud": ("fraud", "fraudulent", "deceit", "deception"),
    "misrepresentation": ("misrepresentation", "misrepresent", "false representation"),
    "proposal": ("proposal", "offer", "propose", "proposed", "proposal accepted"),
    "consideration": ("consideration", "lawful consideration"),
    "capacity": ("capacity", "sound mind", "competent", "unsound mind"),
    "undue_influence": ("undue influence",),
    # ICA: formation of contract (ss. 2, 7-8) and doctrines
    "acceptance": ("acceptance", "acceptance of proposal", "accepted", "assent"),
    "void_agreement": ("void agreement", "void contract", "agreement void"),
    "voidable_contract": ("voidable contract", "voidable"),
    "breach_of_contract": ("breach of contract", "breaking the contract", "breach of the contract"),
    "agency": ("agency", "agent", "principal", "sub-agent"),
    "indemnity": ("indemnity", "indemnify", "indemnified"),
    "guarantee": ("guarantee", "guarantor", "surety", "contract of guarantee"),
    "bailment": ("bailment", "bailor", "bailee", "deposit of goods"),
    "pledge": ("pledge", "pledgor", "pledgee", "pawnor", "pawnee"),
    # IPC: theft and property offences
    "theft": (
        "theft",
        "stealing",
        "steal",
        "stolen",
        "dishonest removal",
        "dishonestly taking",
        "dishonestly take",
    ),
    "robbery": ("robbery", "rob", "robbed"),
    "extortion": ("extortion", "extort", "extorted", "putting in fear"),
    "criminal_breach_of_trust": (
        "criminal breach of trust",
        "breach of trust",
        "entrusted property",
    ),
    "mischief": ("mischief", "causing damage to property", "causing damage"),
    "house_trespass": ("house trespass", "house-breaking", "house breaking"),
    "criminal_trespass": ("criminal trespass", "trespass"),
    # IPC: offences against the body and person
    "murder": ("murder", "murdered", "homicide", "killing", "killed"),
    "culpable_homicide": ("culpable homicide", "homicide"),
    "assault": ("assault", "assaulted", "criminal force", "use of force"),
    "rape": ("rape", "raped", "sexually assaulted"),
    "kidnapping": ("kidnapping", "kidnap", "kidnapped", "abduction"),
    "cheating": (
        "cheating",
        "cheat",
        "cheated",
        "dishonest inducement",
        "dishonestly inducing",
        "deception",
    ),
    "forgery": ("forgery", "forged", "forging", "false document"),
    "defamation": ("defamation", "defame", "defamed", "defamatory"),
    "criminal_intimidation": ("criminal intimidation", "intimidation", "intimidates"),
    "dowry_death": ("dowry death", "dowry", "cruelty to wife"),
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
    "acceptance": "acceptance",
    "void_agreement": "void agreement",
    "voidable_contract": "voidable contract",
    "breach_of_contract": "breach of contract",
    "agency": "agency",
    "indemnity": "indemnity",
    "guarantee": "guarantee",
    "bailment": "bailment",
    "pledge": "pledge",
    "theft": "theft",
    "murder": "murder",
    "culpable_homicide": "culpable homicide",
    "cheating": "cheating",
    "robbery": "robbery",
    "extortion": "extortion",
    "criminal_breach_of_trust": "criminal breach of trust",
    "mischief": "mischief",
    "assault": "assault",
    "rape": "rape",
    "kidnapping": "kidnapping",
    "forgery": "forgery",
    "defamation": "defamation",
    "criminal_intimidation": "criminal intimidation",
    "dowry_death": "dowry death",
    "house_trespass": "house trespass",
    "criminal_trespass": "criminal trespass",
}

# Explicit, verified section numbers per concept. ICA 1872 references are
# ss. 1-238; IPC 1860 references are ss. 239+ (keyed alphanumerically, e.g.
# "304b" for s. 304B) and are unique to the Indian Penal Code. Never extended
# heuristically.
VERIFIED_SECTION_MAPPING: dict[str, tuple[int | str, ...]] = {
    # ICA 1872
    "coercion": (15,),
    "free_consent": (14,),
    "voidable_agreement": (19, 2),
    "fraud": (17,),
    "misrepresentation": (18,),
    "proposal": (2,),
    "consideration": (25, 2),
    "capacity": (11, 12),
    "undue_influence": (16,),
    "acceptance": (2, 7, 8),
    "void_agreement": (24, 25, 30),
    "voidable_contract": (19, 2),
    "breach_of_contract": (73, 74),
    "agency": (182,),
    "indemnity": (124,),
    "guarantee": (126,),
    "bailment": (148,),
    "pledge": (172,),
    # IPC 1860
    "theft": (378,),
    "murder": (300, 302),
    "culpable_homicide": (299, 304),
    "cheating": (415, 420),
    "robbery": (390,),
    "extortion": (383, 384),
    "criminal_breach_of_trust": (405, 406),
    "mischief": (425, 426),
    "assault": (351, 352),
    "rape": (375, 376),
    "kidnapping": (359, 360, 361),
    "forgery": (463, 465),
    "defamation": (499, 500),
    "criminal_intimidation": (503, 506),
    "dowry_death": ("304b",),
    "house_trespass": (442,),
    "criminal_trespass": (441,),
}

# Surface phrases -> expanded concepts. More specific phrases (e.g.
# "forced to sign") are listed before their shorter forms so their concepts are
# always included when both match. IPC phrases deliberately avoid bare words
# that also belong to ICA concepts (e.g. "deceived"/"deceit" stay ICA
# fraud/misrepresentation; "deception" alone maps to IPC cheating).
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
    # free consent (s. 14)
    "without free consent": ("free_consent", "coercion", "voidable_agreement"),
    "not free consent": ("free_consent", "voidable_agreement"),
    "free consent": ("free_consent",),
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
    # acceptance (ss. 2, 7-8)
    "acceptance": ("acceptance",),
    "accepting": ("acceptance",),
    "accepts": ("acceptance",),
    "accepted": ("acceptance",),
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
    # void agreement (ss. 24-25, 30) / voidable contract (ss. 19, 2)
    "void agreement": ("void_agreement",),
    "agreement is void": ("void_agreement",),
    "voidable contract": ("voidable_contract", "voidable_agreement"),
    # breach of contract (ss. 73-74)
    "breach of contract": ("breach_of_contract",),
    "breach of the contract": ("breach_of_contract",),
    "broke the contract": ("breach_of_contract",),
    # agency (s. 182)
    "agent": ("agency",),
    "agency": ("agency",),
    "sub-agent": ("agency",),
    # indemnity (s. 124)
    "indemnity": ("indemnity",),
    "indemnify": ("indemnity",),
    "indemnified": ("indemnity",),
    # guarantee (s. 126)
    "contract of guarantee": ("guarantee",),
    "guarantee": ("guarantee",),
    "guarantor": ("guarantee",),
    "surety": ("guarantee",),
    # bailment (s. 148)
    "bailment": ("bailment",),
    "bailor": ("bailment",),
    "bailee": ("bailment",),
    # pledge (s. 172)
    "pledge": ("pledge",),
    "pawnor": ("pledge",),
    "pawnee": ("pledge",),
    # IPC: theft (s. 378)
    "dishonestly taking property": ("theft",),
    "dishonestly taking": ("theft",),
    "dishonest removal": ("theft",),
    "dishonest taking": ("theft",),
    "stealing": ("theft",),
    "steals": ("theft",),
    "stolen": ("theft",),
    "steal": ("theft",),
    "theft": ("theft",),
    # IPC: murder / culpable homicide (ss. 299-304)
    "culpable homicide": ("culpable_homicide",),
    "murdered": ("murder",),
    "murdering": ("murder",),
    "murders": ("murder",),
    "homicide": ("murder", "culpable_homicide"),
    "killing": ("murder",),
    "killed": ("murder",),
    "kills": ("murder",),
    "murder": ("murder",),
    # IPC: cheating (ss. 415, 420)
    "cheating and dishonestly inducing": ("cheating",),
    "dishonest inducement": ("cheating",),
    "dishonestly inducing": ("cheating",),
    "cheating": ("cheating",),
    "cheated": ("cheating",),
    "cheat": ("cheating",),
    "deception": ("cheating",),
    # IPC: robbery (s. 390)
    "robbery": ("robbery",),
    "robbed": ("robbery",),
    "rob": ("robbery",),
    # IPC: extortion (ss. 383-384)
    "putting in fear": ("extortion",),
    "extortion": ("extortion",),
    "extorted": ("extortion",),
    "extort": ("extortion",),
    # IPC: criminal breach of trust (ss. 405-406)
    "criminal breach of trust": ("criminal_breach_of_trust",),
    "breach of trust": ("criminal_breach_of_trust",),
    "entrusted property": ("criminal_breach_of_trust",),
    # IPC: mischief (ss. 425-426)
    "causing damage to property": ("mischief",),
    "causing damage": ("mischief",),
    "mischief": ("mischief",),
    # IPC: assault (ss. 351-352)
    "criminal force": ("assault",),
    "assaulted": ("assault",),
    "assault": ("assault",),
    # IPC: rape (ss. 375-376)
    "sexually assaulted": ("rape",),
    "raped": ("rape",),
    "rape": ("rape",),
    # IPC: kidnapping (ss. 359-361)
    "kidnapping": ("kidnapping",),
    "kidnapped": ("kidnapping",),
    "kidnap": ("kidnapping",),
    "abduction": ("kidnapping",),
    # IPC: forgery (ss. 463, 465)
    "forgery": ("forgery",),
    "forged": ("forgery",),
    "forging": ("forgery",),
    # IPC: defamation (ss. 499, 500)
    "defamation": ("defamation",),
    "defamed": ("defamation",),
    "defame": ("defamation",),
    "defamatory": ("defamation",),
    # IPC: criminal intimidation (ss. 503, 506)
    "criminal intimidation": ("criminal_intimidation",),
    "intimidation": ("criminal_intimidation",),
    "intimidates": ("criminal_intimidation",),
    # IPC: dowry death (s. 304B)
    "dowry death": ("dowry_death",),
    "dowry": ("dowry_death",),
    # IPC: house / criminal trespass (ss. 441-442)
    "house-breaking": ("house_trespass",),
    "house breaking": ("house_trespass",),
    "house trespass": ("house_trespass",),
    "criminal trespass": ("criminal_trespass",),
    "trespass": ("criminal_trespass",),
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
        f"section {n}" for concept in ordered for n in VERIFIED_SECTION_MAPPING.get(concept, ())
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
