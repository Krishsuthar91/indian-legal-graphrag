"""Indexing pipeline — embeds hierarchy nodes and stores vectors in Qdrant.

Supports full indexing from hierarchy JSON or from a graph store, plus
incremental indexing that re-embeds only new or changed nodes (detected via a
text hash stored in the point payload).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger
from src.embeddings.models import collection_for, collection_for_label
from src.embeddings.service import EmbeddingService
from src.embeddings.store import QdrantStore

log = get_logger("indexer")

_DEFAULT_LANGUAGE = "unknown"


def node_text(node: dict[str, Any]) -> str:
    """Text used for embedding: title plus body text."""
    parts = [node.get("title", ""), node.get("text", "")]
    return " ".join(p for p in parts if p).strip()


def text_hash(node: dict[str, Any]) -> str:
    """Stable hash of the embeddable text (for incremental change detection)."""
    return hashlib.md5(node_text(node).encode("utf-8")).hexdigest()


def _build_payload(
    node: dict[str, Any],
    collection: str,
    doc_id: str,
    language: str,
    node_type: str,
) -> dict[str, Any]:
    return {
        "node_id": node["node_id"],
        "collection": collection,
        "doc_id": doc_id,
        "node_type": node_type,
        "language": language,
        "level": node.get("level", node.get("hierarchy_level", 0)),
        "numbering": node.get("numbering", ""),
        "title": node.get("title", ""),
        "text": node.get("text", ""),
        "text_hash": text_hash(node),
    }


class HierarchyIndexer:
    """Embeds hierarchy nodes and maintains vector collections."""

    def __init__(self, graph, store: QdrantStore, service: EmbeddingService) -> None:
        self.graph = graph
        self.store = store
        self.service = service

    # -- full indexing from hierarchy JSON --------------------------------

    def index_hierarchy_file(self, path: Path) -> dict[str, Any]:
        """Embed every node in a hierarchy JSON file into its collection."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        doc_id = data["document_id"]
        language = data.get("language", _DEFAULT_LANGUAGE)
        nodes = data.get("nodes", [])

        batches: dict[str, list[dict[str, Any]]] = {c: [] for c in self.store.collections}
        texts_by_batch: dict[str, list[str]] = {c: [] for c in self.store.collections}

        for node in nodes:
            node_type = node.get("node_type", "section")
            collection = collection_for(node_type)
            payload = _build_payload(node, collection, doc_id, language, node_type)
            batches[collection].append(payload)
            texts_by_batch[collection].append(node_text(node))

        totals: dict[str, int] = {}
        for collection in self.store.collections:
            if not batches[collection]:
                continue
            vectors = self.service.embed(texts_by_batch[collection])
            items = [
                {"node_id": p["node_id"], "vector": vec, "payload": p}
                for p, vec in zip(batches[collection], vectors)
            ]
            totals[collection] = self.store.upsert_batch(collection, items)

        log.info(
            "index.hierarchy_complete",
            doc_id=doc_id,
            collections=totals,
        )
        return {"doc_id": doc_id, "collections": totals}

    # -- indexing from graph ---------------------------------------------

    def _graph_nodes(self, node_ids: list[str] | None) -> list[dict[str, Any]]:
        if node_ids is None:
            return [n for n in self.graph.all_nodes() if n.get("node_id")]
        nodes = []
        for nid in node_ids:
            node = self.graph.get_node(nid)
            if node:
                nodes.append(node)
        return nodes

    def _doc_language(self) -> str:
        for node in self.graph.all_nodes():
            if node.get("label") == "Document":
                return node.get("language", _DEFAULT_LANGUAGE)
        return _DEFAULT_LANGUAGE

    def _index_nodes(
        self, nodes: list[dict[str, Any]], doc_id: str, language: str
    ) -> dict[str, Any]:
        batches: dict[str, list[dict[str, Any]]] = {}
        for node in nodes:
            label = node.get("label", "")
            collection = collection_for_label(label)
            if collection is None:
                continue
            payload = _build_payload(node, collection, doc_id, language, str(label).lower())
            batches.setdefault(collection, []).append(payload)

        totals: dict[str, int] = {}
        for collection, payloads in batches.items():
            vectors = self.service.embed([node_text(p) for p in payloads])
            items = [
                {"node_id": p["node_id"], "vector": vec, "payload": p}
                for p, vec in zip(payloads, vectors)
            ]
            totals[collection] = self.store.upsert_batch(collection, items)
        return totals

    def index_graph(self, node_ids: list[str] | None = None) -> dict[str, Any]:
        """Embed all (or selected) hierarchy nodes from the graph store."""
        doc_id = ""
        doc = next(
            (n for n in self.graph.all_nodes() if n.get("label") == "Document"), None
        )
        if doc:
            doc_id = doc.get("document_id", doc["node_id"])
        language = self._doc_language()
        totals = self._index_nodes(self._graph_nodes(node_ids), doc_id, language)
        log.info("index.graph_complete", doc_id=doc_id, collections=totals)
        return {"doc_id": doc_id, "collections": totals}

    # -- incremental ------------------------------------------------------

    def index_incremental(self, node_ids: list[str] | None = None) -> dict[str, Any]:
        """Re-embed only new or text-changed nodes; skip already-fresh ones."""
        doc = next(
            (n for n in self.graph.all_nodes() if n.get("label") == "Document"), None
        )
        doc_id = doc.get("document_id", doc["node_id"]) if doc else ""
        language = self._doc_language()

        existing: dict[str, dict[str, Any]] = {}
        for collection in self.store.collections:
            existing[collection] = self.store.indexed_payloads(collection)

        to_embed: list[tuple[str, dict[str, Any]]] = []
        skipped = 0
        for node in self._graph_nodes(node_ids):
            label = node.get("label", "")
            collection = collection_for_label(label)
            if collection is None:
                continue
            payload = _build_payload(node, collection, doc_id, language, str(label).lower())
            current = existing[collection].get(node["node_id"])
            if current is not None and current.get("text_hash") == payload["text_hash"]:
                skipped += 1
                continue
            to_embed.append((collection, payload))

        batches: dict[str, list[dict[str, Any]]] = {}
        for collection, payload in to_embed:
            batches.setdefault(collection, []).append(payload)

        totals: dict[str, int] = {}
        for collection, payloads in batches.items():
            vectors = self.service.embed([node_text(p) for p in payloads])
            items = [
                {"node_id": p["node_id"], "vector": vec, "payload": p}
                for p, vec in zip(payloads, vectors)
            ]
            totals[collection] = self.store.upsert_batch(collection, items)

        log.info(
            "index.incremental_complete",
            doc_id=doc_id,
            indexed=sum(totals.values()),
            skipped=skipped,
        )
        return {"indexed": sum(totals.values()), "skipped": skipped, "collections": totals}

    def sync_graph(self, node_ids: list[str] | None = None) -> dict[str, Any]:
        """Incremental sync: index new/changed nodes and delete stale points.

        Stale = nodes indexed in Qdrant but no longer present in the graph.
        """
        result = self.index_incremental(node_ids)

        current = {n["node_id"] for n in self._graph_nodes(node_ids)}
        stale_count = 0
        for collection in self.store.collections:
            indexed = self.store.indexed_ids(collection)
            stale = indexed - current
            if stale:
                stale_count += self.store.delete(collection, list(stale))
        result["deleted"] = stale_count
        log.info("index.sync_complete", **result)
        return result
