"""Legal citation extraction from text using regex patterns.

Handles Indian legal citation formats:
- Section 10, Section 34 of the Indian Contract Act
- Rule 45-A
- Article 14
- Order VII Rule 11
- AIR 1965 SC 123
- (2001) 2 SCC 123
- 2001 SCC (Cri) 123
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Citation:
    """A extracted citation from text."""

    citation_type: str   # section, rule, article, order, case
    raw_text: str        # the full matched text
    ref_number: str = "" # e.g. "12", "45-A", "VII Rule 11"
    act_name: str = ""   # e.g. "Indian Contract Act"
    case_name: str = ""  # e.g. "AIR 1965 SC 123"
    court: str = ""      # e.g. "SC", "Bombay HC"
    year: str = ""       # e.g. "1965"
    start: int = 0       # start position in text
    end: int = 0         # end position in text


# ---------------------------------------------------------------------------
# Section / Rule / Article patterns
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r"(?:Sections?|Sec\.?|S\.)\s+(\d+[A-Za-z]*(?:\s*[-–]\s*\d*[A-Za-z]*)?)"
    r"(?:\s+(?:of|under)\s+((?:the\s+)?[A-Z][\w\s,]*))?",
    re.I,
)

_RULE_RE = re.compile(
    r"Rules?\s+(\d+[A-Za-z]*(?:\s*[-–]\s*\d*[A-Za-z]*)?)"
    r"(?:\s+(?:of|under)\s+((?:the\s+)?[A-Z][\w\s,]*))?",
    re.I,
)

_ARTICLE_RE = re.compile(
    r"Articles?\s+(\d+[A-Za-z]*)"
    r"(?:\s+(?:of|under)\s+((?:the\s+)?[A-Z][\w\s,]*))?",
    re.I,
)

_ORDER_RE = re.compile(
    r"Orders?\s+([IVXLC]+)\s+Rules?\s+(\d+[A-Za-z]*)"
    r"(?:\s+(?:of|under)\s+((?:the\s+)?[A-Z][\w\s,]*))?",
    re.I,
)

# ---------------------------------------------------------------------------
# Case citation patterns (Indian formats)
# ---------------------------------------------------------------------------

# AIR 1965 SC 123
_AIR_RE = re.compile(
    r"AIR\s+(\d{4})\s+([A-Z]{2,10})\s+(\d+)",
)

# (2001) 2 SCC 123
_PAREN_YEAR_RE = re.compile(
    r"\((\d{4})\)\s+(\d+)\s+(SCC|SCR|AIR|Cri)\s+(\d+)",
)

# 2001 SCC (Cri) 123
_YEAR_COURT_RE = re.compile(
    r"(\d{4})\s+(SCC|SCR|AIR|Cri)\s*\((\w+)\)\s+(\d+)",
)


def extract_citations(text: str) -> list[Citation]:
    """Extract all legal citations from a text block."""
    citations: list[Citation] = []
    seen: set[str] = set()

    def _add(c: Citation) -> None:
        key = f"{c.citation_type}:{c.raw_text}"
        if key not in seen:
            seen.add(key)
            citations.append(c)

    # Section citations
    for m in _SECTION_RE.finditer(text):
        _add(Citation(
            citation_type="section",
            raw_text=m.group(0).strip(),
            ref_number=m.group(1),
            act_name=m.group(2).strip() if m.group(2) else "",
            start=m.start(),
            end=m.end(),
        ))

    # Rule citations
    for m in _RULE_RE.finditer(text):
        _add(Citation(
            citation_type="rule",
            raw_text=m.group(0).strip(),
            ref_number=m.group(1),
            act_name=m.group(2).strip() if m.group(2) else "",
            start=m.start(),
            end=m.end(),
        ))

    # Article citations
    for m in _ARTICLE_RE.finditer(text):
        _add(Citation(
            citation_type="article",
            raw_text=m.group(0).strip(),
            ref_number=m.group(1),
            act_name=m.group(2).strip() if m.group(2) else "",
            start=m.start(),
            end=m.end(),
        ))

    # Order + Rule citations
    for m in _ORDER_RE.finditer(text):
        _add(Citation(
            citation_type="order",
            raw_text=m.group(0).strip(),
            ref_number=f"Order {m.group(1)} Rule {m.group(2)}",
            act_name=m.group(3).strip() if m.group(3) else "",
            start=m.start(),
            end=m.end(),
        ))

    # AIR case citations
    for m in _AIR_RE.finditer(text):
        _add(Citation(
            citation_type="case",
            raw_text=m.group(0).strip(),
            case_name=m.group(0).strip(),
            court=m.group(2),
            year=m.group(1),
            start=m.start(),
            end=m.end(),
        ))

    # (Year) Vol Court Page
    for m in _PAREN_YEAR_RE.finditer(text):
        _add(Citation(
            citation_type="case",
            raw_text=m.group(0).strip(),
            case_name=m.group(0).strip(),
            court=m.group(3),
            year=m.group(1),
            start=m.start(),
            end=m.end(),
        ))

    # Year Court (Bench) Page
    for m in _YEAR_COURT_RE.finditer(text):
        _add(Citation(
            citation_type="case",
            raw_text=m.group(0).strip(),
            case_name=m.group(0).strip(),
            court=m.group(2),
            year=m.group(1),
            start=m.start(),
            end=m.end(),
        ))

    return citations
