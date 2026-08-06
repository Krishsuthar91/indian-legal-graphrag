"""Legal document ingestion pipeline orchestrator.

Coordinates loading, OCR, language detection, metadata extraction,
text cleaning, and JSON output for a single document.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.config.logging_config import get_logger
from src.ingestion.cleaning.text_cleaner import clean_pages
from src.ingestion.detection.language_detector import detect_document_language
from src.ingestion.detection.scanner_detector import is_scanned_pdf
from src.ingestion.loaders.docx_loader import load_docx
from src.ingestion.loaders.pdf_loader import load_pdf, render_page_to_image
from src.ingestion.loaders.txt_loader import load_txt
from src.ingestion.metadata.extractor import build_metadata
from src.ingestion.ocr.engine import ocr_image
from src.models.schemas import DocumentMetadata, IngestedDocument, PageData

log = get_logger("ingestion")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"


def _generate_document_id(path: Path, text_sample: str) -> str:
    """Generate a deterministic document ID from file path and content."""
    raw = f"{path.resolve()}:{text_sample[:500]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _derive_title(path: Path, pages: list[str]) -> str:
    """Extract a title from the document content or fall back to filename."""
    for page in pages:
        lines = [raw.strip() for raw in page.split("\n") if raw.strip()]
        for line in lines[:5]:
            if len(line) > 5 and len(line) < 200:
                return line
    return path.stem.replace("_", " ").replace("-", " ").title()


def ingest_document(file_path: str | Path) -> IngestedDocument:
    """Run the full ingestion pipeline on a single document.

    Steps:
        1. Load document (PDF / DOCX / TXT)
        2. Detect if scanned
        3. Apply OCR if needed
        4. Detect language
        5. Clean text
        6. Extract metadata
        7. Build output schema
        8. Save to data/processed/<document>.json
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {SUPPORTED_EXTENSIONS}")

    log.info("ingestion.start", file=str(path), ext=ext)

    # --- 1. Load ---
    ocr_applied = False
    pdf_info: dict = {}

    if ext == ".pdf":
        pages, pdf_info = load_pdf(path)
        is_scanned = is_scanned_pdf(path)
    elif ext == ".docx":
        pages = load_docx(path)
        is_scanned = False
    elif ext == ".txt":
        pages = load_txt(path)
        is_scanned = False
    else:
        raise ValueError(f"Unsupported extension: {ext}")

    # --- 2 & 3. OCR for scanned PDFs ---
    if ext == ".pdf" and is_scanned:
        log.info("ocr.applying", file=str(path), pages=len(pages))
        ocr_pages: list[str] = []
        for page_num in range(1, len(pages) + 1):
            if pages[page_num - 1].strip() and len(pages[page_num - 1].strip()) > 50:
                ocr_pages.append(pages[page_num - 1])
                continue
            img = render_page_to_image(path, page_num)
            if img is not None:
                text = ocr_image(img)
                ocr_pages.append(text)
            else:
                ocr_pages.append(pages[page_num - 1])
        pages = ocr_pages
        ocr_applied = True

    # --- 4. Language detection ---
    language = detect_document_language(pages)
    log.info("language.detected", lang=language, file=str(path))

    # --- 5. Clean text ---
    pages = clean_pages(pages)

    # --- 6. Metadata ---
    metadata = build_metadata(
        path=path,
        num_pages=len(pages),
        language=language,
        is_scanned=is_scanned,
        ocr_applied=ocr_applied,
        pdf_info=pdf_info if pdf_info else None,
    )

    # --- 7. Build schema ---
    doc_id = _generate_document_id(path, pages[0] if pages else "")
    title = _derive_title(path, pages)

    page_data = [
        PageData(page_number=i + 1, text=text, is_scanned=is_scanned)
        for i, text in enumerate(pages)
    ]

    doc = IngestedDocument(
        document_id=doc_id,
        title=title,
        language=language,
        pages=page_data,
        metadata=DocumentMetadata(**metadata),
    )

    # --- 8. Save ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{doc_id}.json"
    out_path.write_text(
        json.dumps(doc.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("ingestion.complete", file=str(path), output=str(out_path), doc_id=doc_id)

    return doc
