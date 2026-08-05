"""Regex patterns for detecting legal document numbering styles.

Each pattern returns a tuple of (node_type, level, numbering_text, title).
Patterns are ordered by specificity — more specific patterns are tried first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NumberingMatch:
    """Result of matching a line against legal numbering patterns."""

    node_type: str
    level: int
    numbering: str  # raw matched text
    title: str  # extracted title after numbering


# ---------------------------------------------------------------------------
# Roman numeral helpers
# ---------------------------------------------------------------------------
_ROMAN_ONES = "IVXLCDM"

_ROMAN_MAP: dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
    "XXI": 21, "XXII": 22, "XXIII": 23, "XXIV": 24, "XXV": 25,
    "XXVI": 26, "XXVII": 27, "XXVIII": 28, "XXIX": 29, "XXX": 30,
}

_ROMAN_PATTERN = "|".join(sorted(_ROMAN_MAP.keys(), key=len, reverse=True))

# ---------------------------------------------------------------------------
# Level constants (lower = higher in hierarchy)
# ---------------------------------------------------------------------------
LVL_DOCUMENT = 0
LVL_ACT_TITLE = 1
LVL_SCHEDULE = 1
LVL_APPENDIX = 1
LVL_PREAMBLE = 2
LVL_PART = 3
LVL_CHAPTER = 4
LVL_SECTION = 5
LVL_SUB_SECTION = 6
LVL_CLAUSE = 7
LVL_SUB_CLAUSE = 8
LVL_EXPLANATION = 9
LVL_ILLUSTRATION = 9
LVL_PROVISO = 9
LVL_BODY = 10  # fallback for unrecognized text

# ---------------------------------------------------------------------------
# Compiled patterns — each returns (node_type, level)
# Order matters: first match wins within the same line.
# ---------------------------------------------------------------------------

@dataclass
class _Pat:
    regex: re.Pattern
    node_type: str
    level: int
    group: int = 1  # which capture group holds the numbering


_PATTERNS: list[_Pat] = [
    # --- Schedule / Appendix (highest structural level) ---
    _Pat(
        re.compile(r"^\s*(?:SCHEDULE|SCHEDULE\s+\d+|[A-Z]\.\s*SCHEDULE)\s*$", re.I),
        "schedule", LVL_SCHEDULE,
    ),
    _Pat(
        re.compile(r"^\s*(?:APPENDIX|APPENDIX\s+[A-Z]|APPENDIX\s+\d+)\s*$", re.I),
        "appendix", LVL_APPENDIX,
    ),

    # --- Part ---
    _Pat(
        re.compile(
            rf"^\s*PART\s+(?:{_ROMAN_PATTERN}|[A-Z]|\d+)\s*$", re.I
        ),
        "part", LVL_PART,
    ),
    _Pat(
        re.compile(r"^\s*Part\s+(\d+)\s*$", re.I),
        "part", LVL_PART,
    ),

    # --- Chapter ---
    _Pat(
        re.compile(
            rf"^\s*CHAPTER\s+(?:{_ROMAN_PATTERN}|\d+)\s*[-–—]?\s*(.*)", re.I
        ),
        "chapter", LVL_CHAPTER,
    ),
    _Pat(
        re.compile(r"^\s*Chapter\s+(\d+)\s*(.*)", re.I),
        "chapter", LVL_CHAPTER,
    ),

    # --- Section (explicit keyword) ---
    _Pat(
        re.compile(r"^\s*(?:Section|Sec\.?|S\.)\s+(\d+[A-Za-z]*(?:\s*[-–]\s*[A-Z])?)\s*(.*)", re.I),
        "section", LVL_SECTION,
    ),

    # --- Section (bare number + dot, e.g. "12.") ---
    _Pat(
        re.compile(r"^\s*(\d+[A-Za-z]*)\.\s+(.*)"),
        "section", LVL_SECTION,
    ),

    # --- Sub-section: (1), (2), (3) ---
    _Pat(
        re.compile(r"^\s*\((\d+)\)\s*(.*)"),
        "sub_section", LVL_SUB_SECTION,
    ),

    # --- Sub-clause: (i), (ii), (iii) ---  (checked before clause to avoid conflict)
    _Pat(
        re.compile(r"^\s*\(([ivxlcdm]+)\)\s*(.*)", re.I),
        "sub_clause", LVL_SUB_CLAUSE,
    ),

    # --- Clause: (a), (b), (c) ---
    _Pat(
        re.compile(r"^\s*\(([a-z])\)\s*(.*)"),
        "clause", LVL_CLAUSE,
    ),

    # --- Explanation ---
    _Pat(
        re.compile(r"^\s*Explanation\s*(?:\d+)?\.?\s*:?\s*(.*)", re.I),
        "explanation", LVL_EXPLANATION,
    ),

    # --- Illustration ---
    _Pat(
        re.compile(r"^\s*Illustration\s*(?:\d+)?\.?\s*:?\s*(.*)", re.I),
        "illustration", LVL_ILLUSTRATION,
    ),

    # --- Proviso ---
    _Pat(
        re.compile(r"^\s*Proviso\s*(?:\d+)?\.?\s*:?\s*(.*)", re.I),
        "proviso", LVL_PROVISO,
    ),
]


def match_line(line: str) -> NumberingMatch | None:
    """Try to match a line against all legal numbering patterns.

    Returns a NumberingMatch if successful, None otherwise.
    """
    stripped = line.strip()
    if not stripped:
        return None

    for pat in _PATTERNS:
        m = pat.regex.match(stripped)
        if m:
            numbering = m.group(1) if pat.group <= len(m.groups()) else stripped
            title_part = m.group(2) if pat.group == 1 and len(m.groups()) >= 2 else ""
            if not title_part and pat.group > 1:
                title_part = m.group(1) if len(m.groups()) >= 1 else ""
            return NumberingMatch(
                node_type=pat.node_type,
                level=pat.level,
                numbering=numbering.strip() if numbering else stripped,
                title=title_part.strip() if title_part else stripped,
            )
    return None
