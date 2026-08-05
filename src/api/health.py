"""Health check endpoints.

Provides liveness/readiness probes plus per-dependency health checks for
database (Neo4j), vector store (Qdrant), and LLM. All checks are additive and
do not modify existing application logic.
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from qdrant_client import QdrantClient

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.models.schemas import HealthResponse, ServiceHealth
from src.utils.constants import HEALTH_FAILED, HEALTH_OK

log = get_logger("health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(
        status=HEALTH_OK,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe for orchestrators."""
    return {"ready": HEALTH_OK}


@router.get("/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """Liveness probe — the process is up and serving requests."""
    return HealthResponse(
        status=HEALTH_OK,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )


@router.get("/check/database", response_model=ServiceHealth)
async def check_database() -> ServiceHealth:
    """Check connectivity to the Neo4j knowledge graph database."""
    return await _check_database()


@router.get("/check/vector", response_model=ServiceHealth)
async def check_vector() -> ServiceHealth:
    """Check connectivity to the Qdrant vector store."""
    return await _check_vector()


@router.get("/check/llm", response_model=ServiceHealth)
async def check_llm() -> ServiceHealth:
    """Check the configured LLM provider is reachable."""
    return await _check_llm()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _check_database() -> ServiceHealth:
    """Probe Neo4j with a trivial query and a short timeout."""
    from neo4j import GraphDatabase

    start = time.monotonic()
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=1.0,
            connection_acquisition_timeout=1.0,
            max_transaction_retry_time=0.5,
        )
        try:
            with driver.session() as session:
                session.run("RETURN 1").consume()
            return _ok("database", start)
        finally:
            driver.close()
    except Exception as exc:  # noqa: BLE001 - report any dependency failure
        log.warning("health.database_failed", error=str(exc))
        return _failed("database", start, str(exc))


async def _check_vector() -> ServiceHealth:
    """Probe Qdrant by listing collections."""
    start = time.monotonic()
    try:
        client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=1.0,
            check_compatibility=False,
        )
        try:
            client.get_collections()
            return _ok("vector", start)
        finally:
            client.close()
    except Exception as exc:  # noqa: BLE001 - report any dependency failure
        log.warning("health.vector_failed", error=str(exc))
        return _failed("vector", start, str(exc))


async def _check_llm() -> ServiceHealth:
    """Probe the configured LLM with a trivial completion."""
    from src.llm.llm import LLMError, get_llm_client

    start = time.monotonic()
    try:
        client = get_llm_client()
        client.complete(
            [{"role": "user", "content": "Reply with the single word: ok"}],
            max_tokens=5,
        )
        return _ok("llm", start)
    except LLMError as exc:
        log.warning("health.llm_failed", error=str(exc))
        return _failed("llm", start, str(exc))
    except Exception as exc:  # noqa: BLE001 - report any dependency failure
        log.warning("health.llm_failed", error=str(exc))
        return _failed("llm", start, str(exc))


def _ok(service: str, start: float) -> ServiceHealth:
    return ServiceHealth(
        status=HEALTH_OK,
        service=service,
        ok=True,
        latency_ms=round((time.monotonic() - start) * 1000, 2),
    )


def _failed(service: str, start: float, detail: str) -> ServiceHealth:
    return ServiceHealth(
        status=HEALTH_FAILED,
        service=service,
        ok=False,
        detail=detail[:500],
        latency_ms=round((time.monotonic() - start) * 1000, 2),
    )
