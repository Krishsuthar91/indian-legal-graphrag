"""Task 20 — citation entailment is now executed in the production pipeline.

Task 19 found that ``_compute_citation_entailment`` was never invoked during
``answer()``/``explain()``: confidence was computed with the entailment weight
silently redistributed, so the verification badge always degraded to
"insufficient" and confidence capped at 0.45.

These tests verify that ``QueryService.answer()`` now re-scores confidence and
the verification badge with the *real* entailment result, reusing the existing
``ExplainabilityEngine`` implementation unchanged.
"""

from src.llm.explanation import ExplainabilityEngine
from src.llm.llm import LLMResponse, MockLLMClient
from src.llm.provenance import (
    Confidence,
    Evidence,
    EvidenceRelevance,
    ExplanationResult,
    ProvenanceStore,
    RetrievalSummary,
    Validity,
    VerificationTrace,
)
from src.llm.service import QueryService

# ---------------------------------------------------------------- helpers ---


def _evidence(text: str = "Performance of contracts must be performed in full."):
    return Evidence(
        node_id="s4",
        title="Performance of contracts",
        text=text,
        label="Section",
        numbering="4",
        collection="sections",
        language="en",
        level=5,
        dense_score=0.5,
        graph_score=0.5,
        hierarchy_score=0.0,
        final_score=0.5,
    )


def _explanation(
    *,
    evidence=None,
    relevance: float = 0.4,
    sufficiency: float = 0.6,
    confidence: float = 0.45,
):
    ev = [_evidence()] if evidence is None else evidence
    validity = Validity(
        is_valid=False,
        supported=False,
        has_conflicts=False,
        cites_counter_authority=False,
        insufficient_evidence=True,
        reasons=["pre-entailment"],
        status="insufficient",
    )
    return ExplanationResult(
        query="performance of contracts",
        query_language="en",
        retrieval=RetrievalSummary(),
        evidence=ev,
        confidence=Confidence(score=confidence, label="low"),
        validity=validity,
        evidence_relevance=EvidenceRelevance(score=relevance, label="partial"),
        verification_trace=VerificationTrace(
            verification_status="insufficient",
            evidence_relevance_score=relevance,
            evidence_sufficiency_score=sufficiency,
            confidence_score=confidence,
        ),
    )


class _EntailmentJudge:
    """Deterministic entailment judge returning a fixed JSON per call."""

    def __init__(self, response: str):
        self._response = response
        self.calls = 0

    def chat(self, *, system: str, user: str, **kw):
        self.calls += 1
        return LLMResponse(text=self._response, model="mock-entailment")


class _DelegatingEngine:
    """Stub engine that fixes ``explain()`` but reuses the real verification
    code paths (entailment, confidence, validity, trace) from a lightweight
    ``ExplainabilityEngine`` so every Task 20 behavior is exercised against the
    production helper methods."""

    def __init__(self, explanation: ExplanationResult, entailment: str):
        # graph=None is fine: entailment/confidence/validity methods do not use
        # the graph or vector retriever.
        self._real = ExplainabilityEngine(None, llm_client=_EntailmentJudge(entailment))
        self._exp = explanation
        self.threshold = 0.45
        self.adaptive = False

    def explain(self, *args, **kwargs):
        return self._exp

    @property
    def llm_client(self):
        return self._real.llm_client

    def _compute_citation_entailment(self, answer, evidence, citations=None):
        return self._real._compute_citation_entailment(answer, evidence, citations)

    def _score_confidence(self, *a, **k):
        return self._real._score_confidence(*a, **k)

    def _assess_validity(self, *a, **k):
        return self._real._assess_validity(*a, **k)

    def _build_verification_trace(self, *a, **k):
        return self._real._build_verification_trace(*a, **k)


def _build_service(explanation: ExplanationResult, entailment: str, **kwargs):
    engine = _DelegatingEngine(explanation, entailment)
    # Disable both answer guards by default: this task's focus is the entailment
    # re-score, so we force a real generated answer that entailment then judges.
    kwargs.setdefault("grounding_guard_enabled", False)
    kwargs.setdefault("require_sufficient_evidence", False)
    service = QueryService(engine, MockLLMClient(), ProvenanceStore(), **kwargs)
    return service, engine


_SUPPORTED = '{"entailment": 1.0, "contradicts": false, "reason": "Supported."}'
_UNSUPPORTED = '{"entailment": 0.0, "contradicts": false, "reason": "Not supported."}'
_CONTRADICTION = '{"entailment": 0.0, "contradicts": true, "reason": "Contradicts."}'


# ---------------------------------------------------------------- tests ----


class TestEntailmentExecutedDuringAnswer:
    def test_entailment_runs_and_populates_result(self):
        service, engine = _build_service(_explanation(), _SUPPORTED)
        result = service.answer("performance of contracts")
        entailment = result.explanation.citation_entailment
        # Entailment method was actually invoked and its output is recorded.
        assert engine.llm_client.calls >= 1
        assert entailment.overall_score == 1.0
        assert entailment.claim_results  # per-claim verdicts recorded
        assert not entailment.contradiction_found


class TestConfidenceUsesRealEntailment:
    def test_supported_answer_improves_confidence(self):
        # Pre-entailment confidence is 0.45 (below/at the insufficiency pinch).
        service, _ = _build_service(_explanation(), _SUPPORTED)
        result = service.answer("performance of contracts")
        factors = result.explanation.confidence.factors
        # The real entailment score is used (not the redistributed 0.0).
        assert factors["citation_entailment"] == 1.0
        assert result.explanation.confidence.score > 0.45
        assert result.explanation.validity.status == "supported"

    def test_unsupported_answer_lowers_confidence(self):
        service, _ = _build_service(_explanation(), _UNSUPPORTED)
        result = service.answer("performance of contracts")
        factors = result.explanation.confidence.factors
        assert factors["citation_entailment"] == 0.0
        # Entailment gate (0.35) drives the badge to insufficient + cap.
        assert result.explanation.validity.status == "insufficient"
        assert result.explanation.confidence.score <= 0.45


class TestContradictionOverrides:
    def test_contradiction_still_wins(self):
        service, _ = _build_service(_explanation(), _CONTRADICTION)
        result = service.answer("performance of contracts")
        factors = result.explanation.confidence.factors
        assert factors["citation_entailment"] == 0.0
        assert factors.get("contradiction_found") is True
        # Priority rule: contradiction overrides everything -> conflicts + 0.20 cap.
        assert result.explanation.validity.status == "conflicts"
        assert result.explanation.confidence.score <= 0.20


class TestSkipConditions:
    def test_no_answer_skips_entailment(self):
        explanation = _explanation()
        service, engine = _build_service(explanation, _SUPPORTED)
        returned = service._score_with_citation_entailment(explanation, "   ", "q")
        assert returned is explanation
        assert engine.llm_client.calls == 0  # entailment judge never called
        assert explanation.citation_entailment.claim_results == []

    def test_no_evidence_skips_entailment(self):
        explanation = _explanation(evidence=[])
        service, engine = _build_service(explanation, _SUPPORTED)
        returned = service._score_with_citation_entailment(explanation, "some answer", "q")
        assert returned is explanation
        assert engine.llm_client.calls == 0
        assert explanation.citation_entailment.claim_results == []


class TestAPISerializationUnchanged:
    def test_api_serialization_still_valid(self):
        from dataclasses import asdict

        from src.api.qa import _query_response

        service, _ = _build_service(_explanation(), _SUPPORTED)
        result = service.answer("performance of contracts")
        # _query_response flattens asdict(explanation) into QueryResponse; the
        # populated entailment dict must not change the public schema shape.
        public = _query_response(result)
        assert public.answer
        assert public.confidence.score > 0.45
        # The entailment detail is an extra (internal) field on the dataclass and
        # is simply preserved in asdict without altering declared schema fields.
        assert "citation_entailment" in asdict(result.explanation)
        assert _query_response(result) is not None
