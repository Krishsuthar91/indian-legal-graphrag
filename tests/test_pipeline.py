"""Tests for the ingestion pipeline end-to-end."""

from pathlib import Path

from src.ingestion.pipeline import ingest_document


class TestIngestionPipeline:
    def test_ingest_txt(self, sample_txt: Path):
        doc = ingest_document(sample_txt)
        assert doc.document_id
        assert doc.title
        assert doc.language == "en"
        assert len(doc.pages) >= 1
        assert doc.metadata.file_type == "txt"
        assert doc.metadata.is_scanned is False

    def test_ingest_pdf(self, sample_pdf: Path):
        doc = ingest_document(sample_pdf)
        assert doc.document_id
        assert doc.language == "en"
        assert len(doc.pages) >= 1
        assert doc.metadata.file_type == "pdf"
        assert "page_count" in doc.metadata.pdf_properties or doc.metadata.num_pages >= 1

    def test_ingest_docx(self, sample_docx: Path):
        doc = ingest_document(sample_docx)
        assert doc.document_id
        assert len(doc.pages) >= 1
        assert doc.metadata.file_type == "docx"

    def test_ingest_creates_json(self, sample_txt: Path, tmp_path: Path):
        doc = ingest_document(sample_txt)
        json_path = Path("data/processed") / f"{doc.document_id}.json"
        assert json_path.exists()

    def test_ingest_nonexistent_file(self):
        try:
            ingest_document("/nonexistent/file.pdf")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_ingest_unsupported_extension(self, tmp_path: Path):
        p = tmp_path / "test.xyz"
        p.write_text("hello")
        try:
            ingest_document(p)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_ingested_doc_matches_schema(self, sample_pdf: Path):
        doc = ingest_document(sample_pdf)
        data = doc.model_dump()
        assert "document_id" in data
        assert "title" in data
        assert "language" in data
        assert "pages" in data
        assert "metadata" in data
        for page in data["pages"]:
            assert "page_number" in page
            assert "text" in page
