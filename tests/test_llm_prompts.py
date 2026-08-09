"""Tests for the prompt builder (Module 7)."""

from src.llm.prompts import (
    SYSTEM_PROMPT,
    build_messages,
    build_system_prompt,
    build_user_prompt,
    format_evidence,
    format_reasoning_chain,
)
from src.llm.provenance import Evidence, ExplanationResult, ReasoningStep


def _evidence() -> Evidence:
    return Evidence(
        node_id="s4",
        title="Performance of contracts",
        text="Performance of contracts. (a) where the contract provides...",
        label="Section",
        numbering="4",
        collection="sections",
        language="en",
        level=5,
        dense_score=0.8,
        graph_score=0.7,
        hierarchy_score=1.0,
        final_score=0.8,
        sources=["dense", "graph", "hierarchy"],
        path=["doc1", "ch2", "s4"],
        snippet="Performance of contracts...",
    )


def _explanation() -> ExplanationResult:
    return ExplanationResult(
        query="performance of contracts",
        query_language="en",
        evidence=[_evidence()],
        reasoning_chain=[
            ReasoningStep(
                step=1,
                kind="query_parse",
                description="Parsed query",
                node_ids=[],
                detail={"keywords": ["performance", "contracts"]},
            )
        ],
        hierarchy_paths=[],
    )


class TestEvidenceFormatting:
    def test_source_numbers_included(self):
        text = format_evidence([_evidence()])
        assert "[SOURCE 1]" in text
        assert "s4" in text
        assert "doc1 <- ch2 <- s4" in text

    def test_empty_evidence(self):
        assert "no evidence" in format_evidence([])


class TestSystemPrompt:
    def test_base_rules_present(self):
        prompt = build_system_prompt()
        assert "retrieved evidence" in prompt.lower()
        assert "[1]" in prompt

    def test_language_instruction(self):
        prompt = build_system_prompt(language="hi")
        assert "respond in hi" in prompt.lower()

    def test_extra_rules_appended(self):
        prompt = build_system_prompt(extra_rules=["Never mention this."])
        assert "Never mention this." in prompt

    def test_never_invents_law(self):
        prompt = build_system_prompt()
        assert "Never invent laws" in prompt

    def test_distinguishes_absence_from_nonexistence(self):
        prompt = build_system_prompt()
        assert "NOT IN INDEXED EVIDENCE" in prompt
        assert "TRULY ABSENT" in prompt
        assert "Do NOT claim it does not exist" in prompt

    def test_explains_why_insufficient(self):
        prompt = build_system_prompt()
        assert "explain WHY the answer cannot be produced" in prompt

    def test_structured_response_sections(self):
        prompt = build_system_prompt()
        for section in (
            "Direct Answer",
            "Key Points",
            "Evidence Summary",
            "Confidence Explanation",
            "Limitations",
        ):
            assert section in prompt


class TestUserPrompt:
    def test_contains_query_and_instructions(self):
        exp = _explanation()
        prompt = build_user_prompt("performance of contracts", exp)
        assert "QUESTION: performance of contracts" in prompt
        assert "RETRIEVED EVIDENCE" in prompt
        assert "GRAPH REASONING CHAIN" in prompt
        assert "INSTRUCTIONS" in prompt

    def test_contains_reasoning_chain(self):
        exp = _explanation()
        chain = format_reasoning_chain(exp.reasoning_chain)
        assert "query_parse" in chain
        assert "1." in chain

    def test_empty_chain(self):
        assert "no reasoning steps" in format_reasoning_chain([])

    def test_instructions_reinforce_no_fabrication(self):
        prompt = build_user_prompt("performance of contracts", _explanation())
        assert "Never invent laws, sections, or citations" in prompt

    def test_instructions_distinguish_absence_from_nonexistence(self):
        prompt = build_user_prompt("performance of contracts", _explanation())
        assert "do not claim it does not exist" in prompt
        assert "not in the indexed evidence" in prompt

    def test_instructions_structured_response(self):
        prompt = build_user_prompt("performance of contracts", _explanation())
        assert "Direct Answer" in prompt
        assert "Key Points" in prompt
        assert "Evidence Summary" in prompt
        assert "Confidence Explanation" in prompt
        assert "Limitations" in prompt


class TestMessages:
    def test_structure(self):
        messages = build_messages("performance of contracts", _explanation())
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert SYSTEM_PROMPT in messages[0]["content"]
