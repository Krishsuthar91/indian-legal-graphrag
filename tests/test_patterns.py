"""Tests for legal numbering pattern detection."""

from src.hierarchy.patterns import (
    LVL_CHAPTER,
    LVL_CLAUSE,
    LVL_EXPLANATION,
    LVL_PART,
    LVL_PROVISO,
    LVL_SECTION,
    LVL_SUB_CLAUSE,
    LVL_SUB_SECTION,
    match_line,
)


class TestChapterPatterns:
    def test_chapter_roman_upper(self):
        m = match_line("CHAPTER I")
        assert m is not None
        assert m.node_type == "chapter"
        assert m.level == LVL_CHAPTER

    def test_chapter_roman_xiv(self):
        m = match_line("CHAPTER XIV")
        assert m is not None
        assert m.node_type == "chapter"

    def test_chapter_arabic(self):
        m = match_line("Chapter 12")
        assert m is not None
        assert m.node_type == "chapter"

    def test_chapter_with_title(self):
        m = match_line("Chapter I — Preliminary")
        assert m is not None
        assert m.node_type == "chapter"


class TestPartPatterns:
    def test_part_roman(self):
        m = match_line("PART IV")
        assert m is not None
        assert m.node_type == "part"
        assert m.level == LVL_PART

    def test_part_letter(self):
        m = match_line("PART A")
        assert m is not None
        assert m.node_type == "part"

    def test_part_arabic(self):
        m = match_line("Part 3")
        assert m is not None
        assert m.node_type == "part"


class TestSectionPatterns:
    def test_section_keyword(self):
        m = match_line("Section 12 of the Act")
        assert m is not None
        assert m.node_type == "section"
        assert m.level == LVL_SECTION
        assert "12" in m.numbering

    def test_section_sec_dot(self):
        m = match_line("Sec. 13 provides that")
        assert m is not None
        assert m.node_type == "section"

    def test_section_s_dot(self):
        m = match_line("S. 14 shall apply")
        assert m is not None
        assert m.node_type == "section"

    def test_section_bare_number_dot(self):
        m = match_line("14. This section applies to")
        assert m is not None
        assert m.node_type == "section"
        assert m.numbering == "14"

    def test_section_with_suffix(self):
        m = match_line("Section 14A of the Act")
        assert m is not None
        assert m.node_type == "section"
        assert "14A" in m.numbering


class TestSubSectionPatterns:
    def test_sub_section_numbered(self):
        m = match_line("(1) Where any person")
        assert m is not None
        assert m.node_type == "sub_section"
        assert m.level == LVL_SUB_SECTION
        assert m.numbering == "1"

    def test_sub_section_two_digit(self):
        m = match_line("(12) Notwithstanding")
        assert m is not None
        assert m.node_type == "sub_section"


class TestClausePatterns:
    def test_clause_lowercase(self):
        m = match_line("(a) the person concerned")
        assert m is not None
        assert m.node_type == "clause"
        assert m.level == LVL_CLAUSE
        assert m.numbering == "a"

    def test_clause_b(self):
        m = match_line("(b) in any other case")
        assert m is not None
        assert m.node_type == "clause"


class TestSubClausePatterns:
    def test_sub_clause_roman(self):
        m = match_line("(i) where the contract")
        assert m is not None
        assert m.node_type == "sub_clause"
        assert m.level == LVL_SUB_CLAUSE
        assert m.numbering == "i"

    def test_sub_clause_roman_iii(self):
        m = match_line("(iii) the court may")
        assert m is not None
        assert m.node_type == "sub_clause"


class TestExplanationPatterns:
    def test_explanation_simple(self):
        m = match_line("Explanation.—For the purposes of this section")
        assert m is not None
        assert m.node_type == "explanation"
        assert m.level == LVL_EXPLANATION

    def test_explanation_numbered(self):
        m = match_line("Explanation 1.—Nothing in this section")
        assert m is not None
        assert m.node_type == "explanation"

    def test_explanation_colon(self):
        m = match_line("Explanation: A person includes")
        assert m is not None
        assert m.node_type == "explanation"


class TestProvisoPatterns:
    def test_proviso_simple(self):
        m = match_line("Proviso.—Nothing in this section shall apply")
        assert m is not None
        assert m.node_type == "proviso"
        assert m.level == LVL_PROVISO

    def test_proviso_numbered(self):
        m = match_line("Proviso 2.—Provided further that")
        assert m is not None
        assert m.node_type == "proviso"


class TestNonMatches:
    def test_empty_string(self):
        assert match_line("") is None

    def test_whitespace_only(self):
        assert match_line("   ") is None

    def test_plain_text(self):
        m = match_line("The court held that the petition is maintainable.")
        assert m is None

    def test_random_number(self):
        m = match_line("42 is the answer to everything")
        assert m is None
