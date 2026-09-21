"""Standalone provenance retention cleanup (Issue #13 V2.7).

Deletes provenance artifacts that exceed the retention age or the maximum
retained count. Only provenance records (JSON with a ``provenance_id``) in the
target directory are considered — processed, hierarchy, canonical, evaluation,
and embedding artifacts are never touched. Newest records are always kept.
Run with ``--dry-run`` to preview removals.
"""

import argparse

from src.config.settings import settings
from src.llm.provenance import cleanup_provenance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cleanup_provenance",
        description="Enforce provenance retention (Issue #13 V2.7).",
    )
    parser.add_argument(
        "--directory",
        default=settings.QA_PROVENANCE_DIR,
        help=f"Provenance directory (default: {settings.QA_PROVENANCE_DIR}).",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=settings.PROVENANCE_RETENTION_DAYS,
        help="Delete records older than this many days (0 disables this rule).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=settings.PROVENANCE_MAX_FILES,
        help="Always keep this many newest records (0 disables this rule).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without deleting anything.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = cleanup_provenance(
        directory=args.directory,
        retention_days=args.retention_days,
        max_files=args.max_files,
        enabled=settings.PROVENANCE_CLEANUP_ENABLED,
        dry_run=args.dry_run,
    )
    print(
        f"[cleanup done] removed={result.removed} remaining={result.remaining} "
        f"dry_run={result.dry_run}"
    )


if __name__ == "__main__":
    main()
