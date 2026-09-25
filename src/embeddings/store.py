"""Qdrant vector store wrapper.

Supports both an in-memory store (tests / offline) and a real Qdrant server.
Collections are created per hierarchy granularity (documents, chapters,
sections, clauses). Point IDs are deterministic UUIDs derived from node_id,
making upserts idempotent.
"""

from __future__ import annotations

import gc
import gzip
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.embeddings.models import DEFAULT_COLLECTIONS

log = get_logger("qdrant")

_NAMESPACE = uuid.UUID("00000000-0000-4000-8000-000000000001")

SCROLL_BATCH = 512

_SNAPSHOT_BASE = Path(__file__).resolve().parent.parent.parent


def _snapshot_path(key: str) -> Path:
    """Absolute snapshot file path for a cache key."""
    directory = Path(settings.EMBEDDING_SNAPSHOT_DIR)
    if not directory.is_absolute():
        directory = _SNAPSHOT_BASE / directory
    return directory / f"snapshot_{key}.json.gz"


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
        path: str | None = None,
    ) -> None:
        self.dim = dim
        self.timeout = timeout if timeout is not None else settings.QDRANT_TIMEOUT_SECONDS
        self._collections = list(collections) if collections else list(DEFAULT_COLLECTIONS)
        self._local_path: Path | None = None
        if in_memory:
            log.info("qdrant.connect.start", mode="in-memory")
            self._client = QdrantClient(":memory:")
            log.info("qdrant.connect.complete", mode="in-memory", dim=dim)
        elif path:
            # Embedded on-disk Qdrant (e.g. temporary persistent instances for
            # verification). Behaves exactly like a server-backed persistent
            # store but lives in a directory.
            self._local_path = Path(path)
            log.info("qdrant.connect.start", mode="local-persistent", path=str(path))
            self._client = QdrantClient(path=str(path))
            log.info(
                "qdrant.connect.complete",
                mode="local-persistent",
                path=str(path),
                dim=dim,
            )
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

    def collection_dimension(self, name: str) -> int | None:
        """Vector size configured on an existing collection, or None.

        Returns None when the collection does not exist or its vector config is
        ambiguous (e.g. named vectors with mixed sizes). Persisted collections
        always use a single ``VectorParams`` config, so in practice this is the
        stored dimension size.
        """
        log.info("qdrant.request_start", method="get_collection", collection=name)
        try:
            if not self._client.collection_exists(name):
                return None
            info = self._client.get_collection(name)
        except Exception:
            log.exception("qdrant.request_failed", method="get_collection", collection=name)
            raise
        log.info("qdrant.request_complete", method="get_collection", collection=name)
        vectors = info.config.params.vectors
        if isinstance(vectors, models.VectorParams):
            return vectors.size
        if isinstance(vectors, dict):
            sizes = {v.size for v in vectors.values() if isinstance(v, models.VectorParams)}
            return sizes.pop() if len(sizes) == 1 else None
        return None

    def recreate_collection(self, name: str) -> None:
        """Delete and recreate a collection with the current dimension.

        The locally-embedded ``QdrantClient(path=...)`` can resurrect a
        collection's data when it is deleted and re-created under the same name
        in one session: on Windows the client-side ``delete_collection`` rmtree
        can silently fail while the collection's sqlite handle is still open, so
        the on-disk data directory is removed explicitly before re-creating.
        This mirrors the true reset a server-backed collection undergoes.
        """
        if self._client.collection_exists(name):
            self.delete_collection(name)
        if self._local_path is not None:
            gc.collect()
            shutil.rmtree(
                self._local_path / "collection" / name,
                ignore_errors=True,
            )
        self._client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=self.dim,
                distance=models.Distance.COSINE,
            ),
        )
        log.info("qdrant.collection_recreated", collection=name, dim=self.dim)

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

    def save_snapshot(self, key: str) -> int:
        """Persist all indexed points (payload + vector) to a gzip JSON file.

        Used by the in-memory store so a subsequent startup can restore the
        computed vectors instead of re-embedding the whole corpus on CPU.
        Writes are atomic (temp file + rename). Returns the point count.
        """
        points: dict[str, dict[str, dict[str, Any]]] = {}
        vectors: dict[str, dict[str, list[float]]] = {}
        total = 0
        for name in self._collections:
            coll_points: dict[str, dict[str, Any]] = {}
            coll_vectors: dict[str, list[float]] = {}
            offset = None
            while True:
                page, offset = self._client.scroll(
                    name,
                    limit=SCROLL_BATCH,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )
                for point in page:
                    payload = dict(point.payload or {})
                    node_id = payload.get("node_id", "")
                    if not node_id:
                        continue
                    coll_points[node_id] = payload
                    vector = getattr(point, "vector", None)
                    coll_vectors[node_id] = [float(v) for v in vector]
                if offset is None:
                    break
            if coll_points:
                points[name] = coll_points
                vectors[name] = coll_vectors
                total += len(coll_points)

        path = _snapshot_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump({"key": key, "dim": self.dim, "points": points, "vectors": vectors}, fh)
        os.replace(tmp, path)
        log.info("qdrant.snapshot_saved", key=key, points=total, path=str(path))
        return total

    def load_snapshot(self, key: str) -> int:
        """Restore points/vectors from a saved snapshot, if any.

        Returns the number of points restored (0 when the cache key is stale,
        missing, or corrupt — callers then fall back to a full re-embed).
        """
        path = _snapshot_path(key)
        if not path.exists():
            return 0
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:  # pragma: no cover - corrupt/partial snapshot
            log.warning("qdrant.snapshot_unreadable", key=key, path=str(path))
            return 0
        if data.get("key") != key or int(data.get("dim", -1)) != self.dim:
            log.warning(
                "qdrant.snapshot_stale",
                key=key,
                dim=data.get("dim"),
                expected=self.dim,
            )
            return 0
        points = data.get("points", {})
        vectors = data.get("vectors", {})
        restored = 0
        for name, coll_points in points.items():
            coll_vectors = vectors.get(name, {})
            prepared = []
            for node_id, payload in coll_points.items():
                vector = coll_vectors.get(node_id)
                if not vector:
                    continue
                prepared.append(
                    models.PointStruct(id=point_id(node_id), vector=vector, payload=payload)
                )
            for start in range(0, len(prepared), SCROLL_BATCH):
                self._client.upsert(name, points=prepared[start : start + SCROLL_BATCH])
            restored += len(prepared)
        log.info("qdrant.snapshot_restored", key=key, points=restored, path=str(path))
        return restored

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        language: str | None = None,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Dense search in a single collection.

        Returns [{node_id, collection, score (cosine in [-1, 1]), payload}].

        ``document_id`` restricts results to points whose ``doc_id`` payload
        field matches exactly (case-sensitive).  When *None* the filter is
        skipped and all documents are searched.
        """
        conditions: list[models.FieldCondition] = []
        if language:
            conditions.append(
                models.FieldCondition(key="language", match=models.MatchValue(value=language))
            )
        if document_id:
            conditions.append(
                models.FieldCondition(key="doc_id", match=models.MatchValue(value=document_id))
            )
        query_filter = models.Filter(must=conditions) if conditions else None
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
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search several collections and aggregate the results.

        Each collection contributes ``per_collection`` hits (default top_k),
        then results are sorted by cosine score descending.

        ``document_id`` restricts results to points whose ``doc_id`` payload
        field matches exactly (case-sensitive).  When *None* the filter is
        skipped and all documents are searched.
        """
        limit = per_collection or top_k
        aggregated: list[dict[str, Any]] = []
        for name in collections:
            aggregated.extend(
                self.search(name, vector, top_k=limit, language=language, document_id=document_id)
            )
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
