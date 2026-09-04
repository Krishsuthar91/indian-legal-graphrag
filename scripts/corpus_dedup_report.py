"""Canonical corpus deduplication report — Task 18.

Audits every hierarchy JSON in ``data/hierarchy``, groups files by normalised
Act title, selects a single canonical file per Act, and prints:

- canonical documents
- skipped duplicate documents
- node counts
- section counts
- reduction percentage (files, graph nodes)

This is read-only: it never deletes or modifies any hierarchy file.

Usage:
    python scripts/corpus_dedup_report.py [--output results/corpus_dedup_report.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.knowledge_graph.canonical import build_corpus_audit

DEFAULT_HIERARCHY = _REPO_ROOT / "data" / "hierarchy"


def _fmt(entry: dict) -> str:
    return (
        f"    {entry['document_id']}  nodes={entry['node_count']:>4}  "
        f"sections={entry['section_count']:>4}  {entry['title']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical corpus dedup report")
    parser.add_argument(
        "--hierarchy",
        type=Path,
        default=DEFAULT_HIERARCHY,
        help="Directory of hierarchy JSON files (default: data/hierarchy)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON file to write the full audit to",
    )
    args = parser.parse_args()

    audit = build_corpus_audit(args.hierarchy)
    summary = audit["summary"]

    print("=" * 72)
    print("CANONICAL CORPUS DEDUPLICATION REPORT")
    print("=" * 72)
    print(f"Hierarchy directory : {args.hierarchy}")
    print(f"Total hierarchy files: {summary['total_files']}")
    print(f"Canonical files     : {summary['canonical_files']}")
    print(f"Skipped duplicates  : {summary['skipped_files']}")
    print(f"File reduction      : {summary['file_reduction_pct']:.1f}%")
    print(f"Graph nodes before  : {summary['graph_nodes_before']}")
    print(f"Graph nodes after   : {summary['graph_nodes_after']}")
    print(f"Node reduction      : {summary['node_reduction_pct']:.1f}%")
    print()

    print("CANONICAL DOCUMENTS")
    print("-" * 72)
    for entry in audit["canonical_documents"]:
        print(_fmt(entry))
    print()

    print("SKIPPED DUPLICATES")
    print("-" * 72)
    for entry in audit["skipped_duplicates"]:
        print(_fmt(entry))
    print()

    for act, entries in sorted(audit["groups"].items()):
        print(f"Act group: {act!r} ({len(entries)} files)")
        canonical_id = next(
            (e["document_id"] for e in audit["canonical_documents"] if e["act"] == act),
            None,
        )
        print(f"   canonical: {canonical_id}, skipped: {len(entries) - 1}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nFull audit written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
