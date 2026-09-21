"""Query parsing and normalization for graph retrieval.

Converts a natural-language legal query into structured retrieval terms:
- keywords: cleaned content tokens
- section_refs / section_numbers: normalized legal references (Section 5, Rule 12, ...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.knowledge_graph.citation_extractor import extract_citations

_STOPWORDS: set[str] = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "under",
    "per",
    "vs",
    "v",
    "act",
    "section",
    "sec",
    "sections",
    "article",
    "articles",
    "rule",
    "rules",
    "order",
    "orders",
    "what",
    "which",
    "who",
    "whom",
    "how",
    "does",
    "do",
    "did",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "about",
    "provide",
    "provides",
    "provided",
    "provisions",
    "provision",
    "means",
    "mean",
    "explain",
    "explains",
    "define",
    "defines",
    "definition",
    "according",
    "shall",
    "may",
    "not",
    "any",
    "all",
    "each",
}

_SECTION_LABELS: dict[str, str] = {
    "section": "section",
    "rule": "rule",
    "article": "article",
    "order": "order",
}


_ACT_NAME_TO_DOC_ID: dict[str, str] = {
    "indian contract act": "0d1934142f67c5f5",
    "indian contract act, 1872": "0d1934142f67c5f5",
    "indian contract act 1872": "0d1934142f67c5f5",
    "contract act": "0d1934142f67c5f5",
    "contract act, 1872": "0d1934142f67c5f5",
    "contract act 1872": "0d1934142f67c5f5",
    "ica": "0d1934142f67c5f5",
    "indian penal code": "cf20a14c52127fd5",
    "indian penal code, 1860": "cf20a14c52127fd5",
    "indian penal code 1860": "cf20a14c52127fd5",
    "ipc": "cf20a14c52127fd5",
    # Generic "the Act" — contextually the primary domain Act (ICA 1872).
    "the act": "0d1934142f67c5f5",
}

# Canonical display names for each known act pattern (used for query.act_name).
_ACT_DISPLAY_NAMES: dict[str, str] = {
    "indian contract act": "Indian Contract Act",
    "indian contract act, 1872": "Indian Contract Act, 1872",
    "indian contract act 1872": "Indian Contract Act, 1872",
    "contract act": "Contract Act",
    "contract act, 1872": "Contract Act, 1872",
    "contract act 1872": "Contract Act, 1872",
    "ica": "ICA",
    "indian penal code": "Indian Penal Code",
    "indian penal code, 1860": "Indian Penal Code, 1860",
    "indian penal code 1860": "Indian Penal Code, 1860",
    "ipc": "IPC",
    "the act": "the Act",
}

# Pre-compiled, word-boundary anchored patterns for every known Act name or
# abbreviation, ordered longest-first so the most specific phrase wins (e.g.
# "Indian Contract Act" is preferred over "Contract Act").
_ACT_PATTERNS: list[tuple[re.Pattern, str, str]] = sorted(
    (
        (
            re.compile(rf"(?<!\w){re.escape(pattern)}(?!\w)", re.I),
            _ACT_DISPLAY_NAMES.get(pattern, pattern.title()),
            doc_id,
        )
        for pattern, doc_id in _ACT_NAME_TO_DOC_ID.items()
    ),
    key=lambda entry: len(entry[0].pattern),
    reverse=True,
)


@dataclass
class RetrievalQuery:
    """Structured representation of a retrieval query."""

    raw: str
    keywords: list[str] = field(default_factory=list)
    section_refs: list[str] = field(default_factory=list)  # normalized e.g. "section 5"
    section_numbers: list[str] = field(default_factory=list)  # e.g. "5"
    citation_texts: list[str] = field(default_factory=list)  # raw matched citation text
    language: str = "en"
    act_name: str = ""  # e.g. "Indian Contract Act"
    document_id: str = ""  # resolved document UUID hex, e.g. "0d1934142f67c5f5"

    @property
    def is_empty(self) -> bool:
        return not self.keywords and not self.section_refs


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase word tokens.

    Latin text is split on non-alphanumerics. Non-ASCII (Indic) scripts are
    split on whitespace and stripped of surrounding punctuation, preserving
    matra-bearing syllables as single tokens.
    """
    if not text:
        return []
    if re.search(r"[^\x00-\x7F]", text):
        return [
            t
            for t in (
                tok.strip(" \t.,;:!?()[]{}<>\"'‘’“”–—-") for tok in re.split(r"\s+", text.lower())
            )
            if t
        ]
    return re.findall(r"[a-z0-9]+", text.lower())


def _normalize_section_ref(citation_type: str, ref_number: str) -> str:
    label = _SECTION_LABELS.get(citation_type, citation_type)
    return f"{label} {ref_number}".strip()


def _match_act_name(raw: str) -> tuple[str, str] | None:
    """Resolve a known Act name / abbreviation anywhere in ``raw``.

    Returns ``(display_name, document_id)`` for the first known pattern found,
    or ``None`` when the query names no supported Act.  Handles trailing forms
    ("Section 378 IPC", "Explain Section 5 Contract Act"), leading forms
    ("IPC Section 302") and the generic "the Act".
    """
    if not raw:
        return None
    for pattern, display, doc_id in _ACT_PATTERNS:
        if pattern.search(raw):
            return display, doc_id
    return None


def parse_query(raw: str, language: str = "en") -> RetrievalQuery:
    """Parse a natural-language legal query into structured retrieval terms.

    Extracts act name from inline citations (e.g. "Section 10 of the Indian
    Contract Act") and resolves it to a known ``document_id`` via
    ``_ACT_NAME_TO_DOC_ID``.  Also handles act abbreviations appearing before
    the section reference (e.g. "IPC Section 420").
    """
    raw = (raw or "").strip()
    query = RetrievalQuery(raw=raw, language=language)

    for cite in extract_citations(raw):
        if cite.citation_type in _SECTION_LABELS:
            query.section_refs.append(_normalize_section_ref(cite.citation_type, cite.ref_number))
            leading = cite.ref_number.split()[0] if cite.ref_number else ""
            if leading:
                query.section_numbers.append(leading)
            query.citation_texts.append(cite.raw_text)
        if cite.act_name and not query.act_name:
            query.act_name = cite.act_name

    if query.act_name:
        normalized = query.act_name.lower().strip()
        for pattern, doc_id in _ACT_NAME_TO_DOC_ID.items():
            if pattern in normalized or normalized in pattern:
                query.document_id = doc_id
                break

    # Fallback: resolve an Act name / abbreviation appearing anywhere in the
    # raw query when the citation extractor didn't already resolve one.  This
    # handles trailing abbreviations ("Section 378 IPC"), trailing full names
    # ("Explain Section 5 Contract Act"), leading abbreviations
    # ("IPC Section 302") and the generic "the Act" default (→ ICA 1872).
    if not query.document_id and not query.act_name:
        resolved = _match_act_name(raw)
        if resolved:
            query.act_name, query.document_id = resolved

    for token in tokenize(raw):
        if token in _STOPWORDS:
            continue
        # Section numbers (e.g. "10" from "Section 10") should not be used as
        # content keywords for text matching — they are handled by citation_score.
        if token in query.section_numbers:
            continue
        if token not in query.keywords:
            query.keywords.append(token)

    # Act names/abbreviations should not be content keywords, but when the
    # resolved act name is the entire substantive content of the query (e.g. a
    # bare "Indian Contract Act" query) its words are kept so text scoring can
    # still match.  When other content keywords exist, the act-name tokens are
    # dropped as before.
    if query.document_id and query.act_name:
        act_words = set(query.act_name.lower().split())
        remaining = [t for t in query.keywords if t not in act_words]
        if remaining:
            query.keywords = remaining

    return query
