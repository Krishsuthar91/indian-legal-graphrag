"""Prune stale duplicate artifacts from the corpus data dirs (Issue #13 V2.6).

Duplicate processed documents (same document_id or identical content hash) and
duplicate hierarchy files (same document_id or identical content fingerprint)
are reduced to a single canonical artifact each.  Bundled canonical documents
are never deleted.  Idempotent: a second run removes nothing.

Usage:
    python scripts/prune_stale_artifacts.py [--processed-dir DIR]
                                            [--hierarchy-dir DIR]
                                            [--dry-run]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.hierarchy.parser import HIERARCHY_DIR
from src.ingestion.pipeline import OUTPUT_DIR
from src.ingestion.pruning import prune_all


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--processed-dir",
        default=str(OUTPUT_DIR),
        help="Directory containing processed document JSONs.",
    )
    parser.add_argument(
        "--hierarchy-dir",
        default=str(HIERARCHY_DIR),
        help="Directory containing hierarchy JSONs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without deleting anything.",
    )
    args = parser.parse_args()

    result = prune_all(
        Path(args.processed_dir),
        Path(args.hierarchy_dir),
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(
            "[dry-run] would remove "
            f"{result.removed_processed} processed, "
            f"{result.removed_hierarchy} hierarchy artifacts"
        )
    else:
        print(
            "prune.complete "
            f"removed_processed={result.removed_processed} "
            f"removed_hierarchy={result.removed_hierarchy}"
        )


if __name__ == "__main__":
    main()
