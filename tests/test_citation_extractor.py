"""Tests for legal citation extraction."""

from src.knowledge_graph.citation_extractor import extract_citations


class TestSectionCitations:
    def test_simple_section(self):
        cites = extract_citations("Section 12 of the Act")
        assert len(cites) >= 1
        sec = [c for c in cites if c.citation_type == "section"]
        assert len(sec) == 1
        assert sec[0].ref_number == "12"

    def test_section_with_suffix(self):
        cites = extract_citations("Section 14A provides that")
        sec = [c for c in cites if c.citation_type == "section"]
        assert len(sec) == 1
        assert "14A" in sec[0].ref_number

    def test_section_with_range(self):
        cites = extract_citations("Sections 10-12 shall apply")
        sec = [c for c in cites if c.citation_type == "section"]
        assert len(sec) == 1

    def test_section_with_act_name(self):
        cites = extract_citations("Section 123 of the Indian Contract Act")
        sec = [c for c in cites if c.citation_type == "section"]
        assert len(sec) == 1
        assert "Indian Contract Act" in sec[0].act_name

    def test_sec_dot(self):
        cites = extract_citations("Sec. 13 provides that")
        sec = [c for c in cites if c.citation_type == "section"]
        assert len(sec) == 1

    def test_s_dot(self):
        cites = extract_citations("S. 14 shall apply")
        sec = [c for c in cites if c.citation_type == "section"]
        assert len(sec) == 1


class TestRuleCitations:
    def test_simple_rule(self):
        cites = extract_citations("Rule 45-A of the CPC")
        rules = [c for c in cites if c.citation_type == "rule"]
        assert len(rules) == 1
        assert "45" in rules[0].ref_number


class TestArticleCitations:
    def test_simple_article(self):
        cites = extract_citations("Article 14 of the Constitution")
        articles = [c for c in cites if c.citation_type == "article"]
        assert len(articles) == 1
        assert articles[0].ref_number == "14"

    def test_article_with_act(self):
        cites = extract_citations("Article 21 of the Constitution of India")
        articles = [c for c in cites if c.citation_type == "article"]
        assert len(articles) == 1
        assert "Constitution" in articles[0].act_name


class TestOrderCitations:
    def test_order_and_rule(self):
        cites = extract_citations("Order VII Rule 11 of the CPC")
        orders = [c for c in cites if c.citation_type == "order"]
        assert len(orders) == 1
        assert "Order VII Rule 11" in orders[0].ref_number


class TestCaseCitations:
    def test_air_citation(self):
        cites = extract_citations("AIR 1965 SC 123")
        cases = [c for c in cites if c.citation_type == "case"]
        assert len(cases) == 1
        assert cases[0].court == "SC"
        assert cases[0].year == "1965"

    def test_paren_year_citation(self):
        cites = extract_citations("(2001) 2 SCC 123")
        cases = [c for c in cites if c.citation_type == "case"]
        assert len(cases) == 1
        assert cases[0].year == "2001"

    def test_year_court_citation(self):
        cites = extract_citations("2001 SCC (Cri) 456")
        cases = [c for c in cites if c.citation_type == "case"]
        assert len(cases) == 1
        assert cases[0].court == "SCC"


class TestMultipleCitations:
    def test_mixed_citations(self):
        text = (
            "Under Section 12 of the Indian Contract Act and Article 14 of the "
            "Constitution, as held in AIR 1965 SC 123"
        )
        cites = extract_citations(text)
        types = {c.citation_type for c in cites}
        assert "section" in types
        assert "article" in types
        assert "case" in types

    def test_deduplication(self):
        text = "Section 12 applies. Section 12 is important."
        cites = extract_citations(text)
        sec = [c for c in cites if c.citation_type == "section"]
        assert len(sec) == 1

    def test_no_citations(self):
        cites = extract_citations("This is plain text with no legal references.")
        assert len(cites) == 0
