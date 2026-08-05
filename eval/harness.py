"""Module 10 — evaluation harness.

Ties together the corpus, dataset, systems, and metrics into a single
deterministic benchmark run. All functions are offline and deterministic given
the gold dataset and the on-disk corpus.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eval.ablation import build_ablation_rows, run_ablation
from eval.corpus import Corpus, build_corpus
from eval.dataset import EvalDataset, EvalItem, normalize_citation
from eval.metrics.explainability import explainability_metrics
from eval.metrics.ragas import EmbeddingCache, compute_ragas_metrics
from eval.metrics.retrieval import retrieval_metrics, summarize
from eval.systems import RetrievalSystem, SystemResult, build_systems


def item_relevant_ids(graph, item: EvalItem) -> set[str]:
    """Deterministic relevance set for an item (node ids or citation matches)."""
    if item.grounded and item.gold_node_ids:
        return item.gold_node_ids
    gold_keys = item.gold_citation_keys
    relevant: set[str] = set()
    for node in graph.all_nodes():
        node_id = node.get("node_id", "")
        if not node_id:
            continue
        key = normalize_citation(
            f"{node.get('label', '')} {node.get('numbering', '')} "
            f"{node.get('title', '')} {node_id}"
        )
        if any(gold_key in key or key in gold_key for gold_key in gold_keys):
            relevant.add(node_id)
    return relevant


@dataclass
class BenchmarkOutput:
    """Everything produced by one evaluation run."""

    meta: dict[str, Any] = field(default_factory=dict)
    retrieval: list[dict[str, Any]] = field(default_factory=list)
    per_query: list[dict[str, Any]] = field(default_factory=list)
    explainability: list[dict[str, Any]] = field(default_factory=list)
    ragas: list[dict[str, Any]] = field(default_factory=list)
    ablation: dict[str, Any] = field(default_factory=dict)
    ablation_rows: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "retrieval": self.retrieval,
            "per_query": self.per_query,
            "explainability": self.explainability,
            "ragas": self.ragas,
            "ablation": self.ablation,
            "ablation_rows": self.ablation_rows,
            "coverage": self.coverage,
        }


def run_system_batch(
    system: RetrievalSystem,
    items: list[EvalItem],
    top_k: int,
) -> list[tuple[EvalItem, SystemResult]]:
    """Run a system over every item, returning (item, result) pairs."""
    return [(item, system.run(item.query, top_k=top_k)) for item in items]


def benchmark_retrieval(
    corpus: Corpus,
    items: list[EvalItem],
    top_k: int = 5,
    systems: dict[str, RetrievalSystem] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Per-system aggregated accuracy + latency, and per-query detail rows."""
    systems = systems or build_systems(corpus, with_answers=False)
    summary_rows: list[dict[str, Any]] = []
    per_query: list[dict[str, Any]] = []
    for name, system in systems.items():
        metric_rows: list[dict[str, float]] = []
        latency: list[float] = []
        for item in items:
            result = system.run(item.query, top_k=top_k)
            latency.append(result.duration_ms)
            relevant = item_relevant_ids(corpus.graph, item)
            metrics = retrieval_metrics(relevant, result.retrieved_ids, k=top_k)
            metric_rows.append(metrics)
            per_query.append(
                {
                    "system": name,
                    "item_id": item.id,
                    "domain": item.domain,
                    "language": item.language,
                    "grounded": item.grounded,
                    "query": item.query,
                    "relevant_ids": sorted(relevant),
                    "retrieved_ids": result.retrieved_ids[:top_k],
                    "duration_ms": round(result.duration_ms, 3),
                    **metrics,
                }
            )
        summary_rows.append(
            summarize(metric_rows, latency, system=name, items=len(items))
        )
    return summary_rows, per_query


def benchmark_explainability(
    corpus: Corpus,
    items: list[EvalItem],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """HHGR explainability metrics (uses the corpus explainer engine)."""
    rows: list[dict[str, Any]] = []
    for item in items:
        result = corpus.engine.explain(item.query, top_k=top_k)
        metrics = explainability_metrics(
            corpus.graph,
            result,
            item.citations,
            reference_answer=item.reference_answer,
            expected_markers=item.expected_counter_authority_markers,
        )
        rows.append(
            {
                "item_id": item.id,
                "domain": item.domain,
                "language": item.language,
                "query": item.query,
                "n_evidence": len(result.evidence),
                "n_citations": len(result.citations),
                "n_counter_authorities": len(result.counter_authorities),
                "confidence": result.confidence.score,
                "is_valid": result.validity.is_valid,
                **metrics,
            }
        )
    return rows


def _evidence_bag(hits):
    """Minimal evidence-like container for answer systems without provenance."""

    class _EvidenceBag:
        def __init__(self, evidence) -> None:
            self.evidence = evidence

    return _EvidenceBag(hits)


def benchmark_ragas(
    corpus: Corpus,
    items: list[EvalItem],
    top_k: int = 5,
    systems: dict[str, RetrievalSystem] | None = None,
) -> list[dict[str, Any]]:
    """RAGAS-style generation metrics for answer-producing systems."""
    systems = systems or build_systems(corpus, with_answers=True)
    cache = EmbeddingCache()
    rows: list[dict[str, Any]] = []
    for name in ("hhgr", "naive_rag"):
        system = systems.get(name)
        if system is None:
            continue
        for item in items:
            result = system.run(item.query, top_k=top_k)
            evidence = result.explanation or _evidence_bag(result.hits)
            metrics = compute_ragas_metrics(
                query=item.query,
                answer=result.answer or "",
                reference_answer=item.reference_answer,
                result=evidence,
                gold_citations=item.citations,
                cache=cache,
            )
            rows.append(
                {
                    "system": name,
                    "item_id": item.id,
                    "domain": item.domain,
                    "language": item.language,
                    "query": item.query,
                    **metrics.to_dict(),
                }
            )
    return rows


def coverage_stats(datasets: dict[str, EvalDataset]) -> dict[str, Any]:
    """Per-domain dataset coverage summary."""
    total = sum(len(d.items) for d in datasets.values())
    by_domain: dict[str, dict[str, int]] = {}
    for name, dataset in datasets.items():
        for item in dataset.items:
            entry = by_domain.setdefault(item.domain, {"items": 0, "grounded": 0})
            entry["items"] += 1
            if item.grounded:
                entry["grounded"] += 1
    return {
        "files": sorted(datasets),
        "total_items": total,
        "by_domain": by_domain,
    }


def run_benchmark(
    dataset: EvalDataset,
    corpus: Corpus,
    top_k: int = 5,
    quick: bool = False,
    run_ablation_study: bool = True,
    run_ragas: bool = True,
    seed: int = 42,
) -> BenchmarkOutput:
    """Run the full offline benchmark over a dataset and return all outputs."""
    items = dataset.grounded_items() or dataset.items
    if quick:
        items = items[:3]

    start = time.perf_counter()
    systems = build_systems(corpus, with_answers=True)
    retrieval_rows, per_query = benchmark_retrieval(corpus, items, top_k, systems)
    explainability_rows = benchmark_explainability(corpus, items, top_k)

    ragas_rows: list[dict[str, Any]] = []
    if run_ragas:
        ragas_rows = benchmark_ragas(corpus, items, top_k, systems)

    ablation: dict[str, Any] = {}
    ablation_rows: list[dict[str, Any]] = []
    if run_ablation_study:
        ablation = run_ablation(corpus, items, top_k)
        ablation_rows = build_ablation_rows(ablation)

    elapsed = round(time.perf_counter() - start, 3)
    output = BenchmarkOutput(
        meta={
            "dataset": dataset.name,
            "document_id": dataset.document_id,
            "hierarchy_file": str(corpus.hierarchy_file),
            "items_evaluated": len(items),
            "items_total": len(dataset.items),
            "top_k": top_k,
            "seed": seed,
            "quick": quick,
            "node_count": corpus.node_count,
            "edge_count": corpus.edge_count,
            "elapsed_seconds": elapsed,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        retrieval=retrieval_rows,
        per_query=per_query,
        explainability=explainability_rows,
        ragas=ragas_rows,
        ablation=ablation,
        ablation_rows=ablation_rows,
    )
    return output


def benchmark_from_config(
    config: dict[str, Any],
    out_dir: str | Path | None = None,
    quick: bool = False,
    dataset_file: str | None = None,
) -> BenchmarkOutput:
    """Run the benchmark described by an experiment config."""
    ds_conf = config["dataset"]
    exp = config["experiment"]
    doc_id = ds_conf["document_id"]
    hierarchy_file = ds_conf.get("hierarchy_file")
    dataset_path = Path(dataset_file or ds_conf["gold_dir"])
    dataset = _load_primary_dataset(dataset_path, doc_id)
    corpus = build_corpus(
        document_id=doc_id,
        hierarchy_file=hierarchy_file,
        weights=exp.get("hybrid_weights"),
        confidence_threshold=exp.get("confidence_threshold"),
        embedding_dim=exp.get("embedding", {}).get("dim", 64),
        seed=exp.get("seed", 42),
    )
    try:
        return run_benchmark(
            dataset,
            corpus,
            top_k=exp.get("top_k", 5),
            quick=quick,
            run_ablation_study=bool(config.get("ablation", {}).get("variants")),
            run_ragas=True,
            seed=exp.get("seed", 42),
        )
    finally:
        corpus.close()


def _load_primary_dataset(gold_dir: str | Path, document_id: str) -> EvalDataset:
    from eval.dataset import load_gold_dataset

    gold_dir = Path(gold_dir)
    candidates: list[EvalDataset] = []
    for path in sorted(gold_dir.glob("*_gold.json")):
        dataset = load_gold_dataset(path)
        if dataset.document_id == document_id:
            candidates.append(dataset)
    if not candidates:
        raise FileNotFoundError(f"no gold dataset found under {gold_dir}")
    for dataset in candidates:
        if dataset.grounded_items():
            return dataset
    return candidates[0]
