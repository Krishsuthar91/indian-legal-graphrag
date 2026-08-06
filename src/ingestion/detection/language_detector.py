"""Language detection for multilingual Indian legal documents.

Uses langdetect as primary engine with Unicode script-range heuristics
for Indic languages that langdetect may misclassify.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Unicode ranges for Indic scripts (BMP)
# ---------------------------------------------------------------------------
_SCRIPT_RANGES: list[tuple[str, int, int]] = [
    ("hi", 0x0900, 0x097F),  # Devanagari (Hindi, Marathi)
    ("bn", 0x0980, 0x09FF),  # Bengali
    ("ta", 0x0B80, 0x0BFF),  # Tamil
    ("te", 0x0C00, 0x0C7F),  # Telugu
    ("kn", 0x0C80, 0x0CFF),  # Kannada
    ("ml", 0x0D00, 0x0D7F),  # Malayalam
]

# langdetect code → our canonical code
_LANG_ALIASES: dict[str, str] = {
    "en": "en",
    "hi": "hi",
    "mr": "hi",       # Marathi uses Devanagari; map to hi for now
    "bn": "bn",
    "ta": "ta",
    "te": "te",
    "kn": "kn",
    "ml": "ml",
}

SUPPORTED_LANGUAGES = {"en", "hi", "bn", "ta", "te", "kn", "ml"}


def _script_detection(text: str) -> str | None:
    """Detect language from dominant Unicode script."""
    counts: dict[str, int] = {code: 0 for code, _, _ in _SCRIPT_RANGES}
    for ch in text:
        cp = ord(ch)
        for code, lo, hi in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[code] += 1
                break
    if not any(counts.values()):
        return None
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def detect_language(text: str) -> str:
    """Detect the primary language of a text block.

    Strategy:
    1. Use Unicode script detection for Indic scripts.
    2. Fall back to langdetect.
    3. Default to English.
    """
    if not text or not text.strip():
        return "en"

    # Script-based detection (fast, reliable for Indic scripts)
    script_lang = _script_detection(text)
    if script_lang and script_lang in SUPPORTED_LANGUAGES:
        return script_lang

    # langdetect fallback
    try:
        from langdetect import detect as _ld_detect

        raw = _ld_detect(text[:5000])
        return _LANG_ALIASES.get(raw, "en")
    except Exception:
        return "en"


def detect_document_language(pages: list[str]) -> str:
    """Detect the dominant language across all pages of a document.

    Samples up to 3 pages and picks the most frequent language.
    """
    if not pages:
        return "en"

    sample = pages[:3]
    combined = "\n".join(sample)
    return detect_language(combined)
