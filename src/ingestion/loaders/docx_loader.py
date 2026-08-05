"""DOCX document loader using python-docx."""

from __future__ import annotations

from pathlib import Path

import docx


def load_docx(path: Path) -> list[str]:
    """Extract text from a DOCX file.

    Returns a list with a single string (the full document text).
    Paragraphs are joined preserving their separation.
    """
    document = docx.Document(str(path))
    paragraphs = [para.text for para in document.paragraphs if para.text.strip()]
    full_text = "\n".join(paragraphs)
    return [full_text] if full_text.strip() else []
