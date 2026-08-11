"""Benchmark dataset loading (``data/eval/contract_act_1872_benchmark.csv``).

The research benchmark is a CSV with one row per question:

- ``ID``                  unique question id (``ICA1872-001`` .. ``ICA1872-050``)
- ``Question``            the natural-language legal question
- ``Query_Type``          definition | section_lookup | comparison |
                          procedure | explanation | scenario
- ``Difficulty``          Easy | Medium | Hard
- ``Expected_Section``    one or more section references, e.g. ``S.2(a)``
- ``Expected_Keywords``   comma-separated gold keywords
- ``Expected_Answer_Summary``  reference answer used by generation metrics
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.evaluation.sections import normalize_sections

QUERY_TYPES = ("definition", "section_lookup", "comparison", "procedure", "explanation", "scenario")
DIFFICULTIES = ("Easy", "Medium", "Hard")

DEFAULT_BENCHMARK_CSV = Path("data/eval/contract_act_1872_benchmark.csv")


@dataclass
class BenchmarkItem:
    """One benchmark question with its gold answer and expected sections."""

    id: str
    question: str
    query_type: str
    difficulty: str
    expected_section: str
    expected_keywords: str
    expected_answer: str
    expected_sections: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.expected_sections:
            self.expected_sections = normalize_sections(self.expected_section)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "question": self.question,
            "query_type": self.query_type,
            "difficulty": self.difficulty,
            "expected_section": self.expected_section,
            "expected_sections": list(self.expected_sections),
            "expected_keywords": self.expected_keywords,
            "expected_answer": self.expected_answer,
        }


def load_benchmark_csv(path: str | Path = DEFAULT_BENCHMARK_CSV) -> list[BenchmarkItem]:
    """Load and validate the benchmark CSV into a list of :class:`BenchmarkItem`.

    Raises ``ValueError`` on missing columns, duplicate ids, or unknown
    query-type / difficulty values.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"benchmark dataset not found: {path}")

    items: list[BenchmarkItem] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {
            "ID",
            "Question",
            "Query_Type",
            "Difficulty",
            "Expected_Section",
            "Expected_Keywords",
            "Expected_Answer_Summary",
        }
        if reader.fieldnames is None:
            raise ValueError(f"benchmark dataset has no header: {path}")
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"benchmark dataset missing columns: {sorted(missing)}")

        for row in reader:
            item_id = (row.get("ID") or "").strip()
            if not item_id:
                raise ValueError(f"benchmark row with empty ID in {path}")
            if item_id in seen_ids:
                raise ValueError(f"duplicate benchmark ID {item_id!r} in {path}")
            seen_ids.add(item_id)

            query_type = (row.get("Query_Type") or "").strip()
            difficulty = (row.get("Difficulty") or "").strip()
            if query_type not in QUERY_TYPES:
                raise ValueError(f"{item_id}: unknown Query_Type {query_type!r}")
            if difficulty not in DIFFICULTIES:
                raise ValueError(f"{item_id}: unknown Difficulty {difficulty!r}")

            items.append(
                BenchmarkItem(
                    id=item_id,
                    question=(row.get("Question") or "").strip(),
                    query_type=query_type,
                    difficulty=difficulty,
                    expected_section=(row.get("Expected_Section") or "").strip(),
                    expected_keywords=(row.get("Expected_Keywords") or "").strip(),
                    expected_answer=(row.get("Expected_Answer_Summary") or "").strip(),
                )
            )

    if not items:
        raise ValueError(f"benchmark dataset is empty: {path}")
    return items


def query_type_counts(items: list[BenchmarkItem]) -> dict[str, int]:
    """Count of questions per query type."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.query_type] = counts.get(item.query_type, 0) + 1
    return counts


def difficulty_counts(items: list[BenchmarkItem]) -> dict[str, int]:
    """Count of questions per difficulty band."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.difficulty] = counts.get(item.difficulty, 0) + 1
    return counts
