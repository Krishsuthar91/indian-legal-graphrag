"""Tests for benchmark dataset loading and validation."""

import pytest

from src.evaluation.dataset import (
    DEFAULT_BENCHMARK_CSV,
    BenchmarkItem,
    difficulty_counts,
    load_benchmark_csv,
    query_type_counts,
)


def test_loads_50_questions():
    items = load_benchmark_csv(DEFAULT_BENCHMARK_CSV)
    assert len(items) == 50
    assert len({item.id for item in items}) == 50


def test_ids_are_sequential():
    items = load_benchmark_csv(DEFAULT_BENCHMARK_CSV)
    assert items[0].id == "ICA1872-001"
    assert [item.id for item in items] == [f"ICA1872-{i:03d}" for i in range(1, 51)]


def test_query_type_counts():
    items = load_benchmark_csv(DEFAULT_BENCHMARK_CSV)
    assert query_type_counts(items) == {
        "definition": 15,
        "section_lookup": 10,
        "comparison": 8,
        "procedure": 7,
        "explanation": 5,
        "scenario": 5,
    }


def test_difficulty_counts():
    items = load_benchmark_csv(DEFAULT_BENCHMARK_CSV)
    assert difficulty_counts(items) == {"Easy": 17, "Medium": 24, "Hard": 9}


def test_every_item_has_expected_sections_and_answer():
    for item in load_benchmark_csv(DEFAULT_BENCHMARK_CSV):
        assert item.expected_sections, item.id
        assert item.expected_answer
        assert item.question
        assert isinstance(item, BenchmarkItem)


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_benchmark_csv("does/not/exist.csv")


def test_duplicate_id_raises(tmp_path):
    path = tmp_path / "dup.csv"
    path.write_text(
        "ID,Question,Query_Type,Difficulty,Expected_Section,Expected_Keywords,Expected_Answer_Summary\n"
        "ICA1872-001,Q1,definition,Easy,S.1,k1,a1\n"
        "ICA1872-001,Q2,definition,Easy,S.1,k1,a1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_benchmark_csv(path)


def test_bad_query_type_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "ID,Question,Query_Type,Difficulty,Expected_Section,Expected_Keywords,Expected_Answer_Summary\n"
        "ICA1872-001,Q1,banana,Easy,S.1,k1,a1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown Query_Type"):
        load_benchmark_csv(path)
