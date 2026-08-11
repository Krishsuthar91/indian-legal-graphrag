"""Legal section-reference normalization and matching for evaluation.

The benchmark CSV stores expected legal references (e.g. ``S.2(a)``,
``S.124, S.126``) that must be compared against the sections surfaced by the
retrieval pipeline. This module normalizes both sides into comparable keys and
implements the prefix-aware matching used by section accuracy, citation
accuracy, and relevance-set construction.

Design notes:
- Expected references and node-derived references are normalized to a compact
  lowercase alphanumeric key (``S.2(a)`` -> ``2a``, ``Section 65`` -> ``65``).
- A node key ``N`` matches an expected key ``E`` when the keys are equal or
  when ``E`` starts with ``N`` (the parent section covers its sub-clauses, so
  a retrieved ``Section 2`` node satisfies an expectation of ``S.2(a)``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_SECTION_REF_RE = re.compile(
    r"(?:section|sec\.?|s\.?)\s*(\d{1,3}(?:[a-z]|(?:\([a-z0-9]+\)))?)",
    re.IGNORECASE,
)

# Embedded section numbers in node numbering/title text, e.g. ``124.`` from
# ``124. "Contract of indemnity" defined`` or ``294A``. Four-digit numbers
# (such as the 1872 year) are intentionally excluded.
_EMBEDDED_SECTION_RE = re.compile(
    r"(?<![\d.])"
    r"(\d{1,3}(?:[a-z](?![\w.])|(?:\([a-z0-9]+\)))?)"
    r"(?![\d])",
    re.IGNORECASE,
)

_BARE_SECTION_RE = re.compile(r"(\d{1,3}(?:[a-z]|(?:\([a-z0-9]+\)))?)", re.IGNORECASE)


def normalize_section(text: str) -> str:
    """Normalize one expected section reference to a lowercase key.

    ``S.2(a)`` -> ``2a``, ``Section 65`` -> ``65``, ``S.27 Exception 1`` ->
    ``27``. Returns an empty string when no section number can be found.
    """
    text = (text or "").strip()
    match = _SECTION_REF_RE.search(text)
    if match:
        return match.group(1).lower()
    match = _BARE_SECTION_RE.search(text)
    if match:
        return match.group(1).lower()
    return ""


def normalize_sections(text: str) -> list[str]:
    """Normalize a comma-separated list of expected section references.

    ``S.2(g), S.2(i)`` -> ``["2g", "2i"]`` (order preserved, duplicates kept).
    """
    if not text or not text.strip():
        return []
    parts = [part for part in text.split(",") if part.strip()]
    return [key for part in parts if (key := normalize_section(part))]


def section_keys_from_text(text: str) -> set[str]:
    """Extract section keys embedded in node numbering/title text.

    Returns a deduplicated set of keys. Example inputs:
    ``124. "Contract of indemnity" defined`` -> ``{"124"}``,
    ``53`` -> ``{"53"}``, ``294A`` -> ``{"294a"}``.
    """
    if not text:
        return set()
    keys: set[str] = set()
    for match in _EMBEDDED_SECTION_RE.finditer(text):
        keys.add(match.group(1).lower())
    return keys


def node_section_keys(node: dict) -> set[str]:
    """All section keys for a graph node (from numbering and title)."""
    keys: set[str] = set()
    keys.update(section_keys_from_text(node.get("numbering", "")))
    keys.update(section_keys_from_text(node.get("title", "")))
    return {key for key in keys if key}


def predicted_sections(evidence_nodes: Iterable) -> set[str]:
    """Union of section keys across retrieved evidence entries.

    Each evidence entry may be an ``Evidence`` dataclass or a plain dict with
    ``numbering`` / ``title`` keys.
    """
    predicted: set[str] = set()
    for ev in evidence_nodes:
        if isinstance(ev, dict):
            numbering, title = ev.get("numbering", ""), ev.get("title", "")
        else:
            numbering, title = ev.numbering, ev.title
        predicted.update(section_keys_from_text(numbering))
        predicted.update(section_keys_from_text(title))
    return predicted


def section_match(expected_key: str, predicted_keys: Iterable[str]) -> bool:
    """True when any predicted key matches the expected section key."""
    if not expected_key:
        return False
    for candidate in predicted_keys:
        if matches(expected_key, candidate):
            return True
    return False


def matches(expected_key: str, node_key: str) -> bool:
    """Prefix-aware section match: equal keys or parent-section coverage."""
    expected = _normalize_key(expected_key)
    candidate = _normalize_key(node_key)
    if not expected or not candidate:
        return False
    if expected == candidate:
        return True
    if candidate.isdigit() and expected.startswith(candidate):
        return True
    return False


def _normalize_key(key: str) -> str:
    """Collapse a section key to lowercase alphanumerics (``2(a)`` -> ``2a``)."""
    return re.sub(r"[^a-z0-9]", "", (key or "").lower())


def section_coverage(expected_keys: Iterable[str], predicted_keys: Iterable[str]) -> float:
    """Fraction of expected sections covered by the predicted set, in [0, 1]."""
    expected = [key for key in expected_keys if key]
    if not expected:
        return 0.0
    matched = sum(1 for key in expected if section_match(key, predicted_keys))
    return matched / len(expected)
