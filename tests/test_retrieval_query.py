"""Tests for retrieval query parsing."""

from src.retrieval.query import RetrievalQuery, parse_query

ICA_DOC_ID = "0d1934142f67c5f5"
IPC_DOC_ID = "cf20a14c52127fd5"


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


class TestActResolution:
    """Act / document_id resolution for ordinary legal phrasing (Issue #3)."""

    # --- Trailing abbreviations -------------------------------------------------
    def test_trailing_ipc_abbreviation(self):
        q = parse_query("What is theft under Section 378 IPC?")
        assert q.act_name == "IPC"
        assert q.document_id == IPC_DOC_ID
        assert "378" in q.section_numbers

    def test_trailing_ica_abbreviation(self):
        q = parse_query("Explain Section 420 ICA.")
        assert q.act_name == "ICA"
        assert q.document_id == ICA_DOC_ID
        assert "420" in q.section_numbers

    # --- Full Act names ----------------------------------------------------------
    def test_trailing_contract_act_full_name(self):
        q = parse_query("Explain Section 5 Contract Act.")
        assert q.act_name == "Contract Act"
        assert q.document_id == ICA_DOC_ID
        assert "5" in q.section_numbers

    def test_trailing_penal_code_full_name(self):
        q = parse_query("What does Section 302 Indian Penal Code say?")
        assert q.act_name == "Indian Penal Code"
        assert q.document_id == IPC_DOC_ID

    def test_of_form_contract_act_full_name(self):
        q = parse_query("What does Section 10 of the Indian Contract Act say?")
        assert "indian contract act" in q.act_name.lower()
        assert q.document_id == ICA_DOC_ID

    def test_of_form_penal_code_full_name(self):
        q = parse_query("Explain Section 302 of the Indian Penal Code.")
        assert q.act_name == "the Indian Penal Code"
        assert q.document_id == IPC_DOC_ID

    def test_short_contract_act_under_form(self):
        q = parse_query("Section 23 under Contract Act, 1872")
        assert q.document_id == ICA_DOC_ID

    # --- Leading abbreviations ----------------------------------------------------
    def test_leading_ipc_abbreviation(self):
        q = parse_query("IPC Section 302.")
        assert q.act_name == "IPC"
        assert q.document_id == IPC_DOC_ID
        assert "302" in q.section_numbers

    def test_leading_ica_abbreviation(self):
        q = parse_query("ICA Section 10.")
        assert q.act_name == "ICA"
        assert q.document_id == ICA_DOC_ID
        assert "10" in q.section_numbers

    # --- "Section X of the Act" ---------------------------------------------------
    def test_section_of_the_act(self):
        q = parse_query("Section 12 of the Act")
        assert q.act_name == "the Act"
        assert q.document_id == ICA_DOC_ID

    def test_rule_of_the_act(self):
        q = parse_query("Rule 45 of the Act")
        assert q.document_id == ICA_DOC_ID

    # --- Lowercase / uppercase variants ------------------------------------------
    def test_lowercase_trailing_abbreviation(self):
        q = parse_query("section 378 ipc")
        assert q.document_id == IPC_DOC_ID

    def test_uppercase_trailing_abbreviation(self):
        q = parse_query("SECTION 420 IPC")
        assert q.document_id == IPC_DOC_ID

    def test_mixed_case_full_name(self):
        q = parse_query("Explain Section 5 CONTRACT ACT")
        assert q.document_id == ICA_DOC_ID

    # --- Negative cases -------------------------------------------------------------
    def test_unknown_act_remains_empty(self):
        q = parse_query("Section 5 of the Motor Vehicles Act")
        assert q.document_id == ""
        assert q.act_name == "the Motor Vehicles Act"

    def test_no_act_mention_leaves_document_id_empty(self):
        q = parse_query("What is consideration in contract law?")
        assert q.document_id == ""
        assert q.act_name == ""

    def test_abbreviation_not_matched_as_word_part(self):
        q = parse_query("Explain section 5 punishable in africa")
        assert q.document_id == ""
        assert q.act_name == ""

    # --- Keyword interactions --------------------------------------------------------
    def test_bare_act_name_keeps_content_keywords(self):
        q = parse_query("Indian Contract Act")
        assert q.document_id == ICA_DOC_ID
        assert "indian" in q.keywords
        assert "contract" in q.keywords

    def test_abbreviation_excluded_when_other_keywords_present(self):
        q = parse_query("IPC Section 302 punishment for murder")
        assert q.document_id == IPC_DOC_ID
        assert "ipc" not in q.keywords
        assert "punishment" in q.keywords
