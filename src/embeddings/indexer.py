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
            vectors = self.service.embed_documents(texts_by_batch[collection])
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

    def _graph_nodes(
        self,
        node_ids: list[str] | None,
        canonical_doc_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if node_ids is not None:
            nodes = []
            for nid in node_ids:
                node = self.graph.get_node(nid)
                if node:
                    nodes.append(node)
        else:
            nodes = [n for n in self.graph.all_nodes() if n.get("node_id")]
        if canonical_doc_ids is not None:
            nodes = [n for n in nodes if n.get("document_id") in canonical_doc_ids]
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
            # Task 24: each node carries its own source document. Deriving the
            # payload ``doc_id`` from the node's ``document_id`` (falling back to
            # the caller-supplied doc_id only when the node lacks one) is what
            # lets the dense ``document_id`` filter keep ICA and IPC apart.
            node_doc_id = node.get("document_id") or doc_id
            payload = _build_payload(node, collection, node_doc_id, language, str(label).lower())
            batches.setdefault(collection, []).append(payload)

        totals: dict[str, int] = {}
        for collection, payloads in batches.items():
            vectors = self.service.embed_documents([node_text(p) for p in payloads])
            items = [
                {"node_id": p["node_id"], "vector": vec, "payload": p}
                for p, vec in zip(payloads, vectors)
            ]
            totals[collection] = self.store.upsert_batch(collection, items)
        return totals

    def index_graph(
        self,
        node_ids: list[str] | None = None,
        canonical_doc_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """Embed all (or selected) hierarchy nodes from the graph store.

        ``canonical_doc_ids`` restricts embedding to nodes belonging to the given
        canonical documents, so only canonical nodes land in Qdrant.
        """
        doc_id = ""
        doc = next((n for n in self.graph.all_nodes() if n.get("label") == "Document"), None)
        if doc:
            doc_id = doc.get("document_id", doc["node_id"])
        language = self._doc_language()
        totals = self._index_nodes(self._graph_nodes(node_ids, canonical_doc_ids), doc_id, language)
        log.info("index.graph_complete", doc_id=doc_id, collections=totals)
        return {"doc_id": doc_id, "collections": totals}

    # -- incremental ------------------------------------------------------

    def index_incremental(self, node_ids: list[str] | None = None) -> dict[str, Any]:
        """Re-embed only new or text-changed nodes; skip already-fresh ones."""
        doc = next((n for n in self.graph.all_nodes() if n.get("label") == "Document"), None)
        doc_id = doc.get("document_id", doc["node_id"]) if doc else ""
        language = self._doc_language()

        existing: dict[str, dict[str, Any]] = {}
        for collection in self.store.collections:
            existing[collection] = self.store.indexed_payloads(collection)

        to_embed: list[tuple[str, dict[str, Any]]] = []
        skipped = 0
        inserted = 0
        updated = 0
        collections_inserted: dict[str, int] = {}
        collections_updated: dict[str, int] = {}
        for node in self._graph_nodes(node_ids):
            label = node.get("label", "")
            collection = collection_for_label(label)
            if collection is None:
                continue
            node_doc_id = node.get("document_id") or doc_id
            payload = _build_payload(node, collection, node_doc_id, language, str(label).lower())
            current = existing[collection].get(node["node_id"])
            if current is not None and current.get("text_hash") == payload["text_hash"]:
                skipped += 1
                continue
            if current is None:
                inserted += 1
                collections_inserted[collection] = collections_inserted.get(collection, 0) + 1
            else:
                updated += 1
                collections_updated[collection] = collections_updated.get(collection, 0) + 1
            to_embed.append((collection, payload))

        batches: dict[str, list[dict[str, Any]]] = {}
        for collection, payload in to_embed:
            batches.setdefault(collection, []).append(payload)

        totals: dict[str, int] = {}
        for collection, payloads in batches.items():
            vectors = self.service.embed_documents([node_text(p) for p in payloads])
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
        return {
            "indexed": sum(totals.values()),
            "skipped": skipped,
            "inserted": inserted,
            "updated": updated,
            "collections": totals,
            "collections_inserted": collections_inserted,
            "collections_updated": collections_updated,
        }

    def sync_graph(
        self, node_ids: list[str] | None = None, *, recreate_on_dimension_mismatch: bool = False
    ) -> dict[str, Any]:
        """Incremental sync: index new/changed nodes and delete stale points.

        Stale = nodes indexed in Qdrant but no longer present in the graph.
        When ``recreate_on_dimension_mismatch`` is enabled, any collection whose
        stored vector size differs from the provider dimension is recreated
        exactly once before syncing (a hard requirement: mismatched dimensions
        cannot be upserted into). Idempotent — a repeat run reports zero
        inserts, updates, and deletes.
        """
        recreated = 0
        if recreate_on_dimension_mismatch:
            for collection in self.store.collections:
                stored_dim = self.store.collection_dimension(collection)
                if stored_dim is not None and stored_dim != self.store.dim:
                    reason = f"stored dimension {stored_dim} != expected {self.store.dim}"
                    log.info(
                        "vector.sync.recreate",
                        collection=collection,
                        stored_dim=stored_dim,
                        expected_dim=self.store.dim,
                        reason=reason,
                    )
                    print(
                        "vector.sync.recreate "
                        f"collection={collection} stored_dim={stored_dim} "
                        f"expected_dim={self.store.dim} reason=dimension changed"
                    )
                    self.store.recreate_collection(collection)
                    recreated += 1

        nodes = self._graph_nodes(node_ids)
        log.info(
            "vector.sync.start",
            nodes=len(nodes),
            collections=self.store.collections,
            recreate_on_dimension_mismatch=recreate_on_dimension_mismatch,
        )
        print(f"vector.sync.start nodes={len(nodes)} collections={self.store.collections}")

        incremental = self.index_incremental(node_ids)

        for collection, count in incremental.get("collections_inserted", {}).items():
            if not count:
                continue
            log.info("vector.sync.insert", collection=collection, count=count)
            print(f"vector.sync.insert collection={collection} count={count}")
        for collection, count in incremental.get("collections_updated", {}).items():
            if not count:
                continue
            log.info("vector.sync.update", collection=collection, count=count)
            print(f"vector.sync.update collection={collection} count={count}")

        current = {n["node_id"] for n in nodes}
        deleted = 0
        for collection in self.store.collections:
            indexed = self.store.indexed_ids(collection)
            stale = indexed - current
            if stale:
                count = self.store.delete(collection, list(stale))
                deleted += count
                log.info("vector.sync.delete", collection=collection, count=count)
                print(f"vector.sync.delete collection={collection} count={count}")

        skipped = incremental.get("skipped", 0)
        result = {
            "inserted": incremental.get("inserted", 0),
            "updated": incremental.get("updated", 0),
            "deleted": deleted,
            "unchanged": skipped,
            "recreated": recreated,
            "indexed": incremental.get("indexed", 0),
            "skipped": skipped,
            "collections": incremental.get("collections", {}),
        }
        log.info(
            "vector.sync.complete",
            inserted=result["inserted"],
            updated=result["updated"],
            deleted=deleted,
            unchanged=skipped,
            recreated=recreated,
        )
        print(
            "vector.sync.complete "
            f"inserted={result['inserted']} updated={result['updated']} deleted={deleted} "
            f"unchanged={skipped} recreated={recreated}"
        )
        return result
