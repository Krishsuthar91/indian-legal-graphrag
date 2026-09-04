"""Corpus audit — inventory, duplicate detection, and cross-document contamination report.

Usage:
    python scripts/audit_corpus.py [--hierarchy-dir data/hierarchy] [--json OUTPUT.json]

The script reads all hierarchy JSON files, counts nodes per document, identifies
duplicate section numbers across documents, and reports partial/fragment files
that may cause retrieval confusion.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _load_hierarchy(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "document_id": data.get("document_id", ""),
        "language": data.get("language", "unknown"),
        "node_count": len(data.get("nodes", [])),
        "nodes": data.get("nodes", []),
    }


def audit(hierarchy_dir: Path) -> dict:
    files = sorted(hierarchy_dir.glob("*.json"))
    if not files:
        return {"error": f"No JSON files found in {hierarchy_dir}"}

    docs = []
    doc_ids: dict[str, list[str]] = {}
    section_numbers: dict[str, list[tuple[str, str, str]]] = {}
    node_type_counts: Counter = Counter()
    total_nodes = 0

    for f in files:
        doc = _load_hierarchy(f)
        docs.append(doc)
        did = doc["document_id"]
        doc_ids.setdefault(did, []).append(doc["path"])
        total_nodes += doc["node_count"]

        for node in doc["nodes"]:
            ntype = node.get("node_type", "unknown")
            node_type_counts[ntype] += 1
            num = node.get("numbering", "")
            if num and ntype == "section":
                section_numbers.setdefault(num, []).append(
                    (did, node.get("title", ""), doc["path"])
                )

    duplicates = {
        num: entries
        for num, entries in section_numbers.items()
        if len(set(e[0] for e in entries)) > 1
    }

    partial_docs = [
        {"document_id": did, "file_count": len(paths), "files": paths}
        for did, paths in doc_ids.items()
        if len(paths) > 1
    ]

    small_docs = [
        {"document_id": did, "node_count": doc["node_count"], "file": doc["path"]}
        for doc in docs
        if doc["node_count"] <= 15
    ]

    return {
        "total_files": len(files),
        "unique_document_ids": len(doc_ids),
        "total_nodes": total_nodes,
        "node_types": dict(node_type_counts),
        "section_number_duplicates": {
            "count": len(duplicates),
            "details": {
                num: [{"document_id": e[0], "title": e[1], "file": e[2]} for e in entries]
                for num, entries in sorted(duplicates.items())
            },
        },
        "multi_file_documents": partial_docs,
        "small_documents": small_docs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the hierarchy corpus.")
    parser.add_argument(
        "--hierarchy-dir", type=Path, default=Path("data/hierarchy"),
        help="Directory containing hierarchy JSON files",
    )
    parser.add_argument("--json", type=Path, default=None, help="Write JSON report")
    args = parser.parse_args()

    report = audit(args.hierarchy_dir)

    print("=== Corpus Audit Report ===")
    print(f"Total files:           {report['total_files']}")
    print(f"Unique document IDs:   {report['unique_document_ids']}")
    print(f"Total nodes:           {report['total_nodes']}")
    print(f"Node types:            {report['node_types']}")
    print()

    sec_dup = report["section_number_duplicates"]
    print(f"Cross-document section duplicates: {sec_dup['count']}")
    if sec_dup["count"] > 0:
        for num, entries in list(sec_dup["details"].items())[:5]:
            print(f"  Section {num}: {len(entries)} documents")
            for e in entries:
                print(f"    - {e['document_id']}: {e['title']}")
    print()

    print(f"Multi-file documents:  {len(report['multi_file_documents'])}")
    for d in report["multi_file_documents"][:5]:
        print(f"  {d['document_id']}: {d['file_count']} files")

    print(f"Small documents (<=15 nodes): {len(report['small_documents'])}")
    for d in report["small_documents"][:5]:
        print(f"  {d['document_id']}: {d['node_count']} nodes")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON report written to {args.json}")


if __name__ == "__main__":
    main()
