"""Query intent detection and adaptive top-k selection.

Classifies a parsed legal query into one of eight intent classes so the
retrieval layer can adapt how many evidence nodes it fetches:

- easy budgets:    definition, section_lookup, explanation
- medium budgets:  punishment, procedural, comparison, constitutional
- complex budgets: case_law
"""

from __future__ import annotations

import re

from src.retrieval.query import RetrievalQuery, parse_query

DEFINITION = "definition"
SECTION_LOOKUP = "section_lookup"
PUNISHMENT = "punishment"
PROCEDURAL = "procedural"
CONSTITUTIONAL = "constitutional"
CASE_LAW = "case_law"
COMPARISON = "comparison"
EXPLANATION = "explanation"

INTENTS: tuple[str, ...] = (
    DEFINITION,
    SECTION_LOOKUP,
    PUNISHMENT,
    PROCEDURAL,
    CONSTITUTIONAL,
    CASE_LAW,
    COMPARISON,
    EXPLANATION,
)

# Default adaptive budgets per intent bucket (overridable via settings).
EASY_TOP_K = 4
MEDIUM_TOP_K = 7
COMPLEX_TOP_K = 12

# Marker phrases per intent. Multi-word markers match as substrings of the
# lowercased raw query; single-word markers match at word boundaries so e.g.
# "fine" does not fire inside "defines".
_DEFINITION_MARKERS = (
    "define", "defined", "definition", "meaning", "means", "mean",
    "interpretation", "interpret", "construed",
)
_PUNISHMENT_MARKERS = (
    "punish", "punishment", "penalty", "penal", "offence", "offense",
    "imprison", "imprisonment", "fine", "guilty", "criminal",
)
_PROCEDURAL_MARKERS = (
    "procedure", "procedural", "process", "how to", "how do", "file a",
    "filed", "complaint", "summon", "summons", "appeal", "jurisdiction",
    "limitation", "pleading", "pleadings", "evidence act",
)
_CONSTITUTIONAL_MARKERS = (
    "constitution", "constitutional", "fundamental right",
    "fundamental rights", "directive principle",
)
_CASE_LAW_MARKERS = (
    "supreme court", "high court", "judgment", "judgement", "precedent",
    "case law", "landmark",
)
_COMPARISON_MARKERS = (
    "compare", "comparison", "difference", "differ", "distinguish",
    "distinction", "versus", "vs", "differentiate", "similar",
)
_EXPLANATION_MARKERS = ("explain", "explanation", "what is", "how", "why")

# Matches Indian case-citation forms (AIR 1965 SC 123, (2001) 2 SCC 123, ...).
# raw queries are lowercased before matching, so the alternation is lowercase.
_CASE_CITE_RE = re.compile(r"\b(?:air|scc|scr)\b")


def _has_marker(raw: str, marker: str) -> bool:
    marker = marker.lower()
    if " " in marker:
        return marker in raw
    return re.search(rf"\b{re.escape(marker)}\b", raw) is not None


def _has_any(raw: str, markers: tuple[str, ...]) -> bool:
    return any(_has_marker(raw, m) for m in markers)


def detect_intent(query: RetrievalQuery | str) -> str:
    """Classify a parsed (or raw) legal query into one intent class.

    Section/rule/article references win outright (``section_lookup``), then
    case-law signals, then the remaining keyword-driven intents, with
    ``explanation`` as the neutral fallback.
    """
    if isinstance(query, str):
        query = parse_query(query)
    raw = (query.raw or "").lower()

    if query.section_refs or query.section_numbers:
        return SECTION_LOOKUP
    if _has_any(raw, _CASE_LAW_MARKERS) or _CASE_CITE_RE.search(raw):
        return CASE_LAW
    if _has_any(raw, _DEFINITION_MARKERS):
        return DEFINITION
    if _has_any(raw, _PUNISHMENT_MARKERS):
        return PUNISHMENT
    if _has_any(raw, _CONSTITUTIONAL_MARKERS):
        return CONSTITUTIONAL
    if _has_any(raw, _COMPARISON_MARKERS):
        return COMPARISON
    if _has_any(raw, _PROCEDURAL_MARKERS):
        return PROCEDURAL
    return EXPLANATION


def adaptive_top_k(
    intent: str,
    easy: int = EASY_TOP_K,
    medium: int = MEDIUM_TOP_K,
    complex: int = COMPLEX_TOP_K,
) -> int:
    """Return the adaptive evidence budget for an intent class."""
    if intent in (DEFINITION, SECTION_LOOKUP, EXPLANATION):
        return easy
    if intent in (PUNISHMENT, PROCEDURAL, COMPARISON, CONSTITUTIONAL):
        return medium
    return complex
