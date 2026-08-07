"""Tests for the document upload & indexing endpoint."""

import time

import pytest

from src.api import documents as documents_api
from src.embeddings import VectorRetriever
from src.hierarchy import parser as hierarchy_parser
from src.ingestion import pipeline
from tests.qa_helpers import build_graph, build_retriever


@pytest.fixture()
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect every data write into a temp directory."""
    uploads = tmp_path / "uploads"
    processed = tmp_path / "processed"
    hierarchy = tmp_path / "hierarchy"
    monkeypatch.setattr(documents_api, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", processed)
    monkeypatch.setattr(hierarchy_parser, "PROCESSED_DIR", processed)
    monkeypatch.setattr(hierarchy_parser, "HIERARCHY_DIR", hierarchy)
    return uploads, processed, hierarchy


@pytest.fixture()
def corpus(monkeypatch):
    """Inject a lightweight in-memory corpus instead of the real data dir."""
    graph = build_graph()
    retriever = build_retriever(graph)
    store = retriever.store
    service = retriever.service
    monkeypatch.setattr(
        documents_api, "corpus_factory", lambda: (graph, store, service)
    )
    return graph, store, service


def test_upload_indexes_document(client, sample_txt, isolated_dirs, corpus):
    graph, store, service = corpus
    before = sum(store.count(c) for c in store.collections)

    with sample_txt.open("rb") as fh:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.txt", fh, "text/plain")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"]
    assert data["file_name"] == "sample.txt"
    assert data["nodes_indexed"] >= 1
    assert data["num_pages"] >= 1
    assert data["message"]

    assert store.count("documents") >= 1
    after = sum(store.count(c) for c in store.collections)
    assert after - before >= data["nodes_indexed"]

    hits = VectorRetriever(graph, store, service).dense_search(
        "equality before the law", top_k=10
    )
    assert hits
    assert any(h.payload.get("doc_id") == data["document_id"] for h in hits)


def test_upload_rejects_unsupported_extension(client, sample_txt, isolated_dirs, corpus):
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.exe", sample_txt.read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_upload_missing_file_returns_422(client, isolated_dirs, corpus):
    resp = client.post("/api/v1/documents/upload")
    assert resp.status_code == 422


def test_upload_oversized_file_rejected(client, tmp_path, isolated_dirs, corpus, monkeypatch):
    from src.config.settings import settings

    monkeypatch.setattr(settings, "DOCUMENT_UPLOAD_MAX_BYTES", 16)
    big = tmp_path / "big.txt"
    big.write_text("x" * 1000, encoding="utf-8")
    with big.open("rb") as fh:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("big.txt", fh, "text/plain")},
        )
    assert resp.status_code == 422
    assert "limit" in resp.json()["detail"].lower()


def test_upload_failure_returns_500_with_traceback(client, sample_txt, isolated_dirs, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("indexing exploded")

    monkeypatch.setattr(documents_api, "ingest_upload", boom)

    with sample_txt.open("rb") as fh:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.txt", fh, "text/plain")},
        )

    assert resp.status_code == 500
    data = resp.json()
    assert "detail" in data
    assert "indexing exploded" in data["detail"]
    assert "Traceback" in data["detail"]


def test_upload_hang_times_out_and_returns_500_json(
    client, sample_txt, isolated_dirs, monkeypatch
):
    def hang(*args, **kwargs):
        time.sleep(5)
        return None

    monkeypatch.setattr(documents_api, "UPLOAD_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(documents_api, "ingest_upload", hang)

    with sample_txt.open("rb") as fh:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.txt", fh, "text/plain")},
        )

    assert resp.status_code == 500
    data = resp.json()
    assert "timed out" in data["detail"].lower()


def test_first_upload_without_prior_corpus_build_returns_json(
    client, sample_txt, isolated_dirs, monkeypatch
):
    """Upload as the very first request: corpus is built lazily, then 200 JSON."""
    from src.llm import service as svc
    from tests.qa_helpers import build_fast_corpus

    monkeypatch.setattr(svc, "build_default_corpus", build_fast_corpus)
    for name in ("_default_graph", "_default_store", "_default_embedding"):
        monkeypatch.setattr(svc, name, None)
    monkeypatch.setattr(documents_api, "corpus_factory", svc.get_default_corpus)

    with sample_txt.open("rb") as fh:
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.txt", fh, "text/plain")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"]
    assert data["file_name"] == "sample.txt"
    assert data["message"]


def test_startup_prewarms_corpus_once_and_first_upload_reuses_cache(
    sample_txt, isolated_dirs, monkeypatch
):
    """Startup builds the corpus exactly once; the first upload reuses it."""
    from fastapi.testclient import TestClient

    from src.llm import service as svc
    from src.main import app
    from tests.qa_helpers import build_fast_corpus

    build_calls = {"count": 0}
    built = {}

    def counting_build():
        build_calls["count"] += 1
        graph, store, service = build_fast_corpus()
        built["graph"] = graph
        return graph, store, service

    monkeypatch.setattr(svc, "build_default_corpus", counting_build)
    for name in ("_default_service", "_default_graph", "_default_store", "_default_embedding"):
        monkeypatch.setattr(svc, name, None)

    with TestClient(app) as c:
        assert build_calls["count"] == 1

        with sample_txt.open("rb") as fh:
            resp = c.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.txt", fh, "text/plain")},
            )

        assert resp.status_code == 200
        assert build_calls["count"] == 1
        assert svc._default_graph is built["graph"]


def test_startup_survives_prewarm_failure(sample_txt, isolated_dirs, monkeypatch):
    """A failed prewarm must be logged, not crash FastAPI startup."""
    from fastapi.testclient import TestClient

    from src.llm import service as svc
    from src.main import app

    def boom():
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(svc, "build_default_corpus", boom)
    for name in ("_default_service", "_default_graph", "_default_store", "_default_embedding"):
        monkeypatch.setattr(svc, name, None)

    with TestClient(app) as c:
        resp = c.get("/")
        assert resp.status_code == 200
