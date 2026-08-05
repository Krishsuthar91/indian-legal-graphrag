"""Extract metadata from ingested documents."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def extract_file_metadata(path: Path) -> dict:
    """Extract file-system level metadata."""
    stat = path.stat()
    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_size_bytes": stat.st_size,
        "file_type": path.suffix.lower().lstrip("."),
        "creation_date": datetime.fromtimestamp(
            stat.st_ctime, tz=timezone.utc
        ).isoformat(),
    }


def extract_pdf_properties(pdf_pages: list[str] | None = None, pdf_info: dict | None = None) -> dict:
    """Merge PDF-specific properties into the metadata dict."""
    props: dict = {}
    if pdf_info:
        props.update(pdf_info)
    if pdf_pages is not None:
        props["num_pages"] = len(pdf_pages)
    return props


def build_metadata(
    path: Path,
    num_pages: int,
    language: str,
    is_scanned: bool,
    ocr_applied: bool,
    pdf_info: dict | None = None,
) -> dict:
    """Build the full metadata dict for an ingested document."""
    meta = extract_file_metadata(path)
    meta.update({
        "num_pages": num_pages,
        "language": language,
        "is_scanned": is_scanned,
        "ocr_applied": ocr_applied,
    })
    if pdf_info:
        meta["pdf_properties"] = extract_pdf_properties(pdf_info=pdf_info)
    return meta
