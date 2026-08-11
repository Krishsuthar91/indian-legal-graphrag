"""Tests for the benchmark runner (full QA pipeline execution)."""

import json

import pytest

from src.evaluation.corpus import build_evaluation_service
from src.evaluation.dataset import load_benchmark_csv
from src.evaluation.runner import (
    RAW_CSV_COLUMNS,
    RawResult,
    run_questions,
    save_raw_csv,
    save_raw_json,
)
from src.retrieval.intent import INTENTS

# 11-node synthetic "Indian Contract Act, 1892" document used by the existing
# eval fixtures — tiny and fast, perfect for deterministic offline tests.
EVAL_DOCUMENT_ID = "0940d367554383c5"


@pytest.fixture(scope="module")
def eval_service():
    service, graph = build_evaluation_service(document_id=EVAL_DOCUMENT_ID)
    return service, graph


@pytest.fixture(scope="module")
def sample_items():
    return load_benchmark_csv()[:3]


def test_run_questions_collects_all_fields(eval_service, sample_items):
    service, _ = eval_service
    rows = run_questions(service, sample_items)
    assert len(rows) == 3
    row = rows[0]

    assert isinstance(row, RawResult)
    assert row.item_id == sample_items[0].id
    assert row.question == sample_items[0].question
    assert row.expected_sections == sample_items[0].expected_sections
    assert row.answer
    assert row.model
    assert isinstance(row.confidence, float)
    assert row.confidence_label
    assert row.latency_ms >= 0
    assert row.retrieval_latency_ms >= 0
    assert row.ranking_latency_ms >= 0
    assert row.llm_time_ms >= 0
    assert isinstance(row.retrieved_nodes, list)
    assert row.intent_class in INTENTS
    assert row.adaptive_top_k is None or isinstance(row.adaptive_top_k, int)
    assert isinstance(row.duplicate_removal_count, int)
    assert len(row.hierarchy_chain) == len(row.retrieved_nodes)
    assert isinstance(row.retrieved_candidates, int)
    assert isinstance(row.ranked_candidates, int)
    assert isinstance(row.supported, bool)
    assert isinstance(row.insufficient_evidence, bool)
    assert row.retrieval_strategy


def test_evidence_dicts_are_structured(eval_service, sample_items):
    service, _ = eval_service
    row = run_questions(service, sample_items[:1])[0]
    if row.retrieved_evidence:
        ev = row.retrieved_evidence[0]
        assert {"node_id", "title", "numbering", "final_score", "snippet"} <= set(ev)
    assert row.ranking_signals is not None


def test_save_raw_json_and_csv(eval_service, sample_items, tmp_path):
    service, _ = eval_service
    rows = run_questions(service, sample_items)

    json_path = save_raw_json(rows, tmp_path / "raw_results.json", meta={"n": 3})
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["meta"]["n"] == 3
    assert len(payload["results"]) == 3
    assert payload["results"][0]["item_id"] == rows[0].item_id
    assert payload["results"][0]["retrieved_evidence"] == rows[0].retrieved_evidence

    csv_path = save_raw_csv(rows, tmp_path / "raw_results.csv")
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == list(RAW_CSV_COLUMNS)
    assert len(lines) == 4  # header + 3 rows
    assert '"node_id"' in lines[1]  # JSON-encoded evidence survives
