"""Unit tests for section-reference normalization and matching."""

import pytest

from src.evaluation.sections import (
    matches,
    node_section_keys,
    normalize_section,
    normalize_sections,
    predicted_sections,
    section_coverage,
    section_keys_from_text,
    section_match,
)


class TestNormalizeSection:
    def test_prefixed_reference(self):
        assert normalize_section("S.2(a)") == "2(a)"
        assert normalize_section("S.65") == "65"
        assert normalize_section("Section 124") == "124"
        assert normalize_section("sec. 5") == "5"

    def test_bare_reference(self):
        assert normalize_section("S.27 Exception 1") == "27"
        assert normalize_section("31") == "31"

    def test_empty(self):
        assert normalize_section("") == ""
        assert normalize_section("no section here") == ""

    def test_normalize_sections_multiple(self):
        assert normalize_sections("S.2(g), S.2(i)") == ["2(g)", "2(i)"]
        assert normalize_sections("S.20, S.22") == ["20", "22"]
        assert normalize_sections("") == []


class TestSectionKeysFromText:
    def test_from_numbering_and_title(self):
        assert section_keys_from_text("124. \"Contract of indemnity\" defined") == {"124"}
        assert section_keys_from_text("53") == {"53"}
        assert section_keys_from_text("294A") == {"294a"}

    def test_year_not_extracted(self):
        assert section_keys_from_text("The Indian Contract Act, 1872") == set()

    def test_no_keys(self):
        assert section_keys_from_text("Chapter II Of contracts") == set()
        assert section_keys_from_text("") == set()

    def test_node_section_keys(self):
        node = {"node_id": "n_0022", "numbering": "65", "title": "Obligation of person"}
        assert node_section_keys(node) == {"65"}
        mixed = {
            "node_id": "n_0015",
            "numbering": "Of contingent contracts 31. \"Contingent contract\" defined",
            "title": "",
        }
        assert node_section_keys(mixed) == {"31"}


class TestMatching:
    def test_exact(self):
        assert matches("65", "65")
        assert matches("2(a)", "2(a)")

    def test_parent_prefix(self):
        assert matches("2(a)", "2")
        assert matches("S.2(g)", "2g") is False  # node key must be a numeric parent

    def test_mismatch(self):
        assert not matches("65", "66")
        assert not matches("", "65")
        assert not matches("65", "")

    def test_section_match_any(self):
        assert section_match("65", {"12", "65"})
        assert not section_match("65", {"12", "66"})

    def test_section_coverage(self):
        assert section_coverage(["65", "2(a)"], {"65", "2"}) == pytest.approx(1.0)
        assert section_coverage(["124", "126"], {"124"}) == pytest.approx(0.5)
        assert section_coverage([], {"124"}) == pytest.approx(0.0)


class TestPredictedSections:
    def test_from_evidence_dataclasses(self):
        from types import SimpleNamespace

        ev1 = SimpleNamespace(numbering="65", title="Obligation of person")
        ev2 = SimpleNamespace(numbering="", title="Chapter X 172. Agent not personally liable")
        assert predicted_sections([ev1, ev2]) == {"65", "172"}

    def test_from_dicts(self):
        expected = {"22", "23"}
        actual = predicted_sections([{"numbering": "22"}, {"numbering": "", "title": "23"}])
        assert actual == expected
