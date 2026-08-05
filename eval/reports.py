"""Module 10, Part 7 — Benchmark report generation.

Exports the same benchmark data as CSV, JSON, Markdown, and a PDF summary that
embeds the latency and accuracy charts alongside the result tables.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_METRIC_LABELS = {
    "recall_at_k": "Recall@K",
    "precision_at_k": "Precision@K",
    "hit_rate_at_k": "Hit Rate@K",
    "mrr": "MRR",
    "map": "MAP",
    "ndcg_at_k": "NDCG@K",
    "mean_ms": "Mean Latency (ms)",
    "p50_ms": "p50 Latency (ms)",
    "p95_ms": "p95 Latency (ms)",
    "throughput_qps": "Throughput (q/s)",
    "citation_accuracy": "Citation Accuracy",
    "hierarchy_correctness": "Hierarchy Correctness",
    "graph_path_accuracy": "Graph Path Accuracy",
    "provenance_completeness": "Provenance Completeness",
    "evidence_coverage": "Evidence Coverage",
    "counter_authority_f1": "Counter-Authority F1",
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "context_recall": "Context Recall",
    "context_precision": "Context Precision",
    "answer_correctness": "Answer Correctness",
}


def metric_label(key: str) -> str:
    return _METRIC_LABELS.get(key, key)


def write_json(data: Any, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_csv(rows: Sequence[dict[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    headers = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})
    return path


def markdown_table(title: str, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render one markdown table with an aligned header separator."""
    header_row = "| " + " | ".join(str(h) for h in headers) + " |"
    separator = "|" + "---|" * len(headers)
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return f"#### {title}\n\n{header_row}\n{separator}\n" + "\n".join(body) + "\n"


def write_markdown(
    sections: Sequence[dict[str, Any]],
    path: str | Path,
    title: str = "Explaintool HHGR Evaluation Report",
) -> Path:
    """Write a markdown report from ``sections`` of table dicts."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    for section in sections:
        lines.append(markdown_table(
            section.get("title", "Table"),
            section.get("headers", []),
            section.get("rows", []),
        ))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_pdf(
    path: str | Path,
    title: str,
    tables: Sequence[dict[str, Any]],
    figures: Sequence[str | Path],
    meta: dict[str, Any] | None = None,
) -> Path:
    """Render a PDF summary with result tables and embedded PNG charts."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=18, spaceAfter=12
    )
    heading_style = ParagraphStyle(
        "ReportH2", parent=styles["Heading2"], spaceBefore=10, spaceAfter=6
    )
    small = ParagraphStyle("SmallMono", parent=styles["BodyText"], fontSize=7.5)

    story: list[Any] = [Paragraph(title, title_style)]
    if meta:
        for key, value in meta.items():
            story.append(Paragraph(f"<b>{key}:</b> {value}", small))
        story.append(Spacer(1, 0.4 * cm))

    for table in tables:
        story.append(Paragraph(table.get("title", "Table"), heading_style))
        headers = [str(h) for h in table.get("headers", [])]
        rows = [[str(cell) for cell in row] for row in table.get("rows", [])]
        data = [headers] + rows
        pdf_table = Table(data, repeatRows=1)
        pdf_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(pdf_table)
        story.append(Spacer(1, 0.5 * cm))

    for figure in figures:
        image_path = Path(figure)
        if image_path.exists():
            from PIL import Image as PilImage

            with PilImage.open(image_path) as img:
                width, height = img.size
            aspect = height / width
            width_cm = min(16, 16)
            story.append(Image(str(image_path), width=width_cm * cm, height=width_cm * aspect * cm))
            story.append(Spacer(1, 0.5 * cm))
            story.append(PageBreak())

    doc.build(story)
    return path
