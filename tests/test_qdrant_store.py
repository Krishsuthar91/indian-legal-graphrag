"""Tests for the QdrantStore wrapper (in-memory mode)."""

import pytest

from src.embeddings.models import DEFAULT_COLLECTIONS
from src.embeddings.store import QdrantStore, point_id


@pytest.fixture()
def store():
    s = QdrantStore(dim=4, in_memory=True)
    s.ensure_collections()
    yield s
    s.close()


class TestCollections:
    def test_default_collections_created(self, store):
        for name in DEFAULT_COLLECTIONS:
            assert store.collection_exists(name)

    def test_dimension_configured(self, store):
        from qdrant_client import models

        info = store._client.get_collection("sections")
        assert info.config.params.vectors.size == 4
        assert info.config.params.vectors.distance == models.Distance.COSINE

    def test_ensure_is_idempotent(self, store):
        store.ensure_collections()
        for name in DEFAULT_COLLECTIONS:
            assert store.collection_exists(name)

    def test_delete_collection(self, store):
        store.delete_collection("sections")
        assert not store.collection_exists("sections")


class TestUpsertAndSearch:
    def test_upsert_and_count(self, store):
        store.upsert(
            "sections",
            "s1",
            [1.0, 0.0, 0.0, 0.0],
            {"node_id": "s1", "language": "en", "level": 5},
        )
        assert store.count("sections") == 1

    def test_upsert_batch(self, store):
        items = [
            {"node_id": "s1", "vector": [1.0, 0.0, 0.0, 0.0], "payload": {"level": 5}},
            {"node_id": "s2", "vector": [0.0, 1.0, 0.0, 0.0], "payload": {"level": 5}},
        ]
        assert store.upsert_batch("sections", items) == 2
        assert store.count("sections") == 2

    def test_search_returns_nearest(self, store):
        store.upsert_batch(
            "sections",
            [
                {"node_id": "s1", "vector": [1.0, 0.0, 0.0, 0.0],
                 "payload": {"node_id": "s1", "language": "en"}},
                {"node_id": "s2", "vector": [0.9, 0.1, 0.0, 0.0],
                 "payload": {"node_id": "s2", "language": "hi"}},
                {"node_id": "s3", "vector": [0.1, 0.9, 0.0, 0.0],
                 "payload": {"node_id": "s3", "language": "en"}},
            ],
        )
        hits = store.search("sections", [1.0, 0.0, 0.0, 0.0], top_k=3)
        assert hits[0]["node_id"] == "s1"
        assert hits[0]["score"] > hits[1]["score"] > hits[2]["score"]

    def test_search_returns_payload(self, store):
        store.upsert(
            "sections", "s1", [1.0, 0.0, 0.0, 0.0],
            {"node_id": "s1", "language": "en", "level": 5},
        )
        hits = store.search("sections", [1.0, 0.0, 0.0, 0.0], top_k=1)
        assert hits[0]["payload"]["level"] == 5
        assert hits[0]["collection"] == "sections"

    def test_search_language_filter(self, store):
        store.upsert_batch(
            "sections",
            [
                {"node_id": "s1", "vector": [1.0, 0.0, 0.0, 0.0],
                 "payload": {"node_id": "s1", "language": "en"}},
                {"node_id": "s2", "vector": [1.0, 0.0, 0.0, 0.0],
                 "payload": {"node_id": "s2", "language": "hi"}},
            ],
        )
        hits = store.search("sections", [1.0, 0.0, 0.0, 0.0], top_k=5, language="hi")
        assert [h["node_id"] for h in hits] == ["s2"]

    def test_search_multiple_aggregates(self, store):
        store.upsert("sections", "s1", [1.0, 0.0, 0.0, 0.0], {"node_id": "s1"})
        store.upsert("chapters", "c1", [0.95, 0.05, 0.0, 0.0], {"node_id": "c1"})
        store.upsert("clauses", "cl1", [0.2, 0.8, 0.0, 0.0], {"node_id": "cl1"})
        hits = store.search_multiple(
            ["sections", "chapters", "clauses"], [1.0, 0.0, 0.0, 0.0], top_k=3
        )
        assert [h["node_id"] for h in hits] == ["s1", "c1", "cl1"]
        assert {h["collection"] for h in hits} == {"sections", "chapters", "clauses"}

    def test_search_multiple_per_collection_limit(self, store):
        for i in range(5):
            store.upsert("sections", f"s{i}", [1.0, 0.0, 0.0, 0.0], {"node_id": f"s{i}"})
        store.upsert("chapters", "c1", [1.0, 0.0, 0.0, 0.0], {"node_id": "c1"})
        store.upsert("chapters", "c2", [1.0, 0.0, 0.0, 0.0], {"node_id": "c2"})
        hits = store.search_multiple(
            ["sections", "chapters"], [1.0, 0.0, 0.0, 0.0], top_k=10, per_collection=2
        )
        assert len(hits) == 4


class TestPointManagement:
    def test_point_id_deterministic(self):
        assert point_id("n1") == point_id("n1")
        assert point_id("n1") != point_id("n2")

    def test_delete(self, store):
        store.upsert("sections", "s1", [1.0, 0.0, 0.0, 0.0], {})
        store.upsert("sections", "s2", [1.0, 0.0, 0.0, 0.0], {})
        assert store.delete("sections", ["s1"]) == 1
        assert store.count("sections") == 1

    def test_indexed_ids(self, store):
        store.upsert("sections", "s1", [1.0, 0.0, 0.0, 0.0], {"node_id": "s1", "text_hash": "a"})
        store.upsert("sections", "s2", [1.0, 0.0, 0.0, 0.0], {"node_id": "s2", "text_hash": "b"})
        assert store.indexed_ids("sections") == {"s1", "s2"}

    def test_indexed_payloads(self, store):
        store.upsert(
            "sections", "s1", [1.0, 0.0, 0.0, 0.0],
            {"node_id": "s1", "text_hash": "a", "level": 5},
        )
        payloads = store.indexed_payloads("sections")
        assert payloads["s1"]["text_hash"] == "a"
        assert payloads["s1"]["level"] == 5

    def test_empty_search(self, store):
        assert store.search("sections", [1.0, 0.0, 0.0, 0.0]) == []
