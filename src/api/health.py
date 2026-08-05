"""Health check endpoints."""

from fastapi import APIRouter

from src.config.settings import settings
from src.models.schemas import HealthResponse
from src.utils.constants import HEALTH_OK

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
