"""Tests for document loaders (PDF, DOCX, TXT)."""

from pathlib import Path

from src.ingestion.loaders.docx_loader import load_docx
from src.ingestion.loaders.pdf_loader import load_pdf, pdf_has_text
from src.ingestion.loaders.txt_loader import load_txt


class TestTxtLoader:
    def test_load_txt(self, sample_txt: Path):
        pages = load_txt(sample_txt)
        assert len(pages) == 1
        assert "SUPREME COURT" in pages[0]
        assert "Section 123" in pages[0]

    def test_load_empty_txt(self, tmp_path: Path):
        p = tmp_path / "empty.txt"
        p.write_text("", encoding="utf-8")
        pages = load_txt(p)
        assert pages == []

    def test_load_txt_latin1(self, tmp_path: Path):
        p = tmp_path / "latin.txt"
        p.write_bytes(b"caf\xe9 legal document")
        pages = load_txt(p)
        assert len(pages) == 1
        assert "caf" in pages[0]


class TestDocxLoader:
    def test_load_docx(self, sample_docx: Path):
        pages = load_docx(sample_docx)
        assert len(pages) == 1
        assert "Writ Petition" in pages[0]

    def test_load_empty_docx(self, tmp_path: Path):
        from docx import Document

        doc = Document()
        p = tmp_path / "empty.docx"
        doc.save(str(p))
        pages = load_docx(p)
        assert pages == []


class TestPdfLoader:
    def test_load_pdf(self, sample_pdf: Path):
        pages, props = load_pdf(sample_pdf)
        assert len(pages) >= 1
        assert "HIGH COURT" in pages[0]
        assert "page_count" in props

    def test_pdf_has_text(self, sample_pdf: Path):
        assert pdf_has_text(sample_pdf) is True

    def test_pdf_has_no_text(self, sample_pdf_empty: Path):
        assert pdf_has_text(sample_pdf_empty) is False

    def test_load_empty_pdf(self, sample_pdf_empty: Path):
        pages, props = load_pdf(sample_pdf_empty)
        assert isinstance(pages, list)
