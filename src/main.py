"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.router import api_router
from src.config.logging_config import get_logger, setup_logging
from src.config.settings import settings
from src.middleware.security import SecurityMiddleware
from src.monitoring.middleware import MetricsMiddleware
from src.utils.exceptions import AppException


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    setup_logging(level=settings.APP_LOG_LEVEL)
    log = get_logger("main")
    log.info("app.starting", env=settings.APP_ENV, version=settings.APP_VERSION)
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


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
