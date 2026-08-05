"""Module 10, Part 6 — Ablation study.

Removes one component of the HHGR pipeline at a time and re-measures retrieval
and explainability quality over the gold dataset:

- ``full``            — dense + graph + hierarchy + multilingual + explainability
- ``no_graph``        — graph signal zeroed
- ``no_hierarchy``    — hierarchy signal zeroed
- ``no_dense``        — dense signal zeroed (graph-only fusion)
- ``no_multilingual`` — Hindi queries forced through the English path
- ``no_explainability`` — signal fusion without provenance enrichment
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eval.corpus import Corpus
from eval.dataset import EvalItem
from eval.metrics.explainability import explainability_metrics
from eval.metrics.retrieval import retrieval_metrics, summarize
from eval.systems import HhgrSystem, HybridSystem
from src.embeddings.retriever import DEFAULT_HYBRID_WEIGHTS, normalize_weights

DEFAULT_WEIGHTS = dict(DEFAULT_HYBRID_WEIGHTS)


@dataclass
class AblationVariant:
    """A single ablation configuration."""

    name: str
    label: str
    weights: dict[str, float] | None = None
    force_language: str | None = None
    use_explanation: bool = True

    def build(self, corpus: Corpus) -> HhgrSystem | HybridSystem:
        weights = normalize_weights(self.weights) if self.weights else None
        if not self.use_explanation:
            return HybridSystem(corpus.retriever, weights=weights, language=self.force_language)
        if weights:
            from src.llm.explanation import ExplainabilityEngine

            engine = ExplainabilityEngine(
                corpus.graph,
                vector_retriever=corpus.retriever,
                weights=weights,
            )
        else:
            engine = corpus.engine
        return HhgrSystem(engine, language=self.force_language)


ABLATION_VARIANTS: list[AblationVariant] = [
    AblationVariant(name="full", label="Full HHGR", weights=DEFAULT_WEIGHTS),
    AblationVariant(
        name="no_graph",
        label="Without graph signal",
        weights={"dense": 0.40, "graph": 0.0, "hierarchy": 0.25},
    ),
    AblationVariant(
        name="no_hierarchy",
        label="Without hierarchy signal",
        weights={"dense": 0.40, "graph": 0.35, "hierarchy": 0.0},
    ),
    AblationVariant(
        name="no_dense",
        label="Without dense signal",
        weights={"dense": 0.0, "graph": 0.35, "hierarchy": 0.25},
    ),
    AblationVariant(
        name="no_multilingual",
        label="Without multilingual path",
        weights=DEFAULT_WEIGHTS,
        force_language="en",
    ),
    AblationVariant(
        name="no_explainability",
        label="Without explainability enrichment",
        weights=DEFAULT_WEIGHTS,
        use_explanation=False,
    ),
]


def run_ablation(
    corpus: Corpus,
    items: list[EvalItem],
    top_k: int = 5,
    variants: list[AblationVariant] | None = None,
) -> dict[str, Any]:
    """Run every ablation variant and return aggregated accuracy rows."""
    variants = variants or ABLATION_VARIANTS
    results: dict[str, Any] = {}
    for variant in variants:
        system = variant.build(corpus)
        per_item: list[dict[str, float]] = []
        explain_rows: list[dict[str, float]] = []
        latency: list[float] = []
        for item in items:
            result = system.run(item.query, top_k=top_k)
            latency.append(result.duration_ms)
            per_item.append(
                retrieval_metrics(item.gold_node_ids, result.retrieved_ids, k=top_k)
            )
            if result.explanation is not None:
                explain_rows.append(
                    explainability_metrics(
                        corpus.graph,
                        result.explanation,
                        item.citations,
                        reference_answer=item.reference_answer,
                        expected_markers=item.expected_counter_authority_markers,
                    )
                )
        row = summarize(
            per_item,
            latency,
            system=variant.name,
            items=len(items),
        )
        if explain_rows:
            from eval.metrics.retrieval import aggregate_metrics

            explain = aggregate_metrics(explain_rows)
            row.update({"explain_" + key: value for key, value in explain.items()})
        row["label"] = variant.label
        results[variant.name] = row
    return results


def build_ablation_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten ablation results into report-friendly rows."""
    rows: list[dict[str, Any]] = []
    for name, row in results.items():
        rows.append({"ablation": name, "label": row["label"], **row})
    return rows
