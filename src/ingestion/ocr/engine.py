"""OCR engine with PaddleOCR primary and Tesseract fallback."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PIL import Image

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PaddleOCR (optional)
# ---------------------------------------------------------------------------
_paddle_instance: Any = None


def _get_paddle() -> Any:
    global _paddle_instance
    if _paddle_instance is not None:
        return _paddle_instance
    try:
        from paddleocr import PaddleOCR

        _paddle_instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return _paddle_instance
    except Exception as exc:
        log.info("PaddleOCR unavailable: %s", exc)
        _paddle_instance = False  # type: ignore[assignment]
        return False


def _ocr_with_paddle(image: Image.Image) -> str:
    engine = _get_paddle()
    if not engine:
        raise RuntimeError("PaddleOCR not available")
    import numpy as np

    arr = np.array(image)
    result = engine.ocr(arr, cls=True)
    lines: list[str] = []
    if result and result[0]:
        for item in result[0]:
            if item and len(item) >= 2:
                lines.append(item[1][0])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tesseract (fallback)
# ---------------------------------------------------------------------------

def _ocr_with_tesseract(image: Image.Image, lang: str = "eng") -> str:
    try:
        import pytesseract

        return pytesseract.image_to_string(image, lang=lang)
    except Exception as exc:
        log.warning("Tesseract OCR failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

LANG_MAP: dict[str, str] = {
    "en": "eng",
    "hi": "hin",
    "kn": "kan",
    "ta": "tam",
    "te": "tel",
    "ml": "mal",
    "mr": "mar",
    "bn": "ben",
}


def ocr_image(image: Image.Image, lang: str = "en") -> str:
    """Run OCR on a PIL Image.

    Tries PaddleOCR first; falls back to Tesseract.
    """
    # Try PaddleOCR
    try:
        text = _ocr_with_paddle(image)
        if text.strip():
            return text
    except Exception:
        pass

    # Fallback to Tesseract
    tess_lang = LANG_MAP.get(lang, "eng")
    return _ocr_with_tesseract(image, lang=tess_lang)


def ocr_pdf_page(path: Path, page_number: int, lang: str = "en") -> str:
    """OCR a single page of a PDF.

    Renders the page to an image using pymupdf, then runs OCR.
    """
    from src.ingestion.loaders.pdf_loader import render_page_to_image

    img = render_page_to_image(path, page_number)
    if img is None:
        return ""
    return ocr_image(img, lang=lang)
