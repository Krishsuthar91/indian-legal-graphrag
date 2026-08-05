"""Module 10, Part 8 — Research figures.

Generates publication-ready diagrams and evaluation charts as both SVG (vector)
and PNG (raster) files under the output figures directory.

Figures: architecture diagram, pipeline flow, knowledge-graph example,
hierarchy tree, retrieval flow, system comparison, ablation study, latency, and
a RAGAS radar plot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from eval.corpus import Corpus

_COLORS = {
    "hhgr": "#1F4E79",
    "dense": "#2E8B57",
    "bm25": "#B8860B",
    "graph": "#8B0000",
    "naive_rag": "#6A5ACD",
    "full": "#1F4E79",
    "no_graph": "#B8860B",
    "no_hierarchy": "#2E8B57",
    "no_dense": "#8B0000",
    "no_multilingual": "#6A5ACD",
    "no_explainability": "#696969",
    "hybrid": "#696969",
}

_STYLE = {
    "axes.edgecolor": "#333333",
    "axes.labelcolor": "#111111",
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "font.family": "DejaVu Sans",
    "figure.facecolor": "white",
}


def _save(fig, out_dir: Path, name: str) -> dict[str, str]:
    fig.tight_layout()
    svg = out_dir / f"{name}.svg"
    png = out_dir / f"{name}.png"
    fig.savefig(svg, format="svg")
    fig.savefig(png, format="png", dpi=300)
    plt.close(fig)
    return {"svg": str(svg), "png": str(png)}


def _color_for(name: str) -> str:
    return _COLORS.get(name, "#555555")


def _prepare(out_dir: str | Path) -> Path:
    plt.style.use(_STYLE)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def pipeline_architecture(out_dir: str | Path) -> dict[str, str]:
    """Block-diagram of the Explaintool HHGR architecture."""
    out = _prepare(out_dir)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.axis("off")

    boxes = [
        (0.05, 0.72, 0.18, 0.16, "Document Intake",
         "PDF / DOCX parsing\nOCR + hierarchy detection"),
        (0.30, 0.72, 0.18, 0.16, "Knowledge Graph",
         "Neo4j / in-memory\nPART_OF hierarchy + citations"),
        (0.55, 0.72, 0.18, 0.16, "Embeddings",
         "Multilingual dense vectors\nQdrant collections"),
        (0.80, 0.72, 0.18, 0.16, "Indexer",
         "Hierarchical index\nincremental sync"),
    ]
    for x, y, w, h, title, sub in boxes:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor="#DCE6F1", edgecolor="#1F4E79", lw=1.5))
        ax.text(x + w / 2, y + h - 0.03, title, ha="center", va="top", fontsize=10, weight="bold")
        ax.text(
            x + w / 2, y + h * 0.28, sub, ha="center",
            va="center", fontsize=7.5, color="#333333",
        )

    stages = [
        (0.05, 0.34, 0.18, 0.16, "1. Query Parsing",
         "keywords, section refs,\ncitation texts"),
        (0.30, 0.34, 0.18, 0.16, "2. Dense Retrieval",
         "multilingual semantic\nvector search"),
        (0.55, 0.34, 0.18, 0.16, "3. Graph Retrieval",
         "HHGR text/citation/\nhierarchy/structural signals"),
        (0.80, 0.34, 0.18, 0.16, "4. Hierarchy Fusion",
         "evidence propagation\nancestor/descendant"),
    ]
    for x, y, w, h, title, sub in stages:
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor="#E2EFDA", edgecolor="#2E8B57", lw=1.5))
        ax.text(x + w / 2, y + h - 0.03, title, ha="center", va="top", fontsize=10, weight="bold")
        ax.text(
            x + w / 2, y + h * 0.28, sub, ha="center",
            va="center", fontsize=7.5, color="#333333",
        )

    fuse = plt.Rectangle((0.30, 0.04), 0.40, 0.16, facecolor="#FCE4D6", edgecolor="#8B0000", lw=1.5)
    ax.add_patch(fuse)
    ax.text(
        0.50, 0.12, "5. Fusion + Explainability",
        ha="center", va="center", fontsize=11, weight="bold",
    )
    ax.text(
        0.50, 0.045,
        "evidence, reasoning chain, citations, confidence, validity, counter-authority",
        ha="center", va="center", fontsize=7.5,
    )

    for x_from, y_from, x_to, y_to in [
        (0.23, 0.80, 0.30, 0.80),
        (0.48, 0.80, 0.55, 0.80),
        (0.73, 0.80, 0.80, 0.80),
        (0.14, 0.72, 0.14, 0.50),
        (0.39, 0.72, 0.39, 0.50),
        (0.64, 0.72, 0.64, 0.50),
        (0.89, 0.72, 0.89, 0.50),
        (0.23, 0.42, 0.30, 0.20),
        (0.48, 0.42, 0.30, 0.20),
        (0.73, 0.42, 0.70, 0.20),
        (0.30, 0.20, 0.30, 0.12),
    ]:
        ax.annotate("", xy=(x_to, y_to), xytext=(x_from, y_from),
                    arrowprops=dict(arrowstyle="-|>", color="#555555", lw=1.3))

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Explaintool: Explainable Multilingual Hierarchical Graph-RAG (HHGR) Architecture")
    return _save(fig, out, "architecture")


def hierarchy_tree(out_dir: str | Path, corpus: Corpus) -> dict[str, str]:
    """Rooted hierarchy tree (document -> chapters -> sections)."""
    from src.knowledge_graph.traversal import get_children, get_parent

    out = _prepare(out_dir)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")

    levels: dict[int, list[dict]] = {}
    seen: set[str] = set()
    roots = [
        node
        for node in corpus.graph.all_nodes()
        if get_parent(corpus.graph, node["node_id"]) is None
    ]
    queue = [(node, 0) for node in roots]
    while queue:
        node, depth = queue.pop(0)
        node_id = node["node_id"]
        if node_id in seen:
            continue
        seen.add(node_id)
        levels.setdefault(depth, []).append(node)
        for child in get_children(corpus.graph, node_id):
            queue.append((child, depth + 1))

    if not levels:
        return {"svg": "", "png": ""}

    max_depth = max(levels)
    positions: dict[str, tuple[float, float]] = {}
    for depth, nodes in levels.items():
        x_step = 1.0 / (len(nodes) + 1)
        for i, node in enumerate(nodes, 1):
            x = i * x_step
            y = 1.0 - (depth + 1) / (max_depth + 2)
            positions[node["node_id"]] = (x, y)

    for node in corpus.graph.all_nodes():
        node_id = node["node_id"]
        if node_id not in positions:
            continue
        parent = get_parent(corpus.graph, node_id)
        if parent and parent["node_id"] in positions:
            x1, y1 = positions[node_id]
            x2, y2 = positions[parent["node_id"]]
            ax.plot([x1, x2], [y1, y2], color="#888888", lw=1.0, zorder=1)

    for node in corpus.graph.all_nodes():
        node_id = node["node_id"]
        if node_id not in positions:
            continue
        x, y = positions[node_id]
        title = node.get("title") or node.get("node_id", "")
        label = node.get("label", "")
        if len(title) > 24:
            title = title[:22] + "…"
        ax.text(x, y, f"{title}\n{label}", ha="center", va="center", fontsize=6.5,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#E2EFDA", edgecolor="#2E8B57"))

    ax.set_title(f"Hierarchy Tree — {corpus.hierarchy_file.name}")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(0, 1.02)
    return _save(fig, out, "hierarchy_tree")


def kg_example_graph(out_dir: str | Path, corpus: Corpus) -> dict[str, str]:
    """Force-directed-style knowledge-graph example for the Contract Act document."""
    out = _prepare(out_dir)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.axis("off")

    rng = np.random.default_rng(7)
    nodes = corpus.graph.all_nodes()
    if not nodes:
        return {"svg": "", "png": ""}
    positions: dict[str, np.ndarray] = {}
    for node in nodes:
        positions[node["node_id"]] = np.array([rng.uniform(0, 1), rng.uniform(0, 1)])
    for _ in range(80):
        for a_id, a_pos in positions.items():
            for b_id, b_pos in positions.items():
                if a_id >= b_id:
                    continue
                diff = a_pos - b_pos
                dist = np.linalg.norm(diff) + 1e-9
                force = 0.002 * (1.0 / dist**2 - 0.6)
                a_pos += force * diff / dist * 0.01
                b_pos -= force * diff / dist * 0.01

    for node in nodes:
        node_id = node["node_id"]
        for edge in corpus.graph.get_edges(node_id):
            other = edge["to_node"] if edge["from_node"] == node_id else edge["from_node"]
            if other in positions:
                x = [positions[node_id][0], positions[other][0]]
                y = [positions[node_id][1], positions[other][1]]
                ax.plot(x, y, color="#B0B0B0", lw=0.8, zorder=1)

    colors = {"Document": "#1F4E79", "Chapter": "#2E8B57", "Section": "#8B0000", "Case": "#6A5ACD"}
    for node in nodes:
        node_id = node["node_id"]
        x, y = positions[node_id]
        label = node.get("label", "Node")
        color = colors.get(label, "#888888")
        title = node.get("title") or node_id
        if len(title) > 20:
            title = title[:18] + "…"
        ax.scatter(x, y, s=220, color=color, zorder=2)
        ax.annotate(title, (x, y), fontsize=6, ha="center", va="center",
                    color="white", weight="bold", zorder=3)

    ax.set_title("Knowledge Graph Example — Indian Contract Act, 1892 (PART_OF + citation edges)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    return _save(fig, out, "kg_example")


def retrieval_flow_chart(out_dir: str | Path, output: Any) -> dict[str, str]:
    """Output counts of the HHGR retrieval + explanation stages."""
    out = _prepare(out_dir)
    fig, ax = plt.subplots(figsize=(8, 4))
    if output.explainability:
        rows = output.explainability[:1]
        values = [
            rows[0].get("n_evidence", 0),
            rows[0].get("n_citations", 0),
            rows[0].get("n_counter_authorities", 0),
        ]
        bar_labels = ["Evidence", "Citations", "Counter-\nauthorities"]
        bars = ax.bar(bar_labels, values, color=[_color_for("hhgr"), "#2E8B57", "#8B0000"])
        ax.bar_label(bars)
        ax.set_ylabel("Count")
        ax.set_title("Retrieval Flow Output — evidence, citations, counter-authority detection")
    else:
        bar_labels = ["Evidence", "Citations", "Counter-\nauthorities"]
        ax.bar(bar_labels, [0, 0, 0], color="#9DB8D2")
        ax.set_ylabel("Count")
        ax.set_title("Retrieval Flow — stage counts (no data)")
    return _save(fig, out, "retrieval_flow")


def eval_comparison(out_dir: str | Path, retrieval_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Grouped bar chart comparing the five systems across accuracy metrics."""
    out = _prepare(out_dir)
    metrics = ["recall_at_k", "precision_at_k", "mrr", "map", "ndcg_at_k"]
    labels = ["Recall@K", "Precision@K", "MRR", "MAP", "NDCG@K"]
    systems = [row["system"] for row in retrieval_rows]
    x = np.arange(len(labels))
    width = 0.15
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, system in enumerate(systems):
        values = [retrieval_rows[i].get(m, 0.0) for m in metrics]
        offset = (i - len(systems) / 2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=system, color=_color_for(system))
        ax.bar_label(bars, fmt="%.2f", fontsize=7, padding=2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Score")
    ax.set_title("Retrieval Accuracy by System (K=5)")
    ax.legend(ncol=5, loc="upper center", fontsize=8)
    return _save(fig, out, "eval_comparison")


def ablation_chart(out_dir: str | Path, ablation_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Grouped bar chart across ablation variants."""
    out = _prepare(out_dir)
    metrics = ["recall_at_k", "mrr", "map"]
    labels = ["Recall@K", "MRR", "MAP"]
    variants = [row["ablation"] for row in ablation_rows]
    x = np.arange(len(labels))
    width = 0.14
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, variant in enumerate(variants):
        values = [ablation_rows[i].get(m, 0.0) for m in metrics]
        offset = (i - len(variants) / 2 + 0.5) * width
        ax.bar(
            x + offset, values, width,
            label=ablation_rows[i]["label"],
            color=_color_for(variant),
        )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Score")
    ax.set_title("Ablation Study — component removal impact on retrieval accuracy")
    ax.legend(ncol=3, loc="upper center", fontsize=7)
    return _save(fig, out, "ablation_chart")


def latency_chart(out_dir: str | Path, retrieval_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Latency comparison (mean / p50 / p95) across systems."""
    out = _prepare(out_dir)
    systems = [row["system"] for row in retrieval_rows]
    x = np.arange(len(systems))
    width = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (key, label) in enumerate([("mean_ms", "Mean"), ("p50_ms", "p50"), ("p95_ms", "p95")]):
        values = [retrieval_rows[j].get(key, 0.0) for j in range(len(systems))]
        ax.bar(x + (i - 1) * width, values, width, label=label,
               color=[_color_for("hhgr"), "#2E8B57", "#B8860B"][i])
    ax.set_xticks(x)
    ax.set_xticklabels(systems)
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Retrieval Latency by System")
    ax.legend()
    return _save(fig, out, "latency_chart")


def ragas_radar(out_dir: str | Path, ragas_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Radar chart of RAGAS-style metrics for hhgr vs naive_rag."""
    out = _prepare(out_dir)
    metrics = [
        "faithfulness",
        "answer_relevancy",
        "context_recall",
        "context_precision",
        "answer_correctness",
    ]
    labels = [
        "Faithfulness",
        "Answer\nRelevancy",
        "Context\nRecall",
        "Context\nPrecision",
        "Answer\nCorrectness",
    ]

    def _mean(system: str) -> list[float]:
        values = [row for row in ragas_rows if row["system"] == system]
        if not values:
            return [0.0] * len(metrics)
        return [
            sum(row[metric] for row in values) / len(values)
            for metric in metrics
        ]

    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    for system in ("hhgr", "naive_rag"):
        values = _mean(system)
        values += values[:1]
        ax.plot(angles, values, linewidth=2, label=system, color=_color_for(system))
        ax.fill(angles, values, alpha=0.12, color=_color_for(system))
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_title("RAGAS-style Generation Metrics (offline surrogate)")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.05))
    return _save(fig, out, "ragas_radar")


def run_all_figures(out_dir: str | Path, output: Any, corpus: Corpus) -> dict[str, dict[str, str]]:
    """Generate every figure for a completed benchmark run."""
    figures: dict[str, dict[str, str]] = {}
    figures["architecture"] = pipeline_architecture(out_dir)
    figures["hierarchy_tree"] = hierarchy_tree(out_dir, corpus)
    figures["kg_example"] = kg_example_graph(out_dir, corpus)
    figures["retrieval_flow"] = retrieval_flow_chart(out_dir, output)
    figures["eval_comparison"] = eval_comparison(out_dir, output.retrieval)
    figures["latency_chart"] = latency_chart(out_dir, output.retrieval)
    if output.ablation_rows:
        figures["ablation_chart"] = ablation_chart(out_dir, output.ablation_rows)
    if output.ragas:
        figures["ragas_radar"] = ragas_radar(out_dir, output.ragas)
    return figures
