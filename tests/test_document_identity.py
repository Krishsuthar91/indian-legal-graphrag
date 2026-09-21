"""Issue #13 V2.5 — content-based document identity tests.

Verifies that document ids are a pure function of file content bytes:
identical documents uploaded from different filenames or directories share
one document_id (no duplicate artifacts), modified content produces a new
id, and the bundled canonical Acts keep their established ids.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.ingestion.identity import (
    CANONICAL_CONTENT_IDS,
    DOCUMENT_ID_LENGTH,
    content_document_id,
    resolve_document_id,
)
from src.ingestion.pipeline import ingest_document

ICA_CANONICAL_ID = "0d1934142f67c5f5"
IPC_CANONICAL_ID = "cf20a14c52127fd5"

BUNDLED_SOURCES = [
    "data/uploads/6f1e824b1f2b4fef9ee00a65adff9045_the-indian-contract-act-1872.pdf",
    "data/uploads/8d5f35578cd44e95a72011bb5ea285fd_ipc.pdf",
]


@pytest.fixture()
def isolated_output(tmp_path, monkeypatch):
    """Redirect the ingestion output dir into a temp directory."""
    out = tmp_path / "processed"
    monkeypatch.setattr("src.ingestion.pipeline.OUTPUT_DIR", out)
    return out


def _write_txt(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestContentDocumentId:
    def test_returns_truncated_sha256(self):
        data = b"content addressed identity"
        assert content_document_id(data) == hashlib.sha256(data).hexdigest()[:DOCUMENT_ID_LENGTH]

    def test_length_matches_project_standard(self):
        assert len(content_document_id(b"x")) == 16

    def test_same_bytes_same_id(self):
        assert content_document_id(b"abc") == content_document_id(b"abc")

    def test_different_bytes_different_id(self):
        assert content_document_id(b"abc") != content_document_id(b"abd")

    def test_resolve_defaults_to_content_id(self):
        assert resolve_document_id(b"arbitrary upload") == content_document_id(b"arbitrary upload")


class TestCanonicalBundledDocuments:
    def test_registry_maps_bundled_sources_to_canonical_ids(self):
        for src in BUNDLED_SOURCES:
            path = Path(src)
            if not path.exists():
                pytest.skip(f"bundled source missing: {src}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            expected = ICA_CANONICAL_ID if "contract-act" in src else IPC_CANONICAL_ID
            assert CANONICAL_CONTENT_IDS[digest] == expected

    def test_resolve_returns_canonical_id_for_bundled_bytes(self):
        for src in BUNDLED_SOURCES:
            path = Path(src)
            if not path.exists():
                pytest.skip(f"bundled source missing: {src}")
            expected = ICA_CANONICAL_ID if "contract-act" in src else IPC_CANONICAL_ID
            assert resolve_document_id(path.read_bytes()) == expected

    def test_canonical_id_independent_of_filename(self, tmp_path):
        src = Path(BUNDLED_SOURCES[0])
        if not src.exists():
            pytest.skip(f"bundled source missing: {src}")
        data = src.read_bytes()
        renamed = tmp_path / "renamed-contract-act.pdf"
        renamed.write_bytes(data)
        assert resolve_document_id(renamed.read_bytes()) == ICA_CANONICAL_ID


class TestIngestIdentity:
    def test_same_content_different_filename_same_id(self, tmp_path, isolated_output):
        dir_a, dir_b = tmp_path / "a", tmp_path / "b"
        dir_a.mkdir(), dir_b.mkdir()
        doc_a = ingest_document(_write_txt(dir_a / "doc.txt", "identical body"))
        doc_b = ingest_document(_write_txt(dir_b / "renamed.txt", "identical body"))
        assert doc_a.document_id == doc_b.document_id

    def test_same_content_different_directory_same_id(self, tmp_path, isolated_output):
        d1, d2 = tmp_path / "uploads", tmp_path / "imports"
        d1.mkdir(), d2.mkdir()
        doc_1 = ingest_document(_write_txt(d1 / "same.txt", "one corpus"))
        doc_2 = ingest_document(_write_txt(d2 / "same.txt", "one corpus"))
        assert doc_1.document_id == doc_2.document_id

    def test_modified_content_different_id(self, tmp_path, isolated_output):
        original = _write_txt(tmp_path / "before.txt", "section 10. agreements are contracts.")
        doc_before = ingest_document(original)
        modified = _write_txt(tmp_path / "after.txt", "section 999. a materially different clause")
        doc_after = ingest_document(modified)
        assert doc_before.document_id != doc_after.document_id

    def test_repeated_upload_does_not_create_new_artifact(self, tmp_path, isolated_output):
        for i in range(2):
            p = _write_txt(tmp_path / f"upload_{i}.txt", "re-uploaded identical document")
            doc = ingest_document(p)
            assert (isolated_output / f"{doc.document_id}.json").exists()
        files = list(isolated_output.glob("*.json"))
        assert len(files) == 1
