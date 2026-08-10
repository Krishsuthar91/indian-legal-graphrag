"""Tests for query intent detection and adaptive top-k selection."""

from src.retrieval.intent import (
    CASE_LAW,
    COMPARISON,
    CONSTITUTIONAL,
    DEFINITION,
    EXPLANATION,
    INTENTS,
    PROCEDURAL,
    PUNISHMENT,
    SECTION_LOOKUP,
    adaptive_top_k,
    detect_intent,
)
from src.retrieval.query import parse_query


class TestDetectIntent:
    def test_section_reference_is_section_lookup(self):
        assert detect_intent(parse_query("what does section 4 say")) == SECTION_LOOKUP

    def test_article_reference_is_section_lookup(self):
        assert detect_intent(parse_query("article 14 of the constitution")) == SECTION_LOOKUP

    def test_rule_reference_is_section_lookup(self):
        assert detect_intent(parse_query("rule 45 of the act")) == SECTION_LOOKUP

    def test_definition_keywords(self):
        assert detect_intent("what is the definition of consideration") == DEFINITION
        assert detect_intent("meaning of acceptance under contract law") == DEFINITION

    def test_punishment_keywords(self):
        assert detect_intent("punishment for breach of contract") == PUNISHMENT
        assert detect_intent("penalty for non performance of a contract") == PUNISHMENT

    def test_procedural_keywords(self):
        assert detect_intent("how to file a complaint in court") == PROCEDURAL
        assert detect_intent("procedure for limitation of suits") == PROCEDURAL

    def test_constitutional_keywords(self):
        assert detect_intent("fundamental rights under the constitution") == CONSTITUTIONAL

    def test_case_law_keywords(self):
        assert detect_intent("landmark supreme court judgment on contracts") == CASE_LAW
        assert detect_intent("precedent on void agreements") == CASE_LAW

    def test_case_citation(self):
        assert detect_intent("AIR 1965 SC 123 contract law") == CASE_LAW

    def test_comparison_keywords(self):
        assert detect_intent("difference between offer and acceptance") == COMPARISON
        assert detect_intent("compare void and voidable agreements") == COMPARISON

    def test_plain_query_falls_back_to_explanation(self):
        assert detect_intent("performance of contracts") == EXPLANATION

    def test_empty_query_falls_back(self):
        assert detect_intent("") == EXPLANATION

    def test_accepts_query_object_and_string(self):
        q = parse_query("punishment for breach")
        assert detect_intent(q) == PUNISHMENT
        assert detect_intent("punishment for breach") == PUNISHMENT


class TestAdaptiveTopK:
    def test_easy_intents_get_easy_budget(self):
        assert adaptive_top_k(DEFINITION) == 4
        assert adaptive_top_k(SECTION_LOOKUP) == 4
        assert adaptive_top_k(EXPLANATION) == 4

    def test_medium_intents_get_medium_budget(self):
        assert adaptive_top_k(PUNISHMENT) == 7
        assert adaptive_top_k(PROCEDURAL) == 7
        assert adaptive_top_k(COMPARISON) == 7
        assert adaptive_top_k(CONSTITUTIONAL) == 7

    def test_complex_intents_get_complex_budget(self):
        assert adaptive_top_k(CASE_LAW) == 12

    def test_unknown_intent_falls_back_to_complex(self):
        assert adaptive_top_k("mystery") == 12

    def test_custom_budgets_override_defaults(self):
        assert adaptive_top_k(DEFINITION, easy=3, medium=6, complex=11) == 3
        assert adaptive_top_k(PUNISHMENT, easy=3, medium=6, complex=11) == 6
        assert adaptive_top_k(CASE_LAW, easy=3, medium=6, complex=11) == 11

    def test_every_intent_maps_to_a_budget(self):
        for intent in INTENTS:
            assert adaptive_top_k(intent) in (4, 7, 12)
