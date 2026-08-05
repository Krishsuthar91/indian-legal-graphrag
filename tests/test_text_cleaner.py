"""Tests for text cleaning."""

from src.ingestion.cleaning.text_cleaner import clean_text, clean_pages


class TestTextCleaner:
    def test_clean_removes_page_numbers(self):
        text = "This is content.\nPage 1 of 10\nMore content."
        cleaned = clean_text(text)
        assert "Page 1 of 10" not in cleaned
        assert "This is content" in cleaned
        assert "More content" in cleaned

    def test_clean_removes_watermarks(self):
        text = "Legal text here.\nDownloaded from Indian Kanoon\nMore text."
        cleaned = clean_text(text)
        assert "Downloaded from Indian Kanoon" not in cleaned
        assert "Legal text" in cleaned

    def test_clean_removes_dash_page_numbers(self):
        text = "Header text\n- 3 -\nFooter text"
        cleaned = clean_text(text)
        assert "- 3 -" not in cleaned

    def test_clean_collapses_whitespace(self):
        text = "This  has    extra   spaces"
        cleaned = clean_text(text)
        assert "  " not in cleaned

    def test_clean_preserves_legal_numbering(self):
        text = "Under Section 123 of the Act\nand Rule 45-A of the Rules"
        cleaned = clean_text(text)
        assert "Section 123" in cleaned or "123" in cleaned

    def test_clean_empty_text(self):
        assert clean_text("") == ""
        assert clean_text("   ") == ""

    def test_clean_pages(self):
        pages = ["Page 1 content.", "Page 2 content."]
        cleaned = clean_pages(pages)
        assert len(cleaned) == 2
        assert all(isinstance(c, str) for c in cleaned)

    def test_clean_removes_copyright(self):
        text = "Order of the Court\n© All rights reserved\nSigned this day."
        cleaned = clean_text(text)
        assert "© All rights reserved" not in cleaned
        assert "Signed this day" in cleaned
