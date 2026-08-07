"""Qdrant vector store wrapper.

Supports both an in-memory store (tests / offline) and a real Qdrant server.
Collections are created per hierarchy granularity (documents, chapters,
sections, clauses). Point IDs are deterministic UUIDs derived from node_id,
making upserts idempotent.
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.embeddings.models import DEFAULT_COLLECTIONS

log = get_logger("qdrant")

_NAMESPACE = uuid.UUID("00000000-0000-4000-8000-000000000001")

SCROLL_BATCH = 512


def point_id(node_id: str) -> str:
    """Deterministic UUID point id derived from a node_id."""
    return str(uuid.uuid5(_NAMESPACE, node_id))


class QdrantStore:
    """Thin wrapper around the Qdrant client with collection-aware helpers."""

    def __init__(
        self,
        dim: int,
        collections: list[str] | None = None,
        in_memory: bool = True,
        url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.dim = dim
        self.timeout = timeout if timeout is not None else settings.QDRANT_TIMEOUT_SECONDS
        self._collections = list(collections) if collections else list(DEFAULT_COLLECTIONS)
        if in_memory:
            log.info("qdrant.connect.start", mode="in-memory")
            self._client = QdrantClient(":memory:")
            log.info("qdrant.connect.complete", mode="in-memory", dim=dim)
        else:
            log.info(
                "qdrant.connect.start",
                mode="server",
                url=url or "http://localhost:6333",
                timeout=self.timeout,
            )
            self._client = QdrantClient(
                url=url or "http://localhost:6333",
                api_key=api_key,
                timeout=self.timeout,
            )
            log.info(
                "qdrant.connect.complete",
                mode="server",
                url=url,
                dim=dim,
                timeout=self.timeout,
            )

    @property
    def collections(self) -> list[str]:
        return list(self._collections)

    def ensure_collections(self) -> None:
        """Create configured collections if they do not exist."""
        log.info("qdrant.request_start", method="ensure_collections")
        try:
            for name in self._collections:
                if not self._client.collection_exists(name):
                    self._client.create_collection(
                        collection_name=name,
                        vectors_config=models.VectorParams(
                            size=self.dim,
                            distance=models.Distance.COSINE,
                        ),
                    )
                    log.info("qdrant.collection_created", collection=name, dim=self.dim)
        except Exception:
            log.exception("qdrant.request_failed", method="ensure_collections")
            raise
        log.info("qdrant.request_complete", method="ensure_collections")

    def collection_exists(self, name: str) -> bool:
        log.info("qdrant.request_start", method="collection_exists", collection=name)
        try:
            result = self._client.collection_exists(name)
        except Exception:
            log.exception("qdrant.request_failed", method="collection_exists", collection=name)
            raise
        log.info("qdrant.request_complete", method="collection_exists", collection=name)
        return result

    def delete_collection(self, name: str) -> None:
        log.info("qdrant.request_start", method="delete_collection", collection=name)
        try:
            if self._client.collection_exists(name):
                self._client.delete_collection(name)
                log.info("qdrant.collection_deleted", collection=name)
        except Exception:
            log.exception("qdrant.request_failed", method="delete_collection", collection=name)
            raise
        log.info("qdrant.request_complete", method="delete_collection", collection=name)

    def upsert(
        self, collection: str, node_id: str, vector: list[float], payload: dict[str, Any]
    ) -> None:
        """Insert or replace (idempotently) a single point."""
        log.info("qdrant.request_start", method="upsert", collection=collection, node_id=node_id)
        try:
            self._client.upsert(
                collection,
                points=[models.PointStruct(id=point_id(node_id), vector=vector, payload=payload)],
            )
        except Exception:
            log.exception(
                "qdrant.request_failed", method="upsert", collection=collection, node_id=node_id
            )
            raise
        log.info("qdrant.request_complete", method="upsert", collection=collection)

    def upsert_batch(self, collection: str, items: list[dict[str, Any]]) -> int:
        """Upsert a batch of {node_id, vector, payload} items. Returns count."""
        if not items:
            return 0
        log.info(
            "qdrant.request_start",
            method="upsert_batch",
            collection=collection,
            count=len(items),
        )
        try:
            points = [
                models.PointStruct(
                    id=point_id(item["node_id"]),
                    vector=item["vector"],
                    payload=item.get("payload", {}),
                )
                for item in items
            ]
            self._client.upsert(collection, points=points)
        except Exception:
            log.exception("qdrant.request_failed", method="upsert_batch", collection=collection)
            raise
        log.info("qdrant.request_complete", method="upsert_batch", collection=collection)
        return len(points)

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """Dense search in a single collection.

        Returns [{node_id, collection, score (cosine in [-1, 1]), payload}].
        """
        query_filter = None
        if language:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="language", match=models.MatchValue(value=language)
                    )
                ]
            )
        log.info(
            "qdrant.request_start",
            method="search",
            collection=collection,
            top_k=top_k,
            language=language,
        )
        try:
            result = self._client.query_points(
                collection,
                query=vector,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
                query_filter=query_filter,
            )
        except Exception:
            log.exception(
                "qdrant.request_failed", method="search", collection=collection, top_k=top_k
            )
            raise
        log.info(
            "qdrant.request_complete",
            method="search",
            collection=collection,
            hits=len(result.points),
        )
        hits = []
        for point in result.points:
            payload = dict(point.payload or {})
            hits.append(
                {
                    "node_id": payload.get("node_id", ""),
                    "collection": collection,
                    "score": float(point.score),
                    "payload": payload,
                }
            )
        return hits

    def search_multiple(
        self,
        collections: list[str],
        vector: list[float],
        top_k: int = 10,
        per_collection: int | None = None,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search several collections and aggregate the results.

        Each collection contributes ``per_collection`` hits (default top_k),
        then results are sorted by cosine score descending.
        """
        limit = per_collection or top_k
        aggregated: list[dict[str, Any]] = []
        for name in collections:
            aggregated.extend(self.search(name, vector, top_k=limit, language=language))
        aggregated.sort(key=lambda h: (-h["score"], h["node_id"]))
        return aggregated[:top_k]

    def delete(self, collection: str, node_ids: list[str]) -> int:
        if not node_ids:
            return 0
        log.info(
            "qdrant.request_start", method="delete", collection=collection, count=len(node_ids)
        )
        try:
            self._client.delete(
                collection,
                points_selector=models.PointIdsList(points=[point_id(n) for n in node_ids]),
            )
        except Exception:
            log.exception("qdrant.request_failed", method="delete", collection=collection)
            raise
        log.info("qdrant.request_complete", method="delete", collection=collection)
        return len(node_ids)

    def count(self, collection: str) -> int:
        log.info("qdrant.request_start", method="count", collection=collection)
        try:
            total = int(self._client.count(collection, exact=True).count)
        except Exception:
            log.exception("qdrant.request_failed", method="count", collection=collection)
            raise
        log.info("qdrant.request_complete", method="count", collection=collection, count=total)
        return total

    def indexed_ids(self, collection: str) -> set[str]:
        """All node_ids currently indexed in a collection (via scroll)."""
        return set(self.indexed_payloads(collection).keys())

    def indexed_payloads(self, collection: str) -> dict[str, dict[str, Any]]:
        """Return {node_id: payload} for all indexed points in a collection."""
        payloads: dict[str, dict[str, Any]] = {}
        offset = None
        log.info("qdrant.request_start", method="scroll", collection=collection)
        try:
            while True:
                points, offset = self._client.scroll(
                    collection,
                    limit=SCROLL_BATCH,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points:
                    payload = point.payload or {}
                    node_id = payload.get("node_id")
                    if node_id:
                        payloads[node_id] = dict(payload)
                if offset is None:
                    break
        except Exception:
            log.exception("qdrant.request_failed", method="scroll", collection=collection)
            raise
        log.info(
            "qdrant.request_complete",
            method="scroll",
            collection=collection,
            points=len(payloads),
        )
        return payloads

    def close(self) -> None:
        self._client.close()
