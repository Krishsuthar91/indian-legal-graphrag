"""Detect whether a PDF page is scanned (image-based) or digital (text-based)."""

from __future__ import annotations

from pathlib import Path

import pdfplumber


def is_scanned_pdf(path: Path, sample_pages: int = 5) -> bool:
    """Determine if a PDF is scanned by checking text content across sample pages.

    Returns True if most sampled pages have little or no extractable text.
    """
    with pdfplumber.open(path) as pdf:
        total = min(len(pdf.pages), sample_pages)
        if total == 0:
            return True

        empty_count = 0
        for i in range(total):
            text = pdf.pages[i].extract_text() or ""
            if len(text.strip()) < 50:
                empty_count += 1

        return empty_count > total / 2


def is_page_scanned(page) -> bool:
    """Check if a single pdfplumber page is scanned (image-based)."""
    text = page.extract_text() or ""
    images = page.images or []
    has_text = len(text.strip()) > 50
    has_images = len(images) > 0
    return has_images and not has_text
