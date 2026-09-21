"""Canonical corpus selection — Task 18.

The ``data/hierarchy`` directory is polluted with many partial documents that
all represent the same Act (e.g. 180 files whose title normalises to the
Indian Contract Act). Each file carries a distinct ``document_id`` but often a
common *Act title*, so deduplication groups files by a normalised Act title and
keeps a single canonical file per Act.

Selection rules (in order) choose the canonical file for a group:

1. highest node count
2. highest section count
3. newest parser format (detected from content where available)
4. a document_id registered in ``_STABLE_CANONICAL_IDS`` (so duplicates that
   tie on all content-based keys resolve deterministically instead of by
   filesystem mtime)
5. newest file modification timestamp

All other files in the group are marked non-canonical and are skipped at import
time. Files are never deleted — only ignored during loading.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.config.logging_config import get_logger

log = get_logger("canonical_corpus")

# Stable, registered canonical document id per Act.  These match the ids the
# rest of the system resolves Act names to at query time (e.g.
# ``src/retrieval/query.py::_ACT_NAME_TO_DOC_ID``) and the evaluation defaults.
# When identical duplicate hierarchy files tie on node/section/parser counts,
# the registered id breaks the tie deterministically; mtime is only a
# content-independent fallback, never the deciding factor for registered Acts.
_STABLE_CANONICAL_IDS: dict[str, str] = {
    "indian contract act": "0d1934142f67c5f5",
    "indian penal code": "cf20a14c52127fd5",
}


@dataclass(frozen=True)
class AuditEntry:
    """Metadata describing a single hierarchy file for deduplication."""

    path: Path
    document_id: str
    title: str
    act_key: str
    node_count: int
    section_count: int
    parser_version: int
    mtime: float

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "document_id": self.document_id,
            "title": self.title,
            "act": self.act_key,
            "node_count": self.node_count,
            "section_count": self.section_count,
            "parser_version": self.parser_version,
            "mtime": self.mtime,
        }


@dataclass
class CanonicalSelection:
    """Result of running canonical selection over a hierarchy directory."""

    canonical: list[AuditEntry] = field(default_factory=list)
    skipped: list[AuditEntry] = field(default_factory=list)
    groups: dict[str, list[AuditEntry]] = field(default_factory=dict)

    @property
    def canonical_ids(self) -> set[str]:
        return {e.document_id for e in self.canonical}

    def summary(self) -> dict:
        total = len(self.canonical) + len(self.skipped)
        before_nodes = sum(e.node_count for e in self.canonical) + sum(
            e.node_count for e in self.skipped
        )
        after_nodes = sum(e.node_count for e in self.canonical)
        reduction = (1 - after_nodes / before_nodes) if before_nodes else 0.0
        return {
            "total_files": total,
            "canonical_files": len(self.canonical),
            "skipped_files": len(self.skipped),
            "file_reduction_pct": (1 - len(self.canonical) / total) * 100 if total else 0.0,
            "graph_nodes_before": before_nodes,
            "graph_nodes_after": after_nodes,
            "node_reduction_pct": reduction * 100,
        }


def normalize_act_title(title: str | None) -> str:
    """Normalise an Act title into a stable dedup key.

    Lowercases, strips a leading "the", removes a trailing year, and drops
    punctuation so that "THE INDIAN CONTRACT ACT, 1892", "The Indian Contract
    Act, 1872" and similar all collapse to "indian contract act".
    """
    if not title:
        return ""
    t = title.strip().lower()
    if t.startswith("the "):
        t = t[4:]
    t = re.sub(r"\d{4}$", "", t.strip())
    t = re.sub(r"[^a-z ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _parser_version(data: dict) -> int:
    """Detect the parser format version encoded in the file, if any.

    All current hierarchy files share one schema, so every file reports a
    baseline version unless a richer format marker is present.
    """
    schema = data.get("schema_version") or data.get("format_version")
    if isinstance(schema, (int, float)):
        return int(schema)
    return 1


def scan_hierarchy_files(hierarchy_dir: Path) -> list[AuditEntry]:
    """Read every hierarchy JSON and build one :class:`AuditEntry` per file."""
    entries: list[AuditEntry] = []
    for json_file in sorted(hierarchy_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("canonical.scan_error", file=str(json_file), error=str(exc))
            continue
        document_id = data.get("document_id", json_file.stem)
        root = next((n for n in data.get("nodes", []) if n.get("node_id") == "root"), {})
        title = root.get("title") or data.get("title") or document_id
        nodes = data.get("nodes", [])
        node_count = len(nodes)
        section_count = sum(1 for n in nodes if n.get("node_type") == "section")
        mtime = json_file.stat().st_mtime
        entries.append(
            AuditEntry(
                path=json_file,
                document_id=document_id,
                title=title,
                act_key=normalize_act_title(title),
                node_count=node_count,
                section_count=section_count,
                parser_version=_parser_version(data),
                mtime=mtime,
            )
        )
    return entries


def _select(entries: list[AuditEntry], act_key: str) -> list[AuditEntry]:
    """Pick the single canonical file for an Act group.

    Preference order: (node_count, section_count, parser_version) descending,
    then membership of ``document_id`` in ``_STABLE_CANONICAL_IDS`` for the
    group's Act, then mtime.  Content-based keys dominate, so a genuinely
    richer corpus still wins; the registered id only breaks ties between
    otherwise identical duplicates, keeping selection deterministic (both
    across machines and re-runs) instead of mtime-dependent.
    """
    if not entries:
        return []
    registered_id = _STABLE_CANONICAL_IDS.get(act_key)

    def key(e: AuditEntry) -> tuple:
        return (
            e.node_count,
            e.section_count,
            e.parser_version,
            int(e.document_id == registered_id) if registered_id else 0,
            e.mtime,
        )

    return [max(entries, key=key)]


def select_canonical(entries: list[AuditEntry]) -> CanonicalSelection:
    """Group files by Act and return the canonical per group plus the skipped."""
    groups: dict[str, list[AuditEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.act_key, []).append(entry)

    canonical: list[AuditEntry] = []
    skipped: list[AuditEntry] = []
    for act_key, group in groups.items():
        chosen = _select(group, act_key)
        chosen_ids = {e.document_id for e in chosen}
        canonical.extend(chosen)
        skipped.extend(e for e in group if e.document_id not in chosen_ids)

    return CanonicalSelection(canonical=canonical, skipped=skipped, groups=groups)


def canonical_files(hierarchy_dir: Path) -> list[Path]:
    """Return the canonical hierarchy files for the given directory."""
    selection = select_canonical(scan_hierarchy_files(hierarchy_dir))
    return [e.path for e in selection.canonical]


def canonical_doc_ids(hierarchy_dir: Path) -> set[str]:
    """Return the canonical document ids for the given directory."""
    return select_canonical(scan_hierarchy_files(hierarchy_dir)).canonical_ids


def build_corpus_audit(hierarchy_dir: Path) -> dict:
    """Full deterministic audit report (used by the dedup-report script)."""
    entries = scan_hierarchy_files(hierarchy_dir)
    selection = select_canonical(entries)
    return {
        "canonical_documents": [e.as_dict() for e in selection.canonical],
        "skipped_duplicates": [e.as_dict() for e in selection.skipped],
        "summary": selection.summary(),
        "groups": {key: [e.as_dict() for e in group] for key, group in selection.groups.items()},
    }
