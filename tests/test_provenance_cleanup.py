"""Tests for provenance retention cleanup (Issue #13 V2.7).

Policy: delete provenance records that exceed the retention age OR the
maximum retained count; newest records always survive. Only persisted
``AnswerResult`` provenance records (JSON with a ``provenance_id``) are ever
considered, so processed/hierarchy/canonical/evaluation/embedding artifacts are
never touched. Cleanup is idempotent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.llm.provenance import ProvenanceStore, cleanup_provenance

START = 1_800_000_000.0
DAY = 86_400


def _write_provenance(directory: Path, pid: str, age_days: float) -> Path:
    """Write a persisted provenance record with a fixed mtime."""
    path = directory / f"{pid}.json"
    record = {
        "provenance_id": pid,
        "query": f"query-{pid}",
        "answer": "answer",
        "model": "mock",
        "duration_ms": 1.0,
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    stamp = START - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def _write_non_provenance(path: Path, content: dict) -> None:
    """Write a JSON artifact that is *not* a provenance record."""
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    stamp = START - 60 * DAY
    os.utime(path, (stamp, stamp))


def test_retention_by_age(tmp_path: Path) -> None:
    fresh = [_write_provenance(tmp_path, "f1", 1.0), _write_provenance(tmp_path, "f2", 5.0)]
    stale = [_write_provenance(tmp_path, "s1", 40.0), _write_provenance(tmp_path, "s2", 45.0)]

    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=0,
        enabled=True,
        now=START,
    )

    assert result.removed == 2
    assert result.remaining == 2
    assert all(p.exists() for p in fresh)
    assert not any(p.exists() for p in stale)


def test_retention_by_count(tmp_path: Path) -> None:
    newest = [_write_provenance(tmp_path, "n1", 1.0), _write_provenance(tmp_path, "n2", 2.0)]
    oldest = [_write_provenance(tmp_path, "o1", 10.0), _write_provenance(tmp_path, "o2", 11.0)]

    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=0,
        max_files=2,
        enabled=True,
        now=START,
    )

    assert result.removed == 2
    assert result.remaining == 2
    assert all(p.exists() for p in newest)
    assert not any(p.exists() for p in oldest)


def test_mixed_old_and_new(tmp_path: Path) -> None:
    keep = [_write_provenance(tmp_path, "k1", 1.0), _write_provenance(tmp_path, "k2", 5.0)]
    _write_provenance(tmp_path, "d1", 40.0)
    _write_provenance(tmp_path, "d2", 45.0)
    _write_provenance(tmp_path, "d3", 48.0)
    _write_provenance(tmp_path, "d4", 50.0)

    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=3,
        enabled=True,
        now=START,
    )

    assert result.removed == 3
    assert result.remaining == 3
    assert all(p.exists() for p in keep)
    assert (tmp_path / "d4.json").exists() is False
    assert (tmp_path / "d2.json").exists() is False
    assert (tmp_path / "d3.json").exists() is False


def test_disabled_cleanup(tmp_path: Path) -> None:
    records = [_write_provenance(tmp_path, "r1", 1.0), _write_provenance(tmp_path, "r2", 45.0)]

    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=0,
        enabled=False,
        now=START,
    )

    assert result.removed == 0
    assert result.remaining == 2
    assert all(p.exists() for p in records)


def test_canonical_hierarchy_eval_artifacts_untouched(tmp_path: Path) -> None:
    fresh = _write_provenance(tmp_path, "a1", 1.0)
    stale = _write_provenance(tmp_path, "a2", 40.0)
    canonical = tmp_path / "0d1934142f67c5f5.json"
    hierarchy = tmp_path / "cf20a14c52127fd5.json"
    eval_output = tmp_path / "evaluation_batch_42.json"
    _write_non_provenance(
        canonical, {"document_id": "0d1934142f67c5f5", "root_id": "r", "nodes": []}
    )
    _write_non_provenance(hierarchy, {"document_id": "cf20a14c52127fd5", "nodes": []})
    _write_non_provenance(eval_output, {"document_id": "0d1934142f67c5f5", "ground_truth": []})

    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=1,
        enabled=True,
        now=START,
    )

    assert result.removed == 1
    assert result.remaining == 1
    assert fresh.exists()
    assert not stale.exists()
    assert canonical.exists()
    assert hierarchy.exists()
    assert eval_output.exists()
    assert canonical.read_text(encoding="utf-8").startswith('{"document_id": "0d1934142f67c5f5"')


def test_non_provenance_files_never_deleted(tmp_path: Path) -> None:
    record = _write_provenance(tmp_path, "p1", 50.0)
    random_json = tmp_path / "random.json"
    corrupt_json = tmp_path / "corrupt.json"
    random_txt = tmp_path / "notes.txt"
    random_json.write_text('{"foo": "bar"}', encoding="utf-8")
    corrupt_json.write_text("{ not valid json !!!", encoding="utf-8")
    random_txt.write_text("hello", encoding="utf-8")
    for p in (random_json, corrupt_json, random_txt):
        stamp = START - 60 * DAY
        os.utime(p, (stamp, stamp))

    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=0,
        enabled=True,
        now=START,
    )

    assert result.removed == 1
    assert result.remaining == 0
    assert not record.exists()
    assert random_json.exists()
    assert corrupt_json.exists()
    assert random_txt.exists()


def test_only_own_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    other = tmp_path / "other"
    target.mkdir()
    other.mkdir()
    stale_target = _write_provenance(target, "t1", 50.0)
    fresh_target = _write_provenance(target, "t2", 1.0)
    stale_other = _write_provenance(other, "o1", 50.0)

    result = cleanup_provenance(
        directory=target,
        retention_days=30,
        max_files=0,
        enabled=True,
        now=START,
    )

    assert result.removed == 1
    assert not stale_target.exists()
    assert fresh_target.exists()
    assert stale_other.exists()


def test_idempotent_rerun(tmp_path: Path) -> None:
    _write_provenance(tmp_path, "a", 1.0)
    _write_provenance(tmp_path, "b", 5.0)
    _write_provenance(tmp_path, "c", 40.0)
    _write_provenance(tmp_path, "d", 48.0)

    first = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=2,
        enabled=True,
        now=START,
    )
    second = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=2,
        enabled=True,
        now=START,
    )

    assert first.removed == 2
    assert first.remaining == 2
    assert second.removed == 0
    assert second.remaining == 2


def test_dry_run_removes_nothing(tmp_path: Path) -> None:
    stale = _write_provenance(tmp_path, "s1", 50.0)
    fresh = _write_provenance(tmp_path, "f1", 1.0)

    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=0,
        enabled=True,
        now=START,
        dry_run=True,
    )

    assert result.removed == 1
    assert result.dry_run is True
    assert stale.exists()
    assert fresh.exists()


def test_empty_directory(tmp_path: Path) -> None:
    result = cleanup_provenance(
        directory=tmp_path,
        retention_days=30,
        max_files=1,
        enabled=True,
        now=START,
    )
    assert result.removed == 0
    assert result.remaining == 0


def test_store_without_directory() -> None:
    result = ProvenanceStore().cleanup(
        retention_days=30,
        max_files=1,
        enabled=True,
        now=START,
    )
    assert result.removed == 0
    assert result.remaining == 0
