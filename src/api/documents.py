"""Document upload & indexing endpoints.

Exposes the existing offline pipeline (ingestion -> hierarchy parse -> graph
import -> vector index) as a single HTTP endpoint so the frontend can let users
upload a legal document and immediately query it.
"""

from __future__ import annotations

import asyncio
import traceback
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.embeddings import EmbeddingService, HierarchyIndexer, QdrantStore
from src.hierarchy import parser as hierarchy_parser
from src.ingestion import pipeline
from src.knowledge_graph.importer import import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.service import get_default_corpus
from src.models.schemas import DocumentUploadResponse
from src.utils.exceptions import ValidationException

log = get_logger("documents_api")

router = APIRouter(tags=["documents"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"

# Hard cap on how long the synchronous indexing chain may run before the
# request is aborted. Prevents a hung pipeline step (e.g. an unreachable vector
# store or a pathologically slow corpus build) from blocking the client forever.
UPLOAD_TIMEOUT_SECONDS = 60

# Overridable in tests to avoid building the full corpus service.
corpus_factory: Callable[
    [], tuple[InMemoryGraph, QdrantStore, EmbeddingService]
] = get_default_corpus


def _get_corpus() -> tuple[InMemoryGraph, QdrantStore, EmbeddingService]:
    return corpus_factory()


def _save_upload(file: UploadFile, file_name: str) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file_name}"
    size = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.DOCUMENT_UPLOAD_MAX_BYTES:
                    raise ValidationException(
                        f"File exceeds the {settings.DOCUMENT_UPLOAD_MAX_BYTES} byte limit"
                    )
                out.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest


def ingest_upload(file_path: Path, original_name: str | None = None) -> DocumentUploadResponse:
    """Run the full chain: ingest -> parse hierarchy -> import graph -> index."""
    log.info("documents.ingest.start", path=str(file_path))
    doc = pipeline.ingest_document(file_path)
    log.info("documents.ingest.complete", document_id=doc.document_id)

    processed_path = pipeline.OUTPUT_DIR / f"{doc.document_id}.json"
    hierarchy = hierarchy_parser.parse_and_save(processed_path)
    hierarchy_path = hierarchy_parser.HIERARCHY_DIR / f"{hierarchy.document_id}.json"

    graph, store, embedding_service = _get_corpus()

    log.info(
        "documents.import.start",
        document_id=doc.document_id,
        path=str(hierarchy_path),
    )
    imported = import_hierarchy_json(graph, hierarchy_path)
    log.info(
        "documents.import.complete",
        document_id=doc.document_id,
        nodes=imported["nodes_created"],
        edges=imported["edges_created"],
    )

    log.info("documents.index.start", document_id=doc.document_id)
    indexed = HierarchyIndexer(graph, store, embedding_service).index_hierarchy_file(
        hierarchy_path
    )
    log.info(
        "documents.index.complete",
        document_id=doc.document_id,
        collections=indexed.get("collections"),
    )

    log.info("documents.response.start", document_id=doc.document_id)
    response = DocumentUploadResponse(
        document_id=doc.document_id,
        title=doc.title,
        language=doc.language,
        num_pages=len(doc.pages),
        file_name=original_name or Path(file_path).name,
        nodes_indexed=imported["nodes_created"],
        collections=indexed.get("collections", {}),
        message=(
            "Document uploaded, parsed, imported into the knowledge graph, "
            "and indexed for retrieval."
        ),
    )
    log.info(
        "documents.response.return",
        document_id=doc.document_id,
        nodes=imported["nodes_created"],
    )
    return response


async def _run_upload(file: UploadFile, file_name: str) -> DocumentUploadResponse:
    """Run the synchronous upload pipeline off the event loop with a hard timeout."""
    dest = await asyncio.wait_for(
        asyncio.to_thread(_save_upload, file, file_name),
        timeout=UPLOAD_TIMEOUT_SECONDS,
    )
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(ingest_upload, dest, file_name),
            timeout=UPLOAD_TIMEOUT_SECONDS,
        )
    finally:
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Upload and index a legal document",
)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """Upload a PDF/DOCX/TXT legal document and index it for retrieval."""
    log.info("documents.upload.start", filename=file.filename)
    file_name = Path(file.filename or "document").name
    ext = Path(file_name).suffix.lower()
    if ext not in pipeline.SUPPORTED_EXTENSIONS:
        raise ValidationException(
            f"Unsupported file type: {ext or '(none)'}. "
            f"Supported: {sorted(pipeline.SUPPORTED_EXTENSIONS)}"
        )

    try:
        result = await _run_upload(file, file_name)
    except TimeoutError as exc:
        log.error(
            "documents.upload_timeout",
            file=file_name,
            timeout_seconds=UPLOAD_TIMEOUT_SECONDS,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"Document indexing timed out after {UPLOAD_TIMEOUT_SECONDS}s "
                "and the request was aborted. The indexing work may still be "
                "finishing in the background."
            ),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("documents.upload_error", file=file_name, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Document indexing failed: {exc}\n\n{traceback.format_exc()}",
        ) from exc
    log.info(
        "documents.upload.complete",
        file=file_name,
        document_id=result.document_id,
    )
    return result
