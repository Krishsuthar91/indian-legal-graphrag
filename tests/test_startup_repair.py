"""Regression tests for the V3.0 startup-hang repair.

Covers the three behaviors that fix cold/warm startup without changing
retrieval or ranking: (1) embedding snapshots round-trip through the in-memory
store, (2) a second ``index_graph`` over fresh payloads embeds nothing, and
(3) the API returns a 503 JSON "warming" response instead of blocking on the
corpus build lock (or surfacing ECONNREFUSED/500 to the frontend).
"""

from __future__ import annotations

import pytest

from src.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingService,
    HierarchyIndexer,
    QdrantStore,
)
from src.embeddings.store import _snapshot_path
from src.llm import service as svc
from tests.qa_helpers import build_graph

DIM = 32


@pytest.fixture()
def graph():
    return build_graph()


def _wire(graph, tmp_path, monkeypatch) -> tuple[object, QdrantStore, EmbeddingService]:
    monkeypatch.setattr(svc.settings, "EMBEDDING_SNAPSHOT_DIR", str(tmp_path))
    provider = DeterministicEmbeddingProvider(dim=DIM)
    service = EmbeddingService(provider=provider)
    store = QdrantStore(dim=DIM, in_memory=True)
    store.ensure_collections()
    return graph, store, service


def test_snapshot_roundtrip_preserves_points_and_vectors(graph, tmp_path, monkeypatch):
    graph, store, service = _wire(graph, tmp_path, monkeypatch)
    HierarchyIndexer(graph, store, service).index_graph()
    key = svc._embedding_cache_key(service.provider, DIM)
    saved = store.save_snapshot(key)
    assert saved > 0

    restored_store = QdrantStore(dim=DIM, in_memory=True)
    restored_store.ensure_collections()
    assert restored_store.load_snapshot(key) == saved

    for collection in store.collections:
        assert store.count(collection) == restored_store.count(collection)
    original = store.indexed_payloads("sections")
    restored = restored_store.indexed_payloads("sections")
    assert set(original) == set(restored)
    assert all(original[n]["text_hash"] == restored[n]["text_hash"] for n in original)


def test_snapshot_stale_key_is_ignored(graph, tmp_path, monkeypatch):
    graph, store, service = _wire(graph, tmp_path, monkeypatch)
    HierarchyIndexer(graph, store, service).index_graph()
    store.save_snapshot("v1_key")
    restored_store = QdrantStore(dim=DIM, in_memory=True)
    restored_store.ensure_collections()
    assert restored_store.load_snapshot("v2_key") == 0
    assert _snapshot_path("v1_key").exists()


def test_second_index_graph_embeds_nothing_when_fresh(graph, tmp_path, monkeypatch):
    graph, store, service = _wire(graph, tmp_path, monkeypatch)
    calls = {"n": 0}

    class CountingProvider(DeterministicEmbeddingProvider):
        def encode(self, texts):
            calls["n"] += len(texts)
            return super().encode(texts)

    indexer = HierarchyIndexer(graph, store, EmbeddingService(provider=CountingProvider(dim=DIM)))
    indexer.index_graph()
    calls["n"] = 0
    second = indexer.index_graph()
    assert calls["n"] == 0  # every payload hash was already fresh
    assert sum(second["collections"].values()) == 0


def test_qa_query_returns_503_json_while_corpus_warming(client, monkeypatch):
    from src.api import qa as qa_api

    monkeypatch.setattr(svc, "_build_in_progress", True)
    for name in ("_default_graph", "_default_store", "_default_embedding"):
        monkeypatch.setattr(svc, name, None)
    monkeypatch.setattr(qa_api, "service_factory", svc.get_default_service)
    monkeypatch.setattr(qa_api, "_CORPUS_WARMING_GRACE_SECONDS", 0.1)

    resp = client.post("/api/v1/query", json={"query": "What is murder?"})
    assert resp.status_code == 503
    body = resp.json()
    assert "detail" in body and "still indexing" in body["detail"]
    assert resp.headers["content-type"].startswith("application/json")


def test_qa_warming_gate_allows_lazy_build_when_not_building(client, monkeypatch):
    """Not building + not ready must NOT 503: the lazy build path is preserved."""
    from src.api import qa as qa_api
    from src.llm.llm import MockLLMClient
    from src.llm.provenance import ProvenanceStore
    from src.llm.service import QueryService
    from src.llm.explanation import ExplainabilityEngine

    monkeypatch.setattr(svc, "_build_in_progress", False)
    for name in ("_default_graph", "_default_store", "_default_embedding"):
        monkeypatch.setattr(svc, name, None)
    monkeypatch.setattr(qa_api, "service_factory", lambda: QueryService(
        ExplainabilityEngine(graph, vector_retriever=None),
        MockLLMClient(),
        ProvenanceStore(),
    ))

    import asyncio

    gate = qa_api._await_corpus_ready()
    asyncio.run(gate)  # returns without 503 when the corpus is not building