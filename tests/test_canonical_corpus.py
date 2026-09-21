"""Regression tests for canonical corpus deduplication (Task 18).

Verifies that only canonical hierarchy files are imported and indexed, duplicate
files are skipped, retrieval still works over the canonical corpus, and the
audit report is produced.
"""

import json
import os
from pathlib import Path

import pytest

from src.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingService,
    HierarchyIndexer,
    QdrantStore,
    VectorRetriever,
)
from src.knowledge_graph.canonical import (
    build_corpus_audit,
    canonical_doc_ids,
    normalize_act_title,
    scan_hierarchy_files,
    select_canonical,
)
from src.knowledge_graph.importer import import_all
from src.knowledge_graph.neo4j_driver import InMemoryGraph


def _hierarchy_json(document_id: str, title: str, section_count: int) -> dict:
    nodes = [
        {
            "node_id": "root",
            "parent_id": None,
            "level": 0,
            "node_type": "document",
            "title": title,
            "text": "",
            "start_page": 1,
            "end_page": 1,
            "numbering": "",
            "children": [f"s{i}" for i in range(section_count)],
        }
    ]
    for i in range(section_count):
        nodes.append(
            {
                "node_id": f"s{i + 1}",
                "parent_id": "root",
                "level": 5,
                "node_type": "section",
                "title": f"Section {i + 1}",
                "text": f"Text of section {i + 1} of {title}.",
                "start_page": 1,
                "end_page": 1,
                "numbering": str(i + 1),
                "children": [],
            }
        )
    return {
        "document_id": document_id,
        "root_id": "root",
        "language": "en",
        "nodes": nodes,
        "nested_set": [],
        "warnings": [],
    }


def _write(dir_: Path, document_id: str, title: str, section_count: int) -> Path:
    path = dir_ / f"{document_id}.json"
    path.write_text(
        json.dumps(_hierarchy_json(document_id, title, section_count)),
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    """A corpus with duplicate ICA files and one distinct Act."""
    d = tmp_path / "hierarchy"
    d.mkdir()
    # Canonical ICA — highest node count (n sections + root).
    _write(d, "canonical", "The Indian Contract Act, 1872", section_count=10)
    # Duplicate ICA fragments (same Act, fewer sections).
    _write(d, "dup1", "THE INDIAN CONTRACT ACT, 1892", section_count=2)
    _write(d, "dup2", "The Indian Contract Act, 1872", section_count=3)
    _write(d, "dup3", "the indian contract act, 1872", section_count=3)
    # A genuinely different Act stays canonical on its own.
    _write(d, "penal", "THE INDIAN PENAL CODE", section_count=4)
    return d


class TestNormalize:
    @pytest.mark.parametrize(
        "title",
        [
            "THE INDIAN CONTRACT ACT, 1892",
            "The Indian Contract Act, 1872",
            "the indian contract act, 1872",
        ],
    )
    def test_contract_act_variants_collapse(self, title):
        assert normalize_act_title(title) == "indian contract act"

    def test_distinct_acts_do_not_collapse(self):
        assert normalize_act_title("THE INDIAN PENAL CODE") == "indian penal code"
        assert normalize_act_title("THE INDIAN CONTRACT ACT, 1892") != (
            normalize_act_title("THE INDIAN PENAL CODE")
        )


class TestSelection:
    def test_prefers_highest_node_count(self, corpus):
        entries = scan_hierarchy_files(corpus)
        selection = select_canonical(entries)
        ica = [e for e in selection.canonical if e.act_key == "indian contract act"]
        assert len(ica) == 1
        assert ica[0].document_id == "canonical"
        assert ica[0].node_count == 11  # root + 10 sections

    def test_skipped_counts(self, corpus):
        selection = select_canonical(scan_hierarchy_files(corpus))
        assert len(selection.canonical) == 2
        assert len(selection.skipped) == 3
        assert {e.document_id for e in selection.skipped} == {
            "dup1",
            "dup2",
            "dup3",
        }


class TestStableRegistryTiebreak:
    """Canonical selection must not depend on file mtime for known Acts.

    Two byte-equivalent ICA duplicates tie on node/section/parser counts; the
    registered document id must win deterministically, not the newest file.
    """

    def test_registered_id_wins_identical_duplicates(self, tmp_path: Path):
        d = tmp_path / "h"
        d.mkdir()
        _write(d, "0d1934142f67c5f5", "The Indian Contract Act, 1872", section_count=3)
        _write(d, "0e178b31f7181a31", "The Indian Contract Act, 1872", section_count=3)
        imported = d / "0e178b31f7181a31.json"
        os.utime(imported, (2_000_000_000, 2_000_000_000))  # non-registered file is newer
        selection = select_canonical(scan_hierarchy_files(d))
        ica = [e for e in selection.canonical if e.act_key == "indian contract act"]
        assert len(ica) == 1
        assert ica[0].document_id == "0d1934142f67c5f5"

    def test_registered_id_wins_regardless_of_mtime_order(self, tmp_path: Path):
        d = tmp_path / "h"
        d.mkdir()
        _write(d, "0d1934142f67c5f5", "The Indian Contract Act, 1872", section_count=3)
        _write(d, "0e178b31f7181a31", "The Indian Contract Act, 1872", section_count=3)
        registered = d / "0d1934142f67c5f5.json"
        os.utime(registered, (2_000_000_000, 2_000_000_000))  # registered file is newer
        selection = select_canonical(scan_hierarchy_files(d))
        ica = [e for e in selection.canonical if e.act_key == "indian contract act"]
        assert len(ica) == 1
        assert ica[0].document_id == "0d1934142f67c5f5"

    def test_richer_corpus_still_wins_over_registered_id(self, tmp_path: Path):
        d = tmp_path / "h"
        d.mkdir()
        _write(d, "0d1934142f67c5f5", "The Indian Contract Act, 1872", section_count=2)
        _write(d, "0e178b31f7181a31", "The Indian Contract Act, 1872", section_count=10)
        selection = select_canonical(scan_hierarchy_files(d))
        ica = [e for e in selection.canonical if e.act_key == "indian contract act"]
        assert ica[0].document_id == "0e178b31f7181a31"


class TestImportAll:
    def test_only_one_ica_imported_and_duplicates_skipped(self, corpus):
        graph = InMemoryGraph()
        result = import_all(graph, corpus)
        assert result["files_scanned"] == 5
        assert result["files_imported"] == 2  # canonical ICA + penal
        assert result["files_skipped"] == 3

        doc_ids = [n.get("document_id") for n in graph.all_nodes() if n.get("label") == "Document"]
        doc_ids = [d for d in doc_ids if d]
        assert doc_ids == ["canonical", "penal"]
        # No duplicate document nodes leak in.
        assert "dup1" not in doc_ids
        assert "dup2" not in doc_ids

    def test_canonical_doc_ids_matches_imported(self, corpus):
        graph = InMemoryGraph()
        import_all(graph, corpus)
        imported = {
            n.get("document_id")
            for n in graph.all_nodes()
            if n.get("label") == "Document" and n.get("document_id")
        }
        assert imported == canonical_doc_ids(corpus)

    def test_all_single_act_dir_imports_one(self, tmp_path: Path):
        d = tmp_path / "h"
        d.mkdir()
        _write(d, "a", "The Indian Contract Act, 1872", section_count=5)
        _write(d, "b", "THE INDIAN CONTRACT ACT, 1892", section_count=1)
        graph = InMemoryGraph()
        result = import_all(graph, d)
        assert result["files_imported"] == 1
        assert result["files_skipped"] == 1


class TestRetrievalStillPasses:
    def test_retriever_works_over_canonical_corpus(self, corpus):
        graph = InMemoryGraph()
        import_all(graph, corpus)
        provider = DeterministicEmbeddingProvider(dim=32)
        service = EmbeddingService(provider=provider)
        store = QdrantStore(dim=32, in_memory=True)
        store.ensure_collections()
        HierarchyIndexer(graph, store, service).index_graph(
            canonical_doc_ids=canonical_doc_ids(corpus)
        )
        assert store.count("sections") >= 1
        retriever = VectorRetriever(graph, store, service)
        hits = retriever.hybrid_retrieve("Section 5", top_k=3)
        assert len(hits) > 0
        canon = canonical_doc_ids(corpus)
        for hit in hits:
            doc = hit.node_id.split("__")[0]
            assert doc in canon


class TestIndexCanonicalOnly:
    def test_qdrant_indexes_only_canonical_nodes(self, corpus):
        graph = InMemoryGraph()
        import_all(graph, corpus)
        provider = DeterministicEmbeddingProvider(dim=32)
        service = EmbeddingService(provider=provider)
        store = QdrantStore(dim=32, in_memory=True)
        store.ensure_collections()
        HierarchyIndexer(graph, store, service).index_graph(
            canonical_doc_ids=canonical_doc_ids(corpus)
        )
        payloads = store.indexed_payloads("sections")
        doc_ids = {p["node_id"].split("__")[0] for p in payloads.values()}
        assert doc_ids == {"canonical", "penal"}
        assert "dup1" not in doc_ids


class TestAuditReport:
    def test_audit_report_generated(self, corpus):
        audit = build_corpus_audit(corpus)
        summary = audit["summary"]
        assert summary["total_files"] == 5
        assert summary["canonical_files"] == 2
        assert summary["skipped_files"] == 3
        canon_ids = {e["document_id"] for e in audit["canonical_documents"]}
        assert canon_ids == {"canonical", "penal"}
        assert summary["file_reduction_pct"] == pytest.approx(60.0)
        assert summary["graph_nodes_after"] < summary["graph_nodes_before"]
