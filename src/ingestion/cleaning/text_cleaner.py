"""Text cleaning pipeline for legal documents.

Removes headers, footers, page numbers, and duplicate whitespace
while preserving legal numbering conventions.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Patterns for noise removal
# ---------------------------------------------------------------------------

# Common header/footer patterns in Indian legal PDFs
_HEADER_FOOTER_PATTERNS: list[re.Pattern] = [
    # Page numbers like "Page 1 of 10", "- 3 -", "3/10"
    re.compile(r"^(?:[-\s]*page\s+\d+\s*(?:of\s+\d+)?[-\s]*)$", re.I),
    re.compile(r"^\s*[-–—]\s*\d+\s*[-–—]\s*$"),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),
    # Confidentiality / downloaded watermarks
    re.compile(r"downloaded from\s+\w", re.I),
    re.compile(r"©.*?reserved", re.I),
    re.compile(r"this is an? (?:computer|electronic)", re.I),
    # Court header boilerplate (common in Indian judgments)
    re.compile(r"^before the hon['']?ble", re.I),
    re.compile(r"^in the (?:supreme|high|district|sessions) court", re.I),
    re.compile(r"^writ petition no", re.I),
]

# Legal numbering: Section 123, Rule 45-A, Clause (iii), Article 14, Order VII Rule 11
_LEGAL_NUMBER_RE = re.compile(
    r"(?:(?:section|rule|clause|article|order|regulation|notification|circular|act|amendment)"
    r"\s*\d+[A-Za-z]*(?:\s*\([a-zA-Z0-9]+\))*)",
    re.I,
)


def _is_noise_line(line: str) -> bool:
    """Return True if a line is likely a header, footer, or page number."""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in _HEADER_FOOTER_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def _collapse_whitespace(text: str) -> str:
    """Remove duplicate whitespace while preserving newlines."""
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text


def _preserve_legal_numbering(text: str) -> str:
    """Ensure legal references are not broken across lines."""
    # Join lines where a legal reference is split
    text = re.sub(r"\n(\d+[A-Za-z]*\.)", r" \1", text)
    text = re.sub(r"\n\(([a-zA-Z0-9]+)\)", r" (\1)", text)
    return text


def clean_text(text: str) -> str:
    """Full cleaning pipeline for a single page of legal text.

    Steps:
    1. Normalize Unicode
    2. Remove headers / footers / page numbers
    3. Preserve legal numbering
    4. Collapse duplicate whitespace
    """
    if not text:
        return ""

    # Unicode normalization
    import unicodedata

    text = unicodedata.normalize("NFKC", text)

    # Remove header/footer noise lines
    lines = text.split("\n")
    cleaned = [line for line in lines if not _is_noise_line(line)]
    text = "\n".join(cleaned)

    # Preserve legal numbering across line breaks
    text = _preserve_legal_numbering(text)

    # Collapse whitespace
    text = _collapse_whitespace(text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def clean_pages(pages: list[str]) -> list[str]:
    """Apply cleaning to all pages."""
    return [clean_text(page) for page in pages]
