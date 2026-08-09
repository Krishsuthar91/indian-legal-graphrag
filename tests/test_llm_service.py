"""Tests for the QueryService orchestrator (Module 7)."""

import re

import pytest

from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from src.llm.llm import MockLLMClient
from src.llm.provenance import ProvenanceStore
from src.llm.service import INSUFFICIENT_EVIDENCE_ANSWER, QueryService
from tests.qa_helpers import build_graph, build_service


class TestAnswer:
    def test_returns_complete_answer(self):
        service = build_service()
        result = service.answer("performance of contracts")
        assert result.provenance_id
        assert result.query == "performance of contracts"
        assert result.answer
        assert result.model == "mock-llm"
        assert result.explanation.evidence
        assert result.explanation.confidence.score > 0
        assert result.duration_ms >= 0

    def test_answer_stores_provenance(self):
        store = ProvenanceStore()
        service = build_service(provenance_store=store)
        result = service.answer("performance of contracts")
        record = service.get_provenance(result.provenance_id)
        assert record is not None
        assert record["answer"] == result.answer
        assert len(store.list_ids()) == 1

    def test_top_k_respected(self):
        service = build_service()
        result = service.answer("performance of contracts", top_k=2)
        assert len(result.explanation.evidence) <= 2

    def test_empty_query_raises(self):
        service = build_service()
        with pytest.raises(ValueError):
            service.answer("   ")

    def test_uses_custom_llm(self):
        class RecordingClient(MockLLMClient):
            calls = 0

            def complete(self, messages, temperature=0.2, max_tokens=800, deadline=None):
                RecordingClient.calls += 1
                return super().complete(messages, temperature, max_tokens)

        service = build_service(llm=RecordingClient())
        service.answer("performance of contracts")
        assert RecordingClient.calls == 1

    def test_retrieved_context_reaches_llm(self):
        """The LLM must receive the retrieved evidence, not just the raw query."""
        captured = {}

        class SpyClient(MockLLMClient):
            def complete(self, messages, temperature=0.2, max_tokens=800, deadline=None):
                captured["messages"] = messages
                return super().complete(messages, temperature, max_tokens)

        service = build_service(llm=SpyClient())
        service.answer("performance of contracts")

        messages = captured["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"]
        user_content = messages[1]["content"]
        assert "QUESTION: performance of contracts" in user_content
        assert "[SOURCE 1]" in user_content
        assert "Performance of contracts" in user_content

    def test_evidence_source_blocks_have_non_empty_text(self):
        """Regression: the prompt passed to the LLM must contain real evidence
        text. A ranked empty-text wrapper (e.g. a Document node) must be
        resolved to its text-bearing sections before the prompt is built."""
        captured = {}

        class SpyClient(MockLLMClient):
            def complete(self, messages, temperature=0.2, max_tokens=800, deadline=None):
                captured["messages"] = messages
                return super().complete(messages, temperature, max_tokens)

        service = build_service(llm=SpyClient())
        service.answer("performance of contracts")
        user_content = captured["messages"][1]["content"]

        source_blocks = re.split(r"\[SOURCE \d+\]", user_content)[1:]
        assert source_blocks, "no source blocks found in prompt"
        for block in source_blocks:
            match = re.search(r"Text:\s*(.*)", block)
            assert match, f"source block missing Text: {block!r}"
            assert match.group(1).strip(), (
                f"empty evidence text passed to LLM: {block!r}"
            )

    def test_deadline_propagates_to_llm_client(self):
        captured = {}

        class SpyClient(MockLLMClient):
            def complete(self, messages, temperature=0.2, max_tokens=800, deadline=None):
                captured["deadline"] = deadline
                return super().complete(messages, temperature, max_tokens)

        service = build_service(llm=SpyClient())
        service.answer("performance of contracts", deadline=1234.5)
        assert captured["deadline"] == 1234.5


class TestExplainOnly:
    def test_no_llm_call(self):
        class BoomClient(MockLLMClient):
            def complete(self, messages, temperature=0.2, max_tokens=800):
                raise AssertionError("LLM should not be called")

        service = build_service(llm=BoomClient())
        explanation = service.explain("performance of contracts")
        assert explanation.evidence
        assert explanation.query == "performance of contracts"


class TestRetrievalValidationGate:
    """Retrieval is validated before the LLM generates an answer: when the
    indexed evidence is insufficient, the LLM is skipped and a grounded guard
    answer is returned instead of risking a fabricated or 'Section does not
    exist' response."""

    def _graph_only_service(self, **kwargs) -> QueryService:
        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        return QueryService(engine, MockLLMClient(), ProvenanceStore(), **kwargs)

    def test_insufficient_evidence_returns_guard_answer_without_llm(self):
        class BoomClient(MockLLMClient):
            def complete(self, messages, temperature=0.2, max_tokens=800, deadline=None):
                raise AssertionError("LLM must not be called with insufficient evidence")

        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        service = QueryService(engine, BoomClient(), ProvenanceStore())
        result = service.answer("zzzqxwv unrelated gibberish")
        assert result.answer == INSUFFICIENT_EVIDENCE_ANSWER
        assert result.model == "grounding-guard"
        assert result.explanation.validity.insufficient_evidence is True

    def test_insufficient_evidence_still_stores_provenance(self):
        store = ProvenanceStore()
        graph = build_graph()
        engine = ExplainabilityEngine(graph, vector_retriever=None)
        service = QueryService(engine, MockLLMClient(), store)
        result = service.answer("zzzqxwv unrelated gibberish")
        record = service.get_provenance(result.provenance_id)
        assert record is not None
        assert record["answer"] == INSUFFICIENT_EVIDENCE_ANSWER

    def test_guard_skipped_when_disabled(self):
        service = self._graph_only_service(require_sufficient_evidence=False)
        result = service.answer("zzzqxwv unrelated gibberish")
        assert result.answer != INSUFFICIENT_EVIDENCE_ANSWER
        assert result.model == "mock-llm"

    def test_sufficient_evidence_still_uses_llm(self):
        service = self._graph_only_service()
        result = service.answer("performance of contracts")
        assert result.answer != INSUFFICIENT_EVIDENCE_ANSWER
        assert result.model == "mock-llm"
