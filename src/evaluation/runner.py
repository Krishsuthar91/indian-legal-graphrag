"""Benchmark runner — executes the full QA pipeline for every question.

Each question is answered through ``QueryService.answer(...)`` — the exact
code path the frontend ``/query`` endpoint uses (retrieve -> explain ->
grounding guard / prompt build -> LLM generation -> provenance store). No
``top_k`` is passed so the adaptive-retrieval strategy from settings applies,
mirroring production behaviour.

The collected raw rows are written to ``results/raw_results.json`` and
``results/raw_results.csv``.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.evaluation.dataset import BenchmarkItem
from src.evaluation.sections import predicted_sections
from src.llm.provenance import AnswerResult
from src.llm.service import QueryService


@dataclass
class RawResult:
    """Everything collected for one benchmark question."""

    item_id: str
    question: str
    query_type: str
    difficulty: str
    expected_section: str
    expected_sections: list[str]
    predicted_section: str
    predicted_sections: list[str]
    answer: str
    model: str
    retrieved_evidence: list[dict[str, Any]]
    confidence: float
    confidence_label: str
    latency_ms: float
    retrieval_latency_ms: float
    ranking_latency_ms: float
    llm_time_ms: float
    retrieved_nodes: list[str]
    ranking_signals: dict[str, Any]
    intent_class: str
    adaptive_top_k: int | None
    duplicate_removal_count: int
    hierarchy_chain: list[list[str]]
    retrieval_strategy: str
    retrieved_candidates: int
    ranked_candidates: int
    supported: bool
    insufficient_evidence: bool
    has_conflicts: bool
    latency_breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation (dataclass + ``asdict``)."""
        return asdict(self)

    def to_csv_row(self) -> dict[str, object]:
        """Flattened row for ``raw_results.csv`` (lists/dicts become JSON)."""
        return {
            "item_id": self.item_id,
            "question": self.question,
            "query_type": self.query_type,
            "difficulty": self.difficulty,
            "expected_section": self.expected_section,
            "predicted_section": self.predicted_section,
            "answer": self.answer,
            "retrieved_evidence": json.dumps(self.retrieved_evidence, ensure_ascii=False),
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "retrieved_nodes": json.dumps(self.retrieved_nodes),
            "ranking_signals": json.dumps(self.ranking_signals),
            "intent_class": self.intent_class,
            "adaptive_top_k": self.adaptive_top_k,
            "duplicate_removal_count": self.duplicate_removal_count,
            "hierarchy_chain": json.dumps(self.hierarchy_chain),
        }


def _evidence_dicts(evidence: list) -> list[dict[str, Any]]:
    """Compact evidence summaries for the raw output."""
    rows: list[dict[str, Any]] = []
    for ev in evidence:
        rows.append(
            {
                "node_id": ev.node_id,
                "title": ev.title,
                "text": ev.text,
                "label": ev.label,
                "numbering": ev.numbering,
                "final_score": ev.final_score,
                "dense_score": ev.dense_score,
                "graph_score": ev.graph_score,
                "hierarchy_score": ev.hierarchy_score,
                "sources": list(ev.sources),
                "path": list(ev.path),
                "snippet": ev.snippet,
            }
        )
    return rows


def _hierarchy_chains(evidence: list) -> list[list[str]]:
    """Root -> node ancestor chains for each evidence entry."""
    return [list(ev.path) for ev in evidence]


def run_questions(
    service: QueryService,
    items: list[BenchmarkItem],
    *,
    deadline: float | None = None,
) -> list[RawResult]:
    """Answer every benchmark question through the full QA pipeline.

    ``deadline`` is a monotonic-clock timestamp forwarded to the LLM call (the
    API layer does the same); leave ``None`` to let the client use its own
    default bound.
    """
    rows: list[RawResult] = []
    for item in items:
        start = time.perf_counter()
        result: AnswerResult = service.answer(item.question, deadline=deadline)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        explanation = result.explanation
        retrieval = explanation.retrieval
        evidence = explanation.evidence
        predicted = sorted(predicted_sections(evidence))

        retrieval_latency = float(retrieval.total_retrieval_latency_ms)
        ranking_latency = float(retrieval.ranking_latency_ms)
        llm_time = max(0.0, elapsed_ms - retrieval_latency)

        rows.append(
            RawResult(
                item_id=item.id,
                question=item.question,
                query_type=item.query_type,
                difficulty=item.difficulty,
                expected_section=item.expected_section,
                expected_sections=list(item.expected_sections),
                predicted_section=", ".join(predicted),
                predicted_sections=predicted,
                answer=result.answer,
                model=result.model,
                retrieved_evidence=_evidence_dicts(evidence),
                confidence=float(explanation.confidence.score),
                confidence_label=explanation.confidence.label,
                latency_ms=round(elapsed_ms, 3),
                retrieval_latency_ms=round(retrieval_latency, 3),
                ranking_latency_ms=round(ranking_latency, 3),
                llm_time_ms=round(llm_time, 3),
                retrieved_nodes=[ev.node_id for ev in evidence],
                ranking_signals=dict(retrieval.ranking_breakdown),
                intent_class=retrieval.query_intent or retrieval.intent,
                adaptive_top_k=retrieval.adaptive_top_k,
                duplicate_removal_count=int(retrieval.duplicates_removed),
                hierarchy_chain=_hierarchy_chains(evidence),
                retrieval_strategy=retrieval.retrieval_strategy,
                retrieved_candidates=int(retrieval.retrieved_candidates),
                ranked_candidates=int(retrieval.ranked_candidates),
                supported=explanation.validity.supported,
                insufficient_evidence=explanation.validity.insufficient_evidence,
                has_conflicts=explanation.validity.has_conflicts,
                latency_breakdown=dict(retrieval.latency_breakdown),
            )
        )
    return rows


RAW_CSV_COLUMNS = (
    "item_id",
    "question",
    "query_type",
    "difficulty",
    "expected_section",
    "predicted_section",
    "answer",
    "retrieved_evidence",
    "confidence",
    "latency_ms",
    "retrieved_nodes",
    "ranking_signals",
    "intent_class",
    "adaptive_top_k",
    "duplicate_removal_count",
    "hierarchy_chain",
)


def save_raw_json(
    rows: list[RawResult], path: str | Path, meta: dict[str, Any] | None = None
) -> Path:
    """Persist raw results (plus optional metadata) as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"meta": meta or {}, "results": [row.to_dict() for row in rows]}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def save_raw_csv(rows: list[RawResult], path: str | Path) -> Path:
    """Persist raw results as a flattened CSV."""
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=RAW_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())
    return path
