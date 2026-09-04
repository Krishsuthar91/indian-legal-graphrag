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
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "under", "per", "vs", "v", "act", "section", "sec", "sections",
    "article", "articles", "rule", "rules", "order", "orders", "what", "which",
    "who", "whom", "how", "does", "do", "did", "is", "are", "was", "were", "be",
    "been", "being", "about", "provide", "provides", "provided", "provisions",
    "provision", "means", "mean", "explain", "explains", "define", "defines",
    "definition", "according", "shall", "may", "not", "any", "all", "each",
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
}


@dataclass
class RetrievalQuery:
    """Structured representation of a retrieval query."""

    raw: str
    keywords: list[str] = field(default_factory=list)
    section_refs: list[str] = field(default_factory=list)     # normalized e.g. "section 5"
    section_numbers: list[str] = field(default_factory=list)  # e.g. "5"
    citation_texts: list[str] = field(default_factory=list)   # raw matched citation text
    language: str = "en"
    act_name: str = ""       # e.g. "Indian Contract Act"
    document_id: str = ""    # resolved document UUID hex, e.g. "0d1934142f67c5f5"

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
            t for t in (
                tok.strip(" \t.,;:!?()[]{}<>\"'‘’“”–—-")
                for tok in re.split(r"\s+", text.lower())
            )
            if t
        ]
    return re.findall(r"[a-z0-9]+", text.lower())


def _normalize_section_ref(citation_type: str, ref_number: str) -> str:
    label = _SECTION_LABELS.get(citation_type, citation_type)
    return f"{label} {ref_number}".strip()


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

    # Fallback: try to match an act abbreviation at the start of the raw query
    # when the citation extractor didn't already resolve an act name.
    # E.g. "IPC Section 420" → "ipc" before the section ref.
    if not query.document_id and not query.act_name:
        raw_lower = raw.lower().strip()
        for pattern, doc_id in _ACT_NAME_TO_DOC_ID.items():
            if raw_lower.startswith(pattern):
                query.document_id = doc_id
                query.act_name = raw[len(pattern):].strip().lstrip(", ")
                break

    for token in tokenize(raw):
        if token in _STOPWORDS:
            continue
        # Section numbers (e.g. "10" from "Section 10") should not be used as
        # content keywords for text matching — they are handled by citation_score.
        if token in query.section_numbers:
            continue
        # Act names/abbreviations should not be content keywords either.
        if query.document_id and token in query.act_name.lower().split():
            continue
        if token not in query.keywords:
            query.keywords.append(token)

    return query
