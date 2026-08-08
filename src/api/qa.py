"""QA endpoints — explainable LLM answer generation (Module 7).

- POST /query           -> generate an answer with full provenance
- POST /explain         -> retrieve + explain without calling the LLM
- GET /provenance/{id}  -> fetch a stored provenance record

All service work is synchronous and may touch external services (Qdrant, an
LLM API), so it is dispatched to a worker thread with a hard timeout. This
guarantees a request always returns JSON instead of hanging the event loop.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.llm.llm import (
    LLMAuthenticationError,
    LLMConnectivityError,
    LLMNotFoundError,
    LLMPermissionError,
    LLMProviderError,
    LLMTimeoutError,
    RateLimitError,
)
from src.llm.schemas import ExplainRequest, ExplanationResponse, QueryRequest, QueryResponse
from src.llm.service import QueryService, get_default_service
from src.utils.exceptions import AppException, NotFoundException, ValidationException

log = get_logger("qa_api")

router = APIRouter(tags=["qa"])

# The LLM is given slightly less than the outer request timeout so that a
# deadline-hit (clean 504) wins before the blanket asyncio.wait_for (500).
_LLM_DEADLINE_MARGIN_SECONDS = 1.0

# Overridable in tests to avoid building the full corpus service.
service_factory: Callable[[], QueryService] = get_default_service


class LLMQuotaExceededError(AppException):
    """Rendered as a clean 429 with the provider-facing quota JSON shape."""

    def __init__(
        self,
        *,
        provider: str,
        retry_after: float | None,
        details: str,
        quota_exhausted: bool,
    ) -> None:
        super().__init__(
            detail=details,
            code="LLM_RATE_LIMITED",
            status_code=429,
        )
        self.provider = provider
        self.retry_after = retry_after
        self.details = details
        self.quota_exhausted = quota_exhausted


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


def _run_answer(req: QueryRequest):
    """Blocking QA work — runs off the event loop (may call Qdrant + LLM).

    The LLM deadline is the request timeout minus a small margin, so a slow or
    overloaded provider produces a clean 504 (deadline exceeded) instead of
    the outer ``asyncio.wait_for`` 500. Retrieval (explain) happens before the
    deadline starts mattering — it is typically well under a second.
    """
    deadline = time.monotonic() + max(
        0.5, settings.QA_REQUEST_TIMEOUT_SECONDS - _LLM_DEADLINE_MARGIN_SECONDS
    )
    return service_factory().answer(
        query=req.query,
        top_k=req.top_k,
        language=req.language,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        deadline=deadline,
    )


def _run_explain(req: ExplainRequest):
    """Blocking retrieval-only work — runs off the event loop (may call Qdrant)."""
    return service_factory().explain(
        query=req.query,
        top_k=req.top_k,
        language=req.language,
    )


def _run_provenance(provenance_id: str):
    """Blocking provenance lookup (reads the provenance store)."""
    return service_factory().get_provenance(provenance_id)


async def _dispatch(fn, *args) -> Any:
    """Run a blocking service call in a thread with a hard timeout.

    Returns the result, or raises an HTTPException — 429 when the LLM provider
    throttles/quota-exhausts, otherwise 500 with a traceback if the call raises
    or never completes within ``QA_REQUEST_TIMEOUT_SECONDS``.
    """
    timeout = settings.QA_REQUEST_TIMEOUT_SECONDS
    log.info("qa.request_start", fn=fn.__name__, timeout=timeout)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(fn, *args),
            timeout=timeout,
        )
    except TimeoutError as exc:
        log.error("qa.request_timeout", fn=fn.__name__, timeout=timeout)
        raise HTTPException(
            status_code=500,
            detail=(
                f"Request timed out after {timeout}s while waiting on the "
                "backend service. The downstream dependency may be "
                "unavailable or too slow."
            ),
        ) from exc
    except HTTPException:
        raise
    except RateLimitError as exc:
        log.error(
            "qa.llm_rate_limited",
            fn=fn.__name__,
            status_code=exc.status_code,
            retry_after=exc.retry_after,
            quota_exhausted=exc.quota_exhausted,
            provider_body=exc.provider_body[:500],
        )
        raise LLMQuotaExceededError(
            provider=exc.provider,
            retry_after=exc.retry_after,
            details=exc.provider_body or str(exc),
            quota_exhausted=exc.quota_exhausted,
        ) from exc
    except LLMTimeoutError as exc:
        log.error(
            "qa.llm_timeout",
            fn=fn.__name__,
            timeout_seconds=exc.timeout_seconds,
            deadline_margin=_LLM_DEADLINE_MARGIN_SECONDS,
            error=str(exc),
        )
        raise HTTPException(
            status_code=504,
            detail=(
                "The LLM provider did not respond within "
                f"{exc.timeout_seconds:.1f}s. It may be slow or overloaded — "
                "please retry in a moment."
            ),
        ) from exc
    except LLMConnectivityError as exc:
        log.error("qa.llm_connectivity", fn=fn.__name__, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="The LLM provider endpoint could not be reached. "
            "Please check network connectivity and try again.",
        ) from exc
    except LLMAuthenticationError as exc:
        log.error("qa.llm_auth", fn=fn.__name__, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="The LLM provider rejected the API key (HTTP 401). "
            "Please check the configured provider key.",
        ) from exc
    except LLMPermissionError as exc:
        log.error("qa.llm_permission", fn=fn.__name__, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="The LLM provider denied access (HTTP 403). The API key "
            "may not have access to the configured model.",
        ) from exc
    except LLMNotFoundError as exc:
        log.error("qa.llm_not_found", fn=fn.__name__, error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="The LLM model or endpoint was not found (HTTP 404). "
            "Please check the configured model and base URL.",
        ) from exc
    except LLMProviderError as exc:
        log.error(
            "qa.llm_provider_error",
            fn=fn.__name__,
            http_status=exc.http_status,
            error=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "The LLM provider returned an error "
                f"(HTTP {exc.http_status or 'unknown'}). Please try again."
            ),
        ) from exc
    except Exception as exc:
        log.exception("qa.request_error", fn=fn.__name__, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Backend service failed: {exc}\n\n{traceback.format_exc()}",
        ) from exc
    log.info("qa.request_complete", fn=fn.__name__, timeout=timeout)
    return result


@router.post("/query", response_model=QueryResponse, summary="Answer with provenance")
async def answer_query(req: QueryRequest) -> QueryResponse:
    """Generate an explainable answer for the given legal question."""
    if not req.query.strip():
        raise ValidationException("query must not be empty")
    log.info("query.return.start")
    result = await _dispatch(_run_answer, req)
    response = _query_response(result)
    log.info("query.return.complete")
    return response


@router.post("/explain", response_model=ExplanationResponse, summary="Explain retrieval")
async def explain_query(req: ExplainRequest) -> ExplanationResponse:
    """Run retrieval and return the explanation without invoking the LLM."""
    if not req.query.strip():
        raise ValidationException("query must not be empty")
    explanation = await _dispatch(_run_explain, req)
    return ExplanationResponse.model_validate(asdict(explanation))


@router.get("/provenance/{provenance_id}", response_model=QueryResponse, summary="Get provenance")
async def get_provenance(provenance_id: str) -> QueryResponse:
    """Return a previously generated answer and its full provenance record."""
    record = await _dispatch(_run_provenance, provenance_id)
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
