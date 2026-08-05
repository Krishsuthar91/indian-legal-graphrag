"""PDF document loader using pdfplumber with pymupdf fallback for rendering."""

from __future__ import annotations

from pathlib import Path

import pdfplumber


def load_pdf(path: Path) -> tuple[list[str], dict]:
    """Extract text from each page of a PDF.

    Returns:
        (pages_text, pdf_properties) where pages_text is a list of strings
        and pdf_properties is a dict of PDF-level metadata.
    """
    pages_text: list[str] = []
    props: dict = {}

    with pdfplumber.open(path) as pdf:
        props: dict = {"page_count": len(pdf.pages)}
        metadata = pdf.metadata
        if metadata:
            props.update({k: str(v) for k, v in metadata.items() if v is not None})

        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

    return pages_text, props


def pdf_has_text(path: Path) -> bool:
    """Check whether a PDF contains any extractable text."""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:5]:
            text = page.extract_text()
            if text and text.strip():
                return True
    return False


def render_page_to_image(path: Path, page_number: int, dpi: int = 300):
    """Render a PDF page to a PIL Image using pymupdf (fitz).

    Used by the OCR engine to process scanned pages.
    Returns a PIL Image or None on failure.
    """
    try:
        import fitz  # pymupdf

        doc = fitz.open(str(path))
        if page_number < 1 or page_number > len(doc):
            doc.close()
            return None
        page = doc[page_number - 1]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(pix.tobytes("png")))
        doc.close()
        return img
    except ImportError:
        return None
