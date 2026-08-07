"""Main API router aggregating all sub-routers."""

from fastapi import APIRouter

from src.api.documents import router as documents_router
from src.api.health import router as health_router
from src.api.qa import router as qa_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(qa_router)
api_router.include_router(documents_router)
