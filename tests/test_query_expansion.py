"""Unit tests for Phase 4 deterministic legal query expansion.

Covers the corpus-aware semantics: concept terms are always expanded, but a
verified section reference is only injected when the section exists in the
currently indexed corpus (``available_sections``); otherwise it is recorded as
omitted.
"""

import json
from pathlib import Path

from src.retrieval.query import parse_query
from src.retrieval.query_expansion import (
    CONCEPT_DISPLAY,
    SURFACE_PHRASES,
    VERIFIED_SECTION_MAPPING,
    available_section_keys,
    expand_query,
    section_keys_from_text,
)

CORPUS = Path(__file__).resolve().parents[1] / "data" / "hierarchy" / "0d1934142f67c5f5.json"

FULL_CORPUS = {"2", "14", "15", "19", "25", "17", "18", "11", "12", "16"}


class TestSectionKeyExtraction:
    def test_section_keys_from_text(self):
        assert section_keys_from_text("124. \"Contract of indemnity\" defined") == {"124"}
        assert section_keys_from_text("53") == {"53"}
        assert section_keys_from_text("294A") == {"294a"}
        assert section_keys_from_text("Of contingent contracts 31.") == {"31"}
        assert section_keys_from_text("no numbers here") == set()
        assert section_keys_from_text("1872") == set()

    def test_available_section_keys_from_node_dicts(self):
        nodes = [
            {"numbering": "23", "title": "what considerations are lawful"},
            {"numbering": "294A", "title": "Of indemnity 124. Contract"},
            {"title": "no section"},
        ]
        assert available_section_keys(nodes) == {"23", "294a", "124"}


class TestThreatExpansion:
    def test_threat_expands_to_coercion_family(self):
        result = expand_query("A signs under threat. Is the contract valid?")
        assert result.active is True
        assert result.expanded_concepts == ["coercion", "free_consent", "voidable_agreement"]
        assert "coercion" in result.expanded_terms
        assert "free consent" in result.expanded_terms
        assert "voidable agreement" in result.expanded_terms

    def test_threat_without_corpus_knowledge_injects_no_sections(self):
        result = expand_query("A signs under threat. Is the contract valid?")
        assert result.section_refs == []
        assert result.section_refs_considered == [
            "section 14", "section 15", "section 19", "section 2",
        ]
        assert result.section_refs_omitted == [
            "section 14", "section 15", "section 19", "section 2",
        ]
        assert result.section_refs_available == []

    def test_threat_injects_sections_when_available(self):
        result = expand_query(
            "A signs under threat. Is the contract valid?",
            available_sections=FULL_CORPUS,
        )
        assert result.section_refs == [
            "section 14", "section 15", "section 19", "section 2",
        ]
        assert result.section_refs_omitted == []
        assert result.section_refs_available == result.section_refs

    def test_threat_omits_absent_sections(self):
        result = expand_query(
            "A signs under threat. Is the contract valid?",
            available_sections={"2"},
        )
        assert result.section_refs == ["section 2"]
        assert result.section_refs_omitted == [
            "section 14", "section 15", "section 19",
        ]

    def test_forced_to_sign_matches(self):
        result = expand_query("She was forced to sign the deed")
        assert result.expanded_concepts == ["coercion", "free_consent", "voidable_agreement"]

    def test_duress_matches(self):
        result = expand_query("The agreement was made under duress")
        assert result.expanded_concepts == ["coercion", "free_consent", "voidable_agreement"]


class TestFraudExpansion:
    def test_lied_expands_to_fraud_and_misrepresentation(self):
        result = expand_query("He lied about the quality of the goods")
        assert result.expanded_concepts == ["fraud", "misrepresentation"]
        assert result.section_refs == []

    def test_false_statement_injects_sections_when_available(self):
        result = expand_query(
            "There was a false statement in the prospectus",
            available_sections=FULL_CORPUS,
        )
        assert result.section_refs == ["section 17", "section 18"]

    def test_false_statement_omits_absent_sections(self):
        result = expand_query(
            "There was a false statement in the prospectus",
            available_sections={"17"},
        )
        assert result.section_refs == ["section 17"]
        assert result.section_refs_omitted == ["section 18"]


class TestProposalExpansion:
    def test_offer_expands_to_proposal(self):
        result = expand_query("An offer was made to sell the house")
        assert result.expanded_concepts == ["proposal"]
        assert result.section_refs == []

    def test_offer_injects_section_2_when_available(self):
        result = expand_query(
            "An offer was made to sell the house",
            available_sections={"2"},
        )
        assert result.section_refs == ["section 2"]


class TestConsiderationExpansion:
    def test_without_consideration_expands(self):
        result = expand_query("Agreements without consideration are void")
        assert result.expanded_concepts == ["consideration"]
        assert result.section_refs == []

    def test_without_consideration_injects_available_sections(self):
        result = expand_query(
            "Agreements without consideration are void",
            available_sections={"2", "25"},
        )
        assert result.section_refs == ["section 2", "section 25"]

    def test_without_consideration_omits_absent_section_25(self):
        result = expand_query(
            "Agreements without consideration are void",
            available_sections={"2"},
        )
        assert result.section_refs == ["section 2"]
        assert result.section_refs_omitted == ["section 25"]


class TestCapacityExpansion:
    def test_unable_to_understand_expands(self):
        result = expand_query("She was unable to understand the nature of the deed")
        assert result.expanded_concepts == ["capacity"]
        assert "sound mind" in result.expanded_terms
        assert result.section_refs == []

    def test_capacity_injects_sections_when_available(self):
        result = expand_query(
            "She was unable to understand the nature of the deed",
            available_sections=FULL_CORPUS,
        )
        assert result.section_refs == ["section 11", "section 12"]


class TestUndueInfluenceExpansion:
    def test_dominant_party_pressure_expands(self):
        result = expand_query("The dominant party applied pressure to the weaker party")
        assert result.expanded_concepts == ["undue_influence"]
        assert result.section_refs == []

    def test_undue_influence_injects_section_16_when_available(self):
        result = expand_query(
            "The dominant party applied pressure to the weaker party",
            available_sections={"16"},
        )
        assert result.section_refs == ["section 16"]


class TestCorpusAwareness:
    def test_real_corpus_available_sections(self):
        with CORPUS.open(encoding="utf-8") as f:
            data = json.load(f)
        keys = available_section_keys(data["nodes"])
        assert "2" in keys and "65" in keys and "23" in keys
        assert not {"14", "15", "16", "17", "18", "25"} & keys

    def test_real_corpus_never_receives_nonexistent_sections(self):
        with CORPUS.open(encoding="utf-8") as f:
            data = json.load(f)
        keys = available_section_keys(data["nodes"])
        for query in (
            "A signs under threat. Is the contract valid?",
            "Agreements without consideration are void",
            "He lied about the quality of the goods",
        ):
            result = expand_query(query, available_sections=keys)
            assert result.active is True
            for ref in result.section_refs:
                assert ref.rsplit(" ", 1)[-1].lower() in keys, (
                    f"injected ref {ref} not present in corpus"
                )
        assert result.section_refs_omitted  # at least one absent ref was omitted

    def test_real_corpus_threat_keeps_only_available_sections(self):
        with CORPUS.open(encoding="utf-8") as f:
            data = json.load(f)
        result = expand_query(
            "A signs under threat. Is the contract valid?",
            available_sections=available_section_keys(data["nodes"]),
        )
        assert result.section_refs == ["section 2"]
        assert result.section_refs_omitted == [
            "section 14", "section 15", "section 19",
        ]
        assert "omitted 3 section reference(s) not present in the indexed corpus" in result.reason

    def test_real_corpus_consideration_omits_section_25(self):
        with CORPUS.open(encoding="utf-8") as f:
            data = json.load(f)
        result = expand_query(
            "Agreements without consideration are void",
            available_sections=available_section_keys(data["nodes"]),
        )
        assert result.section_refs == ["section 2"]
        assert result.section_refs_omitted == ["section 25"]


class TestInactiveExpansion:
    def test_unrelated_query_is_inactive(self):
        result = expand_query("performance of contracts")
        assert result.active is False
        assert result.expanded_terms == []
        assert result.expanded_concepts == []
        assert result.reason == "no legal concept phrases matched"

    def test_gibberish_is_inactive(self):
        result = expand_query("zzzqxwv unrelated gibberish")
        assert result.active is False
        assert result.expanded_terms == []

    def test_disabled_returns_inactive_result(self):
        result = expand_query("A signs under threat", enabled=False)
        assert result.active is False
        assert result.reason == "expansion disabled"
        assert result.build_search_text("A signs under threat") == "A signs under threat"

    def test_empty_query_is_inactive(self):
        result = expand_query("")
        assert result.active is False

    def test_search_text_unchanged_when_inactive(self):
        query = "performance of contracts"
        result = expand_query(query)
        assert result.build_search_text(query) == query

    def test_search_text_unchanged_when_disabled(self):
        query = "A signs under threat"
        result = expand_query(query, enabled=False)
        assert result.build_search_text(query) == query


class TestSearchText:
    def test_build_search_text_appends_terms_and_available_sections(self):
        query = "A signs under threat"
        result = expand_query(query, available_sections={"2", "15"})
        text = result.build_search_text(query)
        assert "coercion" in text
        assert "section 15" in text
        assert text.startswith(query)

    def test_build_search_text_excludes_omitted_sections(self):
        query = "A signs under threat"
        result = expand_query(query, available_sections={"2"})
        text = result.build_search_text(query)
        assert "coercion" in text
        assert "section 14" not in text
        assert "section 2" in text

    def test_accepts_retrieval_query_object(self):
        parsed = parse_query("A signs under threat")
        result = expand_query(parsed, available_sections={"14", "15", "19", "2"})
        assert result.active is True
        assert result.expanded_concepts == ["coercion", "free_consent", "voidable_agreement"]


class TestDeterminism:
    def test_same_input_produces_same_output(self):
        query = "He lied about the price and forced me to sign"
        first = expand_query(query, available_sections=FULL_CORPUS)
        second = expand_query(query, available_sections=FULL_CORPUS)
        assert first.expanded_terms == second.expanded_terms
        assert first.expanded_concepts == second.expanded_concepts
        assert first.section_refs == second.section_refs
        assert first.section_refs_omitted == second.section_refs_omitted
        assert first.matched_phrases == second.matched_phrases


class TestWordBoundaries:
    def test_threat_does_not_match_threatens(self):
        result = expand_query("the law threatens no one here")
        assert result.active is False

    def test_lie_does_not_match_belief(self):
        result = expand_query("a belief about the contract")
        assert result.active is False

    def test_minor_does_not_match_minority(self):
        result = expand_query("the minority shareholders agreed")
        assert result.active is False


class TestVerifiedSections:
    def test_sections_come_only_from_verified_mapping(self):
        for concept in CONCEPT_DISPLAY:
            assert concept in VERIFIED_SECTION_MAPPING
            assert all(
                isinstance(n, int) and n > 0
                for n in VERIFIED_SECTION_MAPPING[concept]
            )

    def test_every_surface_phrase_maps_to_known_concepts(self):
        for phrase, targets in SURFACE_PHRASES.items():
            assert phrase, "surface phrase must not be empty"
            assert set(targets) <= set(CONCEPT_DISPLAY)
            for target in targets:
                assert target in VERIFIED_SECTION_MAPPING
