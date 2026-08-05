"""Plain text file loader."""

from __future__ import annotations

from pathlib import Path


def load_txt(path: Path) -> list[str]:
    """Read a plain text file and return it as a single-element list.

    Tries UTF-8 first, then falls back to latin-1.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    return [text] if text.strip() else []
