"""Tests for retrieval query parsing."""

from src.retrieval.query import RetrievalQuery, parse_query


class TestParseQueryKeywords:
    def test_extracts_content_keywords(self):
        q = parse_query("what does performance of contracts mean")
        assert "performance" in q.keywords
        assert "contracts" in q.keywords

    def test_removes_stopwords(self):
        q = parse_query("what is the section about performance")
        assert "what" not in q.keywords
        assert "the" not in q.keywords
        assert "is" not in q.keywords
        assert "performance" in q.keywords

    def test_lowercases_keywords(self):
        q = parse_query("Performance OF Contracts")
        assert "performance" in q.keywords
        assert "of" not in q.keywords

    def test_deduplicates_keywords(self):
        q = parse_query("performance and performance")
        assert q.keywords.count("performance") == 1

    def test_unicode_keywords(self):
        q = parse_query("अनुबंध प्रदर्शन")
        assert "अनुबंध" in q.keywords


class TestParseQueryReferences:
    def test_extracts_section_ref(self):
        q = parse_query("what does section 5 say about acceptance")
        assert "section 5" in q.section_refs
        assert "5" in q.section_numbers

    def test_extracts_sec_dot_ref(self):
        q = parse_query("see sec. 12 of the act")
        assert "section 12" in q.section_refs
        assert "12" in q.section_numbers

    def test_extracts_article_ref(self):
        q = parse_query("article 14 of the constitution")
        assert "article 14" in q.section_refs

    def test_extracts_multiple_refs(self):
        q = parse_query("section 2 and section 10 of the act")
        assert "section 2" in q.section_refs
        assert "section 10" in q.section_refs

    def test_empty_query(self):
        q = parse_query("")
        assert q.is_empty
        assert q.keywords == []
        assert q.section_refs == []

    def test_plain_text_no_references(self):
        q = parse_query("performance of contracts")
        assert q.section_refs == []


class TestRetrievalQuery:
    def test_is_empty_true_for_no_terms(self):
        q = RetrievalQuery(raw="the")
        assert q.is_empty

    def test_is_empty_false_for_keywords(self):
        q = RetrievalQuery(raw="performance", keywords=["performance"])
        assert not q.is_empty

    def test_is_empty_false_for_section_ref(self):
        q = RetrievalQuery(raw="section 5", section_refs=["section 5"])
        assert not q.is_empty

    def test_language_defaults_to_english(self):
        q = parse_query("performance")
        assert q.language == "en"
