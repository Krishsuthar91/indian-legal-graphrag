"""Tests for metadata extraction."""

from pathlib import Path

from src.ingestion.metadata.extractor import build_metadata, extract_file_metadata


class TestMetadataExtractor:
    def test_file_metadata(self, sample_txt: Path):
        meta = extract_file_metadata(sample_txt)
        assert meta["file_name"] == "sample.txt"
        assert meta["file_type"] == "txt"
        assert meta["file_size_bytes"] > 0
        assert "creation_date" in meta

    def test_build_metadata(self, sample_txt: Path):
        meta = build_metadata(
            path=sample_txt,
            num_pages=1,
            language="en",
            is_scanned=False,
            ocr_applied=False,
        )
        assert meta["file_name"] == "sample.txt"
        assert meta["num_pages"] == 1
        assert meta["language"] == "en"
        assert meta["is_scanned"] is False
        assert meta["ocr_applied"] is False

    def test_build_metadata_with_pdf_info(self, sample_pdf: Path):
        meta = build_metadata(
            path=sample_pdf,
            num_pages=2,
            language="en",
            is_scanned=False,
            ocr_applied=False,
            pdf_info={"pdf_version": "1.4", "page_count": 2},
        )
        assert "pdf_properties" in meta
        assert meta["pdf_properties"]["pdf_version"] == "1.4"
