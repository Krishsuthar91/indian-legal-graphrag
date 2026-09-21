"""Issue #13 V2.6 — stale duplicate artifact pruning tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.pruning import (
    PROTECTED_DOCUMENT_IDS,
    prune_all,
    prune_directory,
)

ICA = "0d1934142f67c5f5"
IPC = "cf20a14c52127fd5"


def _processed(doc_id: str, text: str) -> dict:
    return {
        "document_id": doc_id,
        "title": "Test Act",
        "language": "en",
        "pages": [{"page_number": 1, "text": text, "is_scanned": False}],
        "metadata": {
            "file_name": f"{doc_id}.txt",
            "file_type": "txt",
            "file_path": f"/tmp/{doc_id}.txt",
            "file_size_bytes": len(text),
            "num_pages": 1,
            "language": "en",
            "creation_date": None,
            "pdf_properties": None,
            "is_scanned": False,
            "ocr_applied": False,
        },
    }


def _hierarchy(doc_id: str, node_count: int = 4, schema: int | None = None) -> dict:
    nodes = [
        {
            "node_id": "root",
            "parent_id": None,
            "level": 0,
            "node_type": "document",
            "title": "Test",
            "text": "",
            "start_page": 1,
            "end_page": 1,
            "numbering": None,
            "children": [],
        }
    ]
    for i in range(1, node_count):
        nodes.append(
            {
                "node_id": f"n_{i:04d}",
                "parent_id": "root",
                "level": 1,
                "node_type": "section",
                "title": f"Section {i}",
                "text": f"body {i}",
                "start_page": 1,
                "end_page": 1,
                "numbering": str(i),
                "children": [],
            }
        )
    data = {
        "document_id": doc_id,
        "root_id": "root",
        "nodes": nodes,
        "nested_set": [],
        "warnings": [],
    }
    if schema is not None:
        data["schema_version"] = schema
    return data


def _write(directory: Path, name: str, data: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


class TestPruneProcessed:
    def test_duplicate_processed_removed(self, tmp_path: Path):
        d = tmp_path / "processed"
        d.mkdir()
        for i in (1, 2, 3):
            _write(d, f"doc{i}.json", _processed(f"id{i}", "identical content body"))

        run = prune_directory(d, "processed")

        assert run.removed_count == 2
        assert len(list(d.glob("*.json"))) == 1

    def test_duplicate_processed_by_document_id(self, tmp_path: Path):
        d = tmp_path / "processed"
        d.mkdir()
        _write(d, "a.json", _processed("dup", "version one"))
        _write(d, "b.json", _processed("dup", "version two"))

        run = prune_directory(d, "processed")

        assert run.removed_count == 1
        assert len(list(d.glob("*.json"))) == 1


class TestPruneHierarchy:
    def test_duplicate_hierarchy_same_document_id(self, tmp_path: Path):
        d = tmp_path / "hierarchy"
        d.mkdir()
        _write(d, "h1.json", _hierarchy("dup", 5))
        _write(d, "h2.json", _hierarchy("dup", 5))

        run = prune_directory(d, "hierarchy")

        assert run.removed_count == 1
        assert len(list(d.glob("*.json"))) == 1

    def test_duplicate_hierarchy_same_content(self, tmp_path: Path):
        d = tmp_path / "hierarchy"
        d.mkdir()
        _write(d, "h1.json", _hierarchy("doc-old", 5))
        _write(d, "h2.json", _hierarchy("doc-new", 5))

        run = prune_directory(d, "hierarchy")

        assert run.removed_count == 1
        assert len(list(d.glob("*.json"))) == 1


class TestCanonicalProtection:
    def test_canonical_processed_never_deleted(self, tmp_path: Path):
        d = tmp_path / "processed"
        d.mkdir()
        _write(d, f"{ICA}.json", _processed(ICA, "full act text"))
        _write(d, "x1.json", _processed("x1", "full act text"))
        _write(d, "x2.json", _processed("x2", "full act text"))

        run = prune_directory(d, "processed")

        assert (d / f"{ICA}.json").exists()
        assert run.removed_count == 2
        assert len(list(d.glob("*.json"))) == 1

    def test_canonical_ids_registered(self):
        assert PROTECTED_DOCUMENT_IDS == {ICA, IPC}

    def test_mixed_canonical_plus_duplicate_set(self, tmp_path: Path):
        d = tmp_path / "hierarchy"
        d.mkdir()
        canon = _write(d, f"{IPC}.json", _hierarchy(IPC, 7))
        _write(d, "ipc-dup.json", _hierarchy("ipc-dup", 7))
        _write(d, "ica.json", _hierarchy(ICA, 9))
        _write(d, "ica-dup.json", _hierarchy(ICA, 9))

        run = prune_directory(d, "hierarchy")

        assert run.removed_count == 2
        assert canon.exists()
        survivors = list(d.glob("*.json"))
        assert len(survivors) == 2
        survivor_ids = {json.loads(p.read_text(encoding="utf-8"))["document_id"] for p in survivors}
        assert survivor_ids == {IPC, ICA}


class TestCorruptionHandling:
    def test_corrupted_duplicate_discarded(self, tmp_path: Path):
        d = tmp_path / "processed"
        d.mkdir()
        valid = _write(d, "a.json", _processed("ccc", "good content"))
        corrupt = d / "ccc.json"
        corrupt.write_text("{ not valid json", encoding="utf-8")

        run = prune_directory(d, "processed")

        assert valid.exists()
        assert not corrupt.exists()
        assert run.removed_count == 1

    def test_corrupt_non_duplicate_survives(self, tmp_path: Path):
        d = tmp_path / "hierarchy"
        d.mkdir()
        p = d / "lone.json"
        p.write_text("{ invalid", encoding="utf-8")

        run = prune_directory(d, "hierarchy")

        assert p.exists()
        assert run.removed_count == 0


class TestIdempotency:
    def test_second_run_removes_nothing(self, tmp_path: Path):
        p = tmp_path / "processed"
        p.mkdir()
        h = tmp_path / "hierarchy"
        h.mkdir()
        for i in (1, 2, 3):
            _write(p, f"d{i}.json", _processed(f"id{i}", "same text here"))
            _write(h, f"h{i}.json", _hierarchy(f"hid{i}", 4))

        first = prune_all(p, h)
        assert first.removed_processed == 2
        assert first.removed_hierarchy == 2

        second = prune_all(p, h)
        assert second.removed_processed == 0
        assert second.removed_hierarchy == 0
        assert len(list(p.glob("*.json"))) == 1
        assert len(list(h.glob("*.json"))) == 1

    def test_dry_run_removes_nothing(self, tmp_path: Path):
        d = tmp_path / "processed"
        d.mkdir()
        _write(d, "d1.json", _processed("id1", "same text"))
        _write(d, "d2.json", _processed("id2", "same text"))

        run = prune_directory(d, "processed", dry_run=True)

        assert run.removed_count == 1
        assert len(list(d.glob("*.json"))) == 2

    def test_empty_directory_noop(self, tmp_path: Path):
        d = tmp_path / "processed"
        d.mkdir()

        run = prune_directory(d, "processed")

        assert run.removed_count == 0
        assert not list(d.glob("*.json"))
