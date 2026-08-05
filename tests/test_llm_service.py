"""Tests for the QueryService orchestrator (Module 7)."""

import pytest

from src.llm.llm import MockLLMClient
from src.llm.provenance import ProvenanceStore
from tests.qa_helpers import build_service


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

            def complete(self, messages, temperature=0.2, max_tokens=800):
                RecordingClient.calls += 1
                return super().complete(messages, temperature, max_tokens)

        service = build_service(llm=RecordingClient())
        service.answer("performance of contracts")
        assert RecordingClient.calls == 1


class TestExplainOnly:
    def test_no_llm_call(self):
        class BoomClient(MockLLMClient):
            def complete(self, messages, temperature=0.2, max_tokens=800):
                raise AssertionError("LLM should not be called")

        service = build_service(llm=BoomClient())
        explanation = service.explain("performance of contracts")
        assert explanation.evidence
        assert explanation.query == "performance of contracts"
