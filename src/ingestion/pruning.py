"""Prune stale duplicate artifacts during corpus rebuild (Issue #13 V2.6).

Historical documents were given path-derived identities, so identical uploads
produced many distinct processed/ and hierarchy/ artifacts.  A corpus rebuild
keeps loading every JSON file, including obsolete duplicates.  This module
removes duplicate artifacts while preserving exactly one canonical copy per
document and never deleting the bundled canonical Acts.

Duplicate definition
  * ``data/processed``: documents are duplicates when they share a
    ``document_id`` OR an identical content hash (SHA-256 of the joined page
    texts, in page order).
  * ``data/hierarchy``: files are duplicates when they represent the same
    ``document_id`` OR an identical content fingerprint (SHA-256 of the
    serialized node body).

Selection when duplicates differ (highest wins)
  1. valid JSON
  2. newest schema/format version
  3. highest completeness (page count for processed / node count for hierarchy)
  4. newest modification timestamp

Bundled canonical documents (``canonical._STABLE_CANONICAL_IDS``) always
survive.  The cleanup is idempotent: a second run over an already-pruned
directory removes nothing.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from src.config.logging_config import get_logger
from src.knowledge_graph.canonical import _STABLE_CANONICAL_IDS

log = get_logger("artifact.prune")

# Canonical bundled document ids that must never be deleted.
PROTECTED_DOCUMENT_IDS: frozenset[str] = frozenset(_STABLE_CANONICAL_IDS.values())


@dataclass
class ArtifactCandidate:
    """A single processed/hierarchy file eligible for duplicate analysis."""

    path: Path
    document_id: str
    content_hash: str | None
    valid: bool
    schema_version: int
    completeness: int
    mtime: float


@dataclass
class PruneRun:
    """Per-directory pruning outcome."""

    kind: str
    kept: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return len(self.removed)


@dataclass
class PruneResult:
    """Aggregate pruning outcome for processed + hierarchy directories."""

    processed: PruneRun = field(default_factory=lambda: PruneRun("processed"))
    hierarchy: PruneRun = field(default_factory=lambda: PruneRun("hierarchy"))

    @property
    def removed_processed(self) -> int:
        return self.processed.removed_count

    @property
    def removed_hierarchy(self) -> int:
        return self.hierarchy.removed_count

    def summary(self) -> dict:
        return {
            "removed_processed": self.removed_processed,
            "removed_hierarchy": self.removed_hierarchy,
        }


def _content_hash_processed(data: dict) -> str:
    """SHA-256 over the joined page texts (formfeed-separated, in order)."""
    pages = data.get("pages") or []
    text = "\f".join(str(p.get("text", "")) for p in pages)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _content_hash_hierarchy(data: dict) -> str:
    """SHA-256 over the deterministic node body, excluding the document_id."""
    nodes = data.get("nodes") or []
    rows = [
        {
            "node_type": n.get("node_type"),
            "title": n.get("title"),
            "text": n.get("text"),
            "numbering": n.get("numbering"),
            "start_page": n.get("start_page"),
            "end_page": n.get("end_page"),
        }
        for n in nodes
    ]
    raw = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_candidate(path: Path, kind: str) -> ArtifactCandidate:
    """Read a JSON artifact and build its candidate record.

    Files that fail to parse (or that are missing the expected structure) are
    marked invalid and grouped only by their filename stem, so a corrupt file
    can be discarded when a valid duplicate with the same document id exists
    but is never removed on its own.
    """
    mtime = path.stat().st_mtime
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ArtifactCandidate(
            path=path,
            document_id=path.stem,
            content_hash=None,
            valid=False,
            schema_version=0,
            completeness=0,
            mtime=mtime,
        )

    document_id = str(data.get("document_id") or path.stem)
    if kind == "processed":
        pages = data.get("pages")
        valid = isinstance(pages, list) and bool(document_id)
        completeness = len(pages) if isinstance(pages, list) else 0
        content_hash = _content_hash_processed(data) if valid else None
    else:
        nodes = data.get("nodes")
        valid = isinstance(nodes, list) and bool(document_id)
        completeness = len(nodes) if isinstance(nodes, list) else 0
        content_hash = _content_hash_hierarchy(data) if valid else None

    schema = data.get("schema_version") or data.get("format_version")
    try:
        schema_version = int(schema)
    except (TypeError, ValueError):
        schema_version = 0

    return ArtifactCandidate(
        path=path,
        document_id=document_id,
        content_hash=content_hash,
        valid=valid,
        schema_version=schema_version,
        completeness=completeness,
        mtime=mtime,
    )


def _find(parent: dict[str, str], x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: dict[str, str], a: str, b: str) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def _duplicate_groups(candidates: list[ArtifactCandidate]) -> list[list[ArtifactCandidate]]:
    """Group candidates that share a document_id OR an identical content hash.

    Transitive grouping (union-find) collapses files that are connected
    through either identity key.
    """
    parent: dict[str, str] = {}

    def node(key: str) -> str:
        if key not in parent:
            parent[key] = key
        return key

    for index, cand in enumerate(candidates):
        file_node = node(f"file:{index}")
        _union(parent, file_node, node(f"doc:{cand.document_id}"))
        if cand.content_hash is not None:
            _union(parent, file_node, node(f"hash:{cand.content_hash}"))

    groups: dict[str, list[ArtifactCandidate]] = defaultdict(list)
    for index, cand in enumerate(candidates):
        groups[_find(parent, f"file:{index}")].append(cand)
    return [sorted(group, key=lambda c: c.path) for group in groups.values()]


def _selection_key(cand: ArtifactCandidate) -> tuple:
    return (cand.valid, cand.schema_version, cand.completeness, cand.mtime)


def _select_survivor(group: list[ArtifactCandidate]) -> ArtifactCandidate:
    """Pick the canonical artifact to keep, honouring the protected ids."""
    protected = [c for c in group if c.document_id in PROTECTED_DOCUMENT_IDS]
    if protected:
        return max(protected, key=_selection_key)
    return max(group, key=_selection_key)


def _emit_keep(cand: ArtifactCandidate) -> None:
    print(f"artifact.prune.keep document_id={cand.document_id} path={cand.path}")
    log.info("artifact.prune.keep", document_id=cand.document_id, path=str(cand.path))


def _emit_remove(cand: ArtifactCandidate) -> None:
    print(f"artifact.prune.remove path={cand.path}")
    log.info("artifact.prune.remove", path=str(cand.path), document_id=cand.document_id)


def prune_directory(directory: Path, kind: str, dry_run: bool = False) -> PruneRun:
    """Remove duplicate artifacts from one data directory.

    ``kind`` is ``"processed"`` or ``"hierarchy"``.  Returns the outcome;
    when ``dry_run=True`` nothing is deleted but the outcome is still computed.
    """
    run = PruneRun(kind)
    json_paths = sorted(directory.glob("*.json"))
    candidates = [_read_candidate(path, kind) for path in json_paths]

    total = len(candidates)
    log.info("artifact.prune.start", kind=kind, directory=str(directory), files=total)

    for group in _duplicate_groups(candidates):
        if len(group) < 2:
            run.kept.append(group[0].path)
            continue
        survivor = _select_survivor(group)
        run.kept.append(survivor.path)
        _emit_keep(survivor)
        for candidate in group:
            if candidate.path == survivor.path:
                continue
            run.removed.append(candidate.path)
            _emit_remove(candidate)
            if not dry_run:
                try:
                    candidate.path.unlink(missing_ok=True)
                except OSError as exc:
                    log.warning(
                        "artifact.prune.unlink_failed",
                        path=str(candidate.path),
                        error=str(exc),
                    )
    return run


def prune_all(
    processed_dir: Path,
    hierarchy_dir: Path,
    dry_run: bool = False,
) -> PruneResult:
    """Prune duplicates from processed and hierarchy directories (idempotent)."""
    result = PruneResult()
    result.processed = prune_directory(processed_dir, "processed", dry_run=dry_run)
    result.hierarchy = prune_directory(hierarchy_dir, "hierarchy", dry_run=dry_run)
    print(
        "artifact.prune.complete "
        f"removed_processed={result.removed_processed} "
        f"removed_hierarchy={result.removed_hierarchy}"
    )
    log.info(
        "artifact.prune.complete",
        removed_processed=result.removed_processed,
        removed_hierarchy=result.removed_hierarchy,
    )
    return result
