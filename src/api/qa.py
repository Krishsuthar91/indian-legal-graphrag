"""QA endpoints — explainable LLM answer generation (Module 7).

- POST /query           -> generate an answer with full provenance
- POST /explain         -> retrieve + explain without calling the LLM
- GET /provenance/{id}  -> fetch a stored provenance record
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter

from src.config.logging_config import get_logger
from src.llm.schemas import ExplainRequest, ExplanationResponse, QueryRequest, QueryResponse
from src.llm.service import QueryService, get_default_service
from src.utils.exceptions import NotFoundException, ValidationException

log = get_logger("qa_api")

router = APIRouter(tags=["qa"])

# Overridable in tests to avoid building the full corpus service.
service_factory: Callable[[], QueryService] = get_default_service


def _query_response(result) -> QueryResponse:
    """Flatten an AnswerResult's explanation into the top-level response model."""
    data = asdict(result.explanation)
    data.update(
        {
            "provenance_id": result.provenance_id,
            "answer": result.answer,
            "model": result.model,
            "duration_ms": result.duration_ms,
        }
    )
    return QueryResponse.model_validate(data)


@router.post("/query", response_model=QueryResponse, summary="Answer with provenance")
async def answer_query(req: QueryRequest) -> QueryResponse:
    """Generate an explainable answer for the given legal question."""
    if not req.query.strip():
        raise ValidationException("query must not be empty")
    result = service_factory().answer(
        query=req.query,
        top_k=req.top_k,
        language=req.language,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    return _query_response(result)


@router.post("/explain", response_model=ExplanationResponse, summary="Explain retrieval")
async def explain_query(req: ExplainRequest) -> ExplanationResponse:
    """Run retrieval and return the explanation without invoking the LLM."""
    if not req.query.strip():
        raise ValidationException("query must not be empty")
    explanation = service_factory().explain(
        query=req.query,
        top_k=req.top_k,
        language=req.language,
    )
    return ExplanationResponse.model_validate(asdict(explanation))


@router.get("/provenance/{provenance_id}", response_model=QueryResponse, summary="Get provenance")
async def get_provenance(provenance_id: str) -> QueryResponse:
    """Return a previously generated answer and its full provenance record."""
    record = service_factory().get_provenance(provenance_id)
    if record is None:
        raise NotFoundException(detail=f"Provenance record {provenance_id!r} not found")
    data = dict(record["explanation"])
    data.update(
        {
            "provenance_id": record["provenance_id"],
            "answer": record["answer"],
            "model": record["model"],
            "duration_ms": record["duration_ms"],
        }
    )
    return QueryResponse.model_validate(data)
