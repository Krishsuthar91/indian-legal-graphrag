"""Tests for language detection."""

from pathlib import Path

from src.ingestion.detection.language_detector import detect_document_language, detect_language


class TestLanguageDetector:
    def test_detect_english(self):
        text = "The Supreme Court held that the petition is maintainable."
        assert detect_language(text) == "en"

    def test_detect_hindi(self):
        text = "भारत का संविधान सभी नागरिकों को समानता का अधिकार देता है।"
        lang = detect_language(text)
        assert lang == "hi"

    def test_detect_kannada(self):
        text = "ಕರ್ನಾಟಕ ಹೈಕೋರ್ಟ್ ಈ ಅರ್ಜಿಯನ್ನು ವಿಚಾರಣೆಗೆ ಸ್ವೀಕರಿಸಿದೆ।"
        lang = detect_language(text)
        assert lang == "kn"

    def test_detect_tamil(self):
        text = "இந்திய அரசியலமைப்பு சட்டம் அனைத்து குடிமக்களுக்கும் சம உரிமை வழங்குகிறது."
        lang = detect_language(text)
        assert lang == "ta"

    def test_detect_telugu(self):
        text = "భారత రాజ్యాంగం పౌరులందరికీ సమానత్వం కల్పిస్తుంది."
        lang = detect_language(text)
        assert lang == "te"

    def test_detect_bengali(self):
        text = "ভারতের সংবিধান সকল নাগরিককে সমতা প্রদান করে।"
        lang = detect_language(text)
        assert lang == "bn"

    def test_detect_malayalam(self):
        text = "ഇന്ത്യൻ ഭരണഘടന എല്ലാ പൌരന്മാർക്കും തുല്യത നൽകുന്നു."
        lang = detect_language(text)
        assert lang == "ml"

    def test_empty_text_defaults_english(self):
        assert detect_language("") == "en"

    def test_document_language_detection(self, sample_pdf: Path):
        from src.ingestion.loaders.pdf_loader import load_pdf

        pages, _ = load_pdf(sample_pdf)
        lang = detect_document_language(pages)
        assert lang == "en"
