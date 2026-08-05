"""API and ingestion schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class ServiceHealth(BaseModel):
    status: str
    service: str
    ok: bool
    detail: str = ""
    latency_ms: float = 0.0


class ErrorResponse(BaseModel):
    detail: str
    code: str


# ---------------------------------------------------------------------------
# Ingestion schemas
# ---------------------------------------------------------------------------

class PageData(BaseModel):
    page_number: int
    text: str
    is_scanned: bool = False


class DocumentMetadata(BaseModel):
    file_name: str
    file_path: str
    file_size_bytes: int
    file_type: str
    num_pages: int
    language: str = "unknown"
    creation_date: str | None = None
    pdf_properties: dict = Field(default_factory=dict)
    is_scanned: bool = False
    ocr_applied: bool = False


class IngestedDocument(BaseModel):
    document_id: str
    title: str
    language: str
    pages: list[PageData]
    metadata: DocumentMetadata
