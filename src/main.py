"""FastAPI application entry point."""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.qa import LLMQuotaExceededError
from src.api.router import api_router
from src.config.logging_config import get_logger, setup_logging
from src.config.settings import ENV_FILE_LOADED, ENV_FILE_PATH, settings
from src.llm.llm import log_llm_configuration
from src.middleware.security import SecurityMiddleware
from src.monitoring.middleware import MetricsMiddleware
from src.utils.exceptions import AppException

PREWARM_TIMEOUT_SECONDS = 300.0


def _elapsed_ms(started: float) -> int:
    """Whole milliseconds elapsed since ``started`` (perf counter)."""
    return int(round((time.perf_counter() - started) * 1000))


async def _prewarm_corpus(log) -> None:
    """Build + cache the shared graph/vector corpus at startup.

    A failure is logged and swallowed so startup never crashes on a down
    Qdrant or an unreachable embedding backend.
    """
    from src.llm import service as svc

    started = time.perf_counter()
    log.info("corpus.prewarm.start", elapsed_ms=0)
    try:
        await asyncio.wait_for(
            asyncio.to_thread(svc.get_default_corpus),
            timeout=PREWARM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        log.exception(
            "corpus.prewarm.failed",
            elapsed_ms=_elapsed_ms(started),
            error=str(exc),
        )
        return
    log.info("corpus.prewarm.complete", elapsed_ms=_elapsed_ms(started))


async def _prewarm_service(log) -> None:
    """Build + cache the default QueryService at startup.

    A failure is logged and swallowed so startup never crashes on a miswired
    LLM client or provenance store.
    """
    from src.llm import service as svc

    started = time.perf_counter()
    log.info("service.prewarm.start", elapsed_ms=0)
    try:
        await asyncio.wait_for(
            asyncio.to_thread(svc.get_default_service),
            timeout=PREWARM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        log.exception(
            "service.prewarm.failed",
            elapsed_ms=_elapsed_ms(started),
            error=str(exc),
        )
        return
    log.info("service.prewarm.complete", elapsed_ms=_elapsed_ms(started))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    setup_logging(level=settings.APP_LOG_LEVEL)
    log = get_logger("main")
    log.info("app.starting", env=settings.APP_ENV, version=settings.APP_VERSION)
    log.info(
        "config.env_file",
        path=str(ENV_FILE_PATH),
        loaded=ENV_FILE_LOADED,
    )
    log_llm_configuration()

    # Eagerly build the shared corpus and query service at startup so the first
    # upload/QA request never triggers a slow (and previously deadlock-prone)
    # lazy build. Non-fatal: a failure is logged and the server still starts.
    await _prewarm_corpus(log)
    await _prewarm_service(log)

    yield
    log.info("app.stopping")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Explainable Multilingual Hierarchical Graph-RAG with HHGR for Indian "
        "Legal Document Intelligence"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityMiddleware)
app.add_middleware(MetricsMiddleware)

app.include_router(api_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Global handler for application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


@app.exception_handler(LLMQuotaExceededError)
async def llm_quota_exceeded_handler(request: Request, exc: LLMQuotaExceededError) -> JSONResponse:
    """Render LLM quota/rate-limit failures as a clean 429 with provider details."""
    provider = (exc.provider or "provider").capitalize()
    content = {
        "error": (
            f"{provider} quota exceeded"
            if exc.quota_exhausted
            else f"{provider} rate limited"
        ),
        "provider": exc.provider,
        "details": exc.details,
    }
    if exc.retry_after is not None:
        content["retry_after"] = exc.retry_after
    return JSONResponse(status_code=429, content=content)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
