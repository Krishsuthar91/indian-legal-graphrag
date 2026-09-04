"""Grounding guard (Task 15) — answer generation must be skipped unless the
retrieval and verification pipeline meets every grounding threshold.
"""

from src.llm.llm import MockLLMClient
from src.llm.provenance import (
    AnswerResult,
    Confidence,
    Evidence,
    EvidenceRelevance,
    ExplanationResult,
    ProvenanceStore,
    RetrievalSummary,
    Validity,
    VerificationTrace,
)
from src.llm.service import (
    GROUNDED_GUARD_ANSWER,
    GUARD_MIN_CONFIDENCE,
    GUARD_MIN_RELEVANCE,
    GUARD_MIN_SUFFICIENCY,
    QueryService,
)

# ---------------------------------------------------------------- helpers ---

def _evidence() -> Evidence:
    return Evidence(
        node_id="s4",
        title="Performance of contracts",
        text="Performance of contracts. (a) where the contract provides "
        "(b) where no provision is made.",
        label="Section",
        numbering="4",
        collection="test",
        language="en",
        level=5,
        dense_score=0.5,
        graph_score=0.5,
        hierarchy_score=0.5,
        final_score=0.5,
    )


def _explanation(
    *,
    evidence: list[Evidence] | None = None,
    relevance: float = 0.8,
    sufficiency: float = 0.8,
    status: str = "supported",
    confidence: float = 0.8,
) -> ExplanationResult:
    ev = list(evidence) if evidence is not None else [_evidence()]
    validity = Validity(
        is_valid=status == "supported",
        supported=status == "supported",
        has_conflicts=False,
        cites_counter_authority=False,
        insufficient_evidence=status == "insufficient",
        reasons=["test"],
        status=status,
        reason="test",
        support_score=sufficiency,
        relevance_score=relevance,
        sufficiency_score=sufficiency,
        contradiction_found=False,
    )
    return ExplanationResult(
        query="performance of contracts",
        query_language="en",
        retrieval=RetrievalSummary(),
        evidence=ev,
        confidence=Confidence(score=confidence, label="medium"),
        validity=validity,
        evidence_relevance=EvidenceRelevance(score=relevance, label="relevant"),
        verification_trace=VerificationTrace(
            verification_status=status,
            evidence_relevance_score=relevance,
            evidence_sufficiency_score=sufficiency,
            confidence_score=confidence,
        ),
    )


def _build_service(explanation: ExplanationResult, llm, **kwargs) -> QueryService:
    class StubEngine:
        threshold = None

        def __init__(self):
            self.adaptive = False

        def explain(self, *args, **kwargs):
            return explanation

    return QueryService(StubEngine(), llm, ProvenanceStore(), **kwargs)


class _CountingClient(MockLLMClient):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def complete(self, messages, temperature=0.2, max_tokens=800, deadline=None):
        self.calls += 1
        return super().complete(messages, temperature, max_tokens)


class TestGroundingGuardShouldGenerate:
    def test_supported_evidence_returns_true(self):
        assert QueryService._should_generate_answer(_explanation()) is True

    def test_low_relevance_returns_false(self):
        exp = _explanation(relevance=GUARD_MIN_RELEVANCE - 0.1)
        assert QueryService._should_generate_answer(exp) is False

    def test_low_sufficiency_returns_false(self):
        exp = _explanation(sufficiency=GUARD_MIN_SUFFICIENCY - 0.1)
        assert QueryService._should_generate_answer(exp) is False

    def test_verification_not_supported_returns_false(self):
        exp = _explanation(status="insufficient")
        assert QueryService._should_generate_answer(exp) is False

    def test_no_evidence_returns_false(self):
        exp = _explanation(evidence=[])
        assert QueryService._should_generate_answer(exp) is False

    def test_low_confidence_returns_false(self):
        exp = _explanation(confidence=GUARD_MIN_CONFIDENCE - 0.1)
        assert QueryService._should_generate_answer(exp) is False


class TestGroundingGuardAnswerGate:
    def test_supported_evidence_calls_llm(self):
        llm = _CountingClient()
        service = _build_service(_explanation(), llm)
        result = service.answer("performance of contracts")
        assert llm.calls == 1
        assert result.answer != GROUNDED_GUARD_ANSWER
        assert result.model == "mock-llm"

    def test_low_relevance_skips_llm(self):
        llm = _CountingClient()
        exp = _explanation(relevance=GUARD_MIN_RELEVANCE - 0.1)
        service = _build_service(exp, llm)
        result = service.answer("performance of contracts")
        assert llm.calls == 0
        assert result.answer == GROUNDED_GUARD_ANSWER
        assert result.model == "grounding-guard"

    def test_low_sufficiency_skips_llm(self):
        llm = _CountingClient()
        exp = _explanation(sufficiency=GUARD_MIN_SUFFICIENCY - 0.1)
        service = _build_service(exp, llm)
        result = service.answer("performance of contracts")
        assert llm.calls == 0
        assert result.answer == GROUNDED_GUARD_ANSWER

    def test_verification_insufficient_skips_llm(self):
        llm = _CountingClient()
        exp = _explanation(status="insufficient")
        service = _build_service(exp, llm)
        result = service.answer("performance of contracts")
        assert llm.calls == 0
        assert result.answer == GROUNDED_GUARD_ANSWER

    def test_no_evidence_skips_llm(self):
        llm = _CountingClient()
        exp = _explanation(evidence=[])
        service = _build_service(exp, llm)
        result = service.answer("performance of contracts")
        assert llm.calls == 0
        assert result.answer == GROUNDED_GUARD_ANSWER

    def test_guard_disabled_calls_llm_regardless(self):
        llm = _CountingClient()
        exp = _explanation(relevance=0.0, sufficiency=0.0,
                           status="insufficient", confidence=0.0, evidence=[])
        # Disable every answer-generation guard so the LLM is invoked.
        service = _build_service(
            exp, llm, grounding_guard_enabled=False, require_sufficient_evidence=False
        )
        result = service.answer("performance of contracts")
        assert llm.calls == 1
        assert result.answer != GROUNDED_GUARD_ANSWER
        assert result.model == "mock-llm"

    def test_blocked_response_keeps_explanation_and_provenance(self):
        llm = _CountingClient()
        exp = _explanation(relevance=0.0)
        store = ProvenanceStore()
        service = _build_service(exp, llm)
        service.provenance = store
        result = service.answer("performance of contracts")
        assert isinstance(result, AnswerResult)
        assert result.provenance_id
        assert store.get(result.provenance_id) is not None
        # Explanation components must remain intact.
        assert result.explanation is exp
        assert result.explanation.evidence
        assert result.explanation.verification_trace is not None
        assert result.explanation.confidence is exp.confidence
        assert result.explanation.evidence_relevance is exp.evidence_relevance
        assert result.explanation.validity.sufficiency_score == exp.validity.sufficiency_score
        assert result.explanation.retrieval is exp.retrieval

    def test_guard_log_entry_emitted(self, monkeypatch):
        """The guard logs "Grounding guard triggered" with grounding diagnostics."""
        import src.llm.service as svc_mod

        calls = []

        class _Spy:
            def info(self, event, **kwargs):
                calls.append((event, kwargs))
            def debug(self, *a, **k):
                pass

        monkeypatch.setattr(svc_mod, "log", _Spy())
        llm = _CountingClient()
        exp = _explanation(relevance=0.0)
        service = _build_service(exp, llm)
        service.answer("performance of contracts")
        assert llm.calls == 0
        assert calls and calls[0][0] == "Grounding guard triggered"
        payload = calls[0][1]
        assert payload["reason"]
        assert payload["confidence"] == exp.confidence.score
        assert payload["relevance"] == exp.evidence_relevance.score
        assert payload["sufficiency"] == exp.validity.sufficiency_score
        assert payload["verification_status"] == exp.validity.status
        assert payload["node_count"] == len(exp.evidence)
