"""Tests for scanner/digital PDF detection."""

from pathlib import Path

from src.ingestion.detection.scanner_detector import is_scanned_pdf


class TestScannerDetector:
    def test_text_pdf_not_scanned(self, sample_pdf: Path):
        assert is_scanned_pdf(sample_pdf) is False

    def test_empty_pdf_is_scanned(self, sample_pdf_empty: Path):
        assert is_scanned_pdf(sample_pdf_empty) is True
