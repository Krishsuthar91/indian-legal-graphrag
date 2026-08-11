"""Markdown evaluation report generation.

Produces ``results/evaluation_report.md`` with the overall score, metric
tables, error analysis (per query-type / difficulty), failure categories, top
failure examples, most successful queries, and auto-generated
recommendations.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.evaluation.metrics.aggregate import (
    GENERATION_METRIC_KEYS,
    RETRIEVAL_METRIC_KEYS,
    group_by,
    summarize_metrics,
)

FAILURE_CATEGORIES = (
    ("insufficient_evidence", "grounding guard triggered (evidence below threshold)"),
    ("no_evidence", "no evidence retrieved for the question"),
    ("section_miss", "at least one expected section not surfaced"),
    ("low_confidence", "aggregate confidence below the 0.45 threshold"),
    ("high_hallucination", "hallucination rate above 0.5"),
    ("ungrounded_citation", "answer cites a source not in the retrieved evidence"),
    ("slow_query", "latency above the p95 for the run"),
)

_HALLUCINATION_THRESHOLD = 0.5


def _failure_score(row: dict[str, Any]) -> float:
    return round(
        (1.0 - row.get("section_accuracy", 0.0))
        + (1.0 - row.get("mrr", 0.0))
        + row.get("hallucination_rate", 0.0)
        + (1.0 - row.get("grounding_accuracy", 0.0)),
        4,
    )


def _success_score(row: dict[str, Any]) -> float:
    return round(
        row.get("section_accuracy", 0.0)
        + row.get("mrr", 0.0)
        + row.get("faithfulness", 0.0)
        + row.get("evidence_coverage", 0.0)
        + (1.0 - row.get("hallucination_rate", 0.0))
        + row.get("grounding_accuracy", 0.0),
        4,
    )


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        cells = [_format_cell(cell) for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _format_cell(cell: Any) -> str:
    if isinstance(cell, float):
        return f"{cell:.4f}"
    text = str(cell).replace("|", "/").replace("\n", " ")
    if len(text) > 90:
        text = text[:90] + "…"
    return text


def _recommendations(aggregate: dict[str, float], performance: dict[str, float]) -> list[str]:
    recs: list[str] = []
    if aggregate.get("recall_at_5", 1.0) < 0.5:
        recs.append(
            "Retrieval recall is low — increase the adaptive evidence budget, add "
            "synonym/expansion terms, or index finer-grained nodes so expected "
            "sections can be surfaced."
        )
    if aggregate.get("section_accuracy", 1.0) < 0.5:
        recs.append(
            "Section accuracy is low — the parsed hierarchy does not expose many of "
            "the benchmark sections; improving document parsing granularity would "
            "directly raise section accuracy."
        )
    if aggregate.get("hierarchy_accuracy", 1.0) < 0.9:
        recs.append(
            "Hierarchy paths are frequently inconsistent with the graph — verify "
            "parent/child edges during import and deduplicate evidence so ancestry "
            "chains stay intact."
        )
    if aggregate.get("grounding_accuracy", 1.0) < 0.9:
        recs.append(
            "Answers cite sources not present in the retrieved evidence — enforce "
            "that inline citations reference the provided source blocks."
        )
    if aggregate.get("hallucination_rate", 0.0) > 0.2:
        recs.append(
            "Hallucination rate is high — reinforce the prompt's grounding rules or "
            "route low-confidence queries through the insufficient-evidence guard."
        )
    if aggregate.get("answer_accuracy", 0.0) < 0.3:
        recs.append(
            "Answer accuracy is low — the offline (mock) LLM only echoes the query; "
            "run the evaluation with a real provider to measure answer quality."
        )
    if performance.get("p95_latency_ms", 0.0) > 5000:
        recs.append(
            "P95 latency exceeds 5s — profile the embedding/vector store and the LLM "
            "deadline handling for the slowest queries."
        )
    if not recs:
        recs.append("All headline metrics are within targets — continue expanding the benchmark.")
    return recs


def build_report(
    *,
    meta: dict[str, Any],
    per_query_rows: list[dict[str, float]],
    performance: dict[str, float],
    scores: dict[str, float],
    p95_latency_ms: float,
    raw_rows: list[Any],
) -> str:
    """Render the full evaluation report as a Markdown string."""
    aggregate = summarize_metrics(per_query_rows)
    sections: list[str] = []

    sections.append("# HHGR Research Evaluation Report")
    sections.append("")
    sections.append(
        _markdown_table(
            ["Field", "Value"],
            [
                ["generated_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())],
                ["document_id", meta.get("document_id", "")],
                ["hierarchy_file", str(meta.get("hierarchy_file", ""))],
                ["questions", meta.get("questions", 0)],
                ["llm_provider", meta.get("llm_provider", "")],
                ["model", meta.get("model", "")],
                ["embedding_provider", meta.get("embedding_provider", "")],
                ["seed", meta.get("seed", "")],
                ["confidence_threshold", meta.get("confidence_threshold", "")],
            ],
        )
    )
    sections.append("")

    # -- Overall score -----------------------------------------------------
    sections.append("## Overall Score")
    sections.append("")
    sections.append(
        _markdown_table(
            ["Score", "Value"],
            [
                ["Overall", scores["overall"]],
                ["Retrieval (0.4)", scores["retrieval"]],
                ["Generation (0.4)", scores["generation"]],
                ["Performance (0.2)", scores["performance"]],
            ],
        )
    )
    sections.append("")

    # -- Metric tables -----------------------------------------------------
    sections.append("## Metric Tables")
    sections.append("")

    sections.append("### Retrieval Metrics")
    sections.append("")
    sections.append(
        _markdown_table(
            ["Metric", "Mean"],
            [[key, aggregate[key]] for key in RETRIEVAL_METRIC_KEYS],
        )
    )
    sections.append("")

    sections.append("### Generation Metrics")
    sections.append("")
    sections.append(
        _markdown_table(
            ["Metric", "Mean"],
            [[key, aggregate[key]] for key in GENERATION_METRIC_KEYS],
        )
    )
    sections.append("")

    sections.append("### Performance Metrics")
    sections.append("")
    sections.append(
        _markdown_table(
            ["Metric", "Value"],
            [
                ["Average Latency (ms)", performance.get("average_latency_ms", 0.0)],
                ["P95 Latency (ms)", performance.get("p95_latency_ms", 0.0)],
                ["Average Retrieval Time (ms)", performance.get("average_retrieval_time_ms", 0.0)],
                ["Average LLM Time (ms)", performance.get("average_llm_time_ms", 0.0)],
                ["Average Ranking Time (ms)", performance.get("average_ranking_time_ms", 0.0)],
                ["Memory Usage (MB)", performance.get("memory_usage_mb", 0.0)],
            ],
        )
    )
    sections.append("")

    # -- Error analysis ----------------------------------------------------
    sections.append("## Error Analysis")
    sections.append("")
    for group_name, group_rows in group_by(per_query_rows, "query_type").items():
        sections.append(f"### By Query Type: {group_name}")
        sections.append("")
        sections.append(
            _markdown_table(
                ["Metric", "Mean"],
                [[key, group_rows[key]] for key in RETRIEVAL_METRIC_KEYS + GENERATION_METRIC_KEYS],
            )
        )
        sections.append("")
    for group_name, group_rows in group_by(per_query_rows, "difficulty").items():
        sections.append(f"### By Difficulty: {group_name}")
        sections.append("")
        sections.append(
            _markdown_table(
                ["Metric", "Mean"],
                [[key, group_rows[key]] for key in RETRIEVAL_METRIC_KEYS + GENERATION_METRIC_KEYS],
            )
        )
        sections.append("")

    # -- Failure categories ------------------------------------------------
    sections.append("## Failure Categories")
    sections.append("")
    counts: dict[str, int] = {name: 0 for name, _ in FAILURE_CATEGORIES}
    # attach raw-only fields used by classification
    for row, raw in zip(per_query_rows, raw_rows):
        row["_raw"] = raw
    for row in per_query_rows:
        raw = row["_raw"]
        for name, _ in FAILURE_CATEGORIES:
            if name == "slow_query" and row.get("latency_ms", 0.0) > p95_latency_ms:
                counts[name] += 1
            elif name == "insufficient_evidence" and getattr(raw, "insufficient_evidence", False):
                counts[name] += 1
            elif name == "no_evidence" and not getattr(raw, "retrieved_nodes", None):
                counts[name] += 1
            elif name == "section_miss" and row.get("section_accuracy", 1.0) < 1.0:
                counts[name] += 1
            elif name == "low_confidence" and row.get("confidence", 1.0) < 0.45:
                counts[name] += 1
            elif name == "high_hallucination" and row.get(
                "hallucination_rate", 0.0
            ) > _HALLUCINATION_THRESHOLD:
                counts[name] += 1
            elif name == "ungrounded_citation" and row.get("grounding_accuracy", 1.0) < 1.0:
                counts[name] += 1
    sections.append(
        _markdown_table(
            ["Category", "Count", "Description"],
            [[name, counts[name], description] for name, description in FAILURE_CATEGORIES],
        )
    )
    sections.append("")

    # -- Top failures ------------------------------------------------------
    sections.append("## Top Failure Examples")
    sections.append("")
    ranked = sorted(per_query_rows, key=_failure_score, reverse=True)[:5]
    sections.append(
        _markdown_table(
            ["ID", "Question", "Failure Score", "Section Acc.", "MRR", "Halluc.", "Grounding"],
            [
                [
                    row["item_id"],
                    row["question"],
                    _failure_score(row),
                    row.get("section_accuracy", 0.0),
                    row.get("mrr", 0.0),
                    row.get("hallucination_rate", 0.0),
                    row.get("grounding_accuracy", 0.0),
                ]
                for row in ranked
            ],
        )
    )
    sections.append("")

    # -- Most successful ---------------------------------------------------
    sections.append("## Most Successful Queries")
    sections.append("")
    ranked = sorted(per_query_rows, key=_success_score, reverse=True)[:5]
    sections.append(
        _markdown_table(
            ["ID", "Question", "Success Score", "Section Acc.", "MRR", "Faithfulness", "Coverage"],
            [
                [
                    row["item_id"],
                    row["question"],
                    _success_score(row),
                    row.get("section_accuracy", 0.0),
                    row.get("mrr", 0.0),
                    row.get("faithfulness", 0.0),
                    row.get("evidence_coverage", 0.0),
                ]
                for row in ranked
            ],
        )
    )
    sections.append("")

    # -- Recommendations ---------------------------------------------------
    sections.append("## Recommendations")
    sections.append("")
    for i, recommendation in enumerate(_recommendations(aggregate, performance), 1):
        sections.append(f"{i}. {recommendation}")
    sections.append("")

    return "\n".join(sections)


def write_report(path: str | Path, content: str) -> Path:
    """Write the report markdown to disk (creating parent directories)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
