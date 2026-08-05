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


@dataclass
class RetrievalQuery:
    """Structured representation of a retrieval query."""

    raw: str
    keywords: list[str] = field(default_factory=list)
    section_refs: list[str] = field(default_factory=list)     # normalized e.g. "section 5"
    section_numbers: list[str] = field(default_factory=list)  # e.g. "5"
    citation_texts: list[str] = field(default_factory=list)   # raw matched citation text
    language: str = "en"

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
    """Parse a natural-language legal query into structured retrieval terms."""
    raw = (raw or "").strip()
    query = RetrievalQuery(raw=raw, language=language)

    for cite in extract_citations(raw):
        if cite.citation_type in _SECTION_LABELS:
            query.section_refs.append(_normalize_section_ref(cite.citation_type, cite.ref_number))
            leading = cite.ref_number.split()[0] if cite.ref_number else ""
            if leading:
                query.section_numbers.append(leading)
            query.citation_texts.append(cite.raw_text)

    for token in tokenize(raw):
        if token in _STOPWORDS:
            continue
        if token not in query.keywords:
            query.keywords.append(token)

    return query
