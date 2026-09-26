"""Semantic vs deterministic retrieval benchmark (V2.4.3).

Reports dense-only and final HHGR ranking quality for:

  1. the 9 concept queries (IPC theft/murder/robbery/rape/cheating,
     ICA offer/acceptance/consideration/breach) against gold section
     numbers per document, and
  2. the existing ``contract_act_gold`` evaluation queries (10 items)
     against gold citation numbers in the canonical ICA document.

Runs the exact production wiring (in-memory Qdrant + full canonical corpus)
twice: once with the deterministic provider, once with the configured
semantic model (``EMBEDDING_MODEL``, default ``BAAI/bge-m3``). Confidence,
evidence relevance, sufficiency, validity status and the grounding guard
decision are captured per query. Results are written to
``evaluation/embed_retrieval_comparison_v243.json``.

Usage:
    python scripts/benchmark_semantic_dense.py [--quick] [--model BAAI/bge-m3]
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import _bootstrap  # noqa: F401 -- prepares sys.path for src imports

from src.config.settings import settings
from src.embeddings import (
    EmbeddingService,
    HierarchyIndexer,
    QdrantStore,
    VectorRetriever,
    get_provider,
)
from src.knowledge_graph.canonical import canonical_doc_ids
from src.knowledge_graph.importer import import_all
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.llm.explanation import ExplainabilityEngine
from src.llm.service import QueryService

REPO = Path(__file__).resolve().parent.parent
settings.QA_INDEX_IN_MEMORY = True
logging.getLogger().setLevel(logging.WARNING)

IPC = "cf20a14c52127fd5"
ICA = "0d1934142f67c5f5"
ICA_GOLD_DOC = "0940d367554383c5"

CONCEPT_QUERIES: list[tuple[str, dict[str, list[str]]]] = [
    ("What is theft?", {IPC: ["378"]}),
    ("What is murder?", {IPC: ["300", "302"]}),
    ("What is robbery?", {IPC: ["390"]}),
    ("What is rape?", {IPC: ["375"]}),
    ("What is cheating?", {IPC: ["415", "420"]}),
    ("What is an offer?", {ICA: ["2"]}),
    ("What is acceptance?", {ICA: ["2", "7", "8"]}),
    ("What is consideration?", {ICA: ["2", "25", "185"]}),
    ("What is breach of contract?", {ICA: ["73", "74"]}),
]

# Existing gold evaluation queries (contract_act_gold): query -> expected
# citation numbering resolved against the canonical ICA document.
ICA_GOLD_QUERIES: list[tuple[str, list[str]]] = [
    ("What is the short title and commencement of the Indian Contract Act, 1892?", ["1"]),
    ("How is a contract defined under the Act?", ["2"]),
    ("What is a promise under the Act?", ["2"]),
    ("When is the communication of a proposal complete?", ["3"]),
    ("What does the Act say about the performance of contracts?", ["4"]),
    ("Which chapter of the Act deals with performance?", ["CHAPTER III", "4"]),
    ("Where are the preliminary provisions of the Act located?", ["CHAPTER I"]),
    ("What is an agreement enforceable by law called?", ["2"]),
    (
        "Does the Act require the parties to specify how a contract is to be performed, "
        "and what happens if they do not?",
        ["4"],
    ),
]

K_LIST = (1, 3, 5, 10)


def build_corpus_with(
    provider_name: str, allow_fallback: bool
) -> tuple[InMemoryGraph, EmbeddingService, QdrantStore, VectorRetriever, ExplainabilityEngine]:
    graph = InMemoryGraph()
    import_all(graph)
    provider = get_provider(
        model_name=provider_name,
        force_deterministic=False,
        batch_size=32,
        allow_fallback=allow_fallback,
        max_seq=settings.EMBEDDING_MAX_SEQUENCE_LENGTH,
    )
    service = EmbeddingService(provider=provider)
    store = QdrantStore(dim=service.dim, in_memory=True)
    store.ensure_collections()
    hierarchy_dir = REPO / "data" / "hierarchy"
    HierarchyIndexer(graph, store, service).index_graph(
        canonical_doc_ids=canonical_doc_ids(hierarchy_dir)
    )
    retriever = VectorRetriever(graph, store, service)
    engine = ExplainabilityEngine(graph, vector_retriever=retriever, expansion_enabled=True)
    engine.adaptive = False
    return graph, service, store, retriever, engine


def gold_nodes_by_number(graph: InMemoryGraph, doc: str, numbers: list[str]) -> set[str]:
    return {
        n["node_id"]
        for n in graph.all_nodes()
        if n.get("document_id") == doc and str(n.get("numbering", "")).strip() in set(numbers)
    }


def retrieve_metrics(relevant: set[str], ranked: list[str], k: int) -> dict:
    top_k = ranked[:k]
    hit = 1.0 if relevant.intersection(top_k) else 0.0
    mrr = 0.0
    for i, nid in enumerate(ranked, 1):
        if nid in relevant:
            mrr = 1.0 / i
            break
    recall = len(relevant.intersection(top_k)) / len(relevant) if relevant else 0.0
    return {"hit": round(hit, 4), "mrr": round(mrr, 4), "recall": round(recall, 4)}


def aggregate(rows: list[dict]) -> dict:
    n = max(1, len(rows))
    out = {}
    for key in rows[0]:
        out[key] = round(sum(r[key] for r in rows) / n, 4)
    out["n"] = len(rows)
    return out


def step_node_ids(res, kind: str) -> list[str]:
    for st in res.reasoning_chain:
        if st.kind == kind:
            return list(st.node_ids or [])
    return []


def short_label(graph: InMemoryGraph, hierarchy_cache: dict, nid: str) -> str:
    doc, _, local = nid.rpartition("__")
    num = None
    for n in hierarchy_cache.get(doc, {}).get("nodes", []):
        if n["node_id"] == local:
            num = str(n.get("numbering", "")).strip()
            break
    doc_short = {"cf20a14c52127fd5": "IPC", "0d1934142f67c5f5": "ICA"}.get(doc, doc[:6])
    return f"{doc_short}-{num or local}"


def run_provider(
    provider_name: str,
    allow_fallback: bool,
    quick: bool,
) -> dict:
    t0 = time.perf_counter()
    graph, service, store, retriever, engine = build_corpus_with(provider_name, allow_fallback)
    build_seconds = round(time.perf_counter() - t0, 1)

    hierarchy_dir = REPO / "data" / "hierarchy"
    hierarchy_cache: dict[str, dict] = {}
    for p in hierarchy_dir.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        hierarchy_cache[d["document_id"]] = d

    def run_query(query: str, gold: dict[str, list[str]] | list[str], label_fn) -> dict:
        if isinstance(gold, dict):
            relevant = set()
            for doc, numbers in gold.items():
                relevant |= gold_nodes_by_number(graph, doc, numbers)
        else:
            relevant = gold_nodes_by_number(graph, ICA, gold)
        res = engine.explain(query, top_k=10)
        dense = step_node_ids(res, "dense")[:10]
        grap = step_node_ids(res, "graph")[:10]
        final10 = [e.node_id for e in res.evidence[:10]]
        final5 = final10[:5]
        dense_metrics = {f"top{k}": retrieve_metrics(relevant, dense, k)["hit"] for k in K_LIST}
        dense_metrics["mrr"] = retrieve_metrics(relevant, dense, 10)["mrr"]
        dense_metrics.update(
            {f"r@{k}": retrieve_metrics(relevant, dense, k)["recall"] for k in (5, 10)}
        )
        final_metrics = {f"top{k}": retrieve_metrics(relevant, final10, k)["hit"] for k in K_LIST}
        final_metrics["mrr"] = retrieve_metrics(relevant, final10, 10)["mrr"]
        final_metrics.update(
            {f"r@{k}": retrieve_metrics(relevant, final10, k)["recall"] for k in (5, 10)}
        )
        guard = QueryService._should_generate_answer(res)
        return {
            "query": query,
            "dense_top10": [label_fn(nid) for nid in dense],
            "graph_top10": [label_fn(nid) for nid in grap],
            "final_top5": [label_fn(nid) for nid in final5],
            "dense_metrics": dense_metrics,
            "final_metrics": final_metrics,
            "confidence": round(res.confidence.score, 4),
            "relevance": round(res.evidence_relevance.score, 4),
            "sufficiency": round(res.validity.sufficiency_score, 4),
            "validity": res.validity.is_valid,
            "status": res.validity.status,
            "grounding": "GENERATE" if guard else "BLOCKED",
        }

    label_fn = lambda nid: short_label(graph, hierarchy_cache, nid)  # noqa: E731

    concept_rows = []
    for query, gold in CONCEPT_QUERIES:
        concept_rows.append(run_query(query, gold, label_fn))

    gold_rows = []
    for query, numbers in ICA_GOLD_QUERIES:
        gold_rows.append(run_query(query, numbers, label_fn))

    def summarize(rows, metrics_key):
        return aggregate([r[metrics_key] for r in rows])

    return {
        "provider": provider_name,
        "dim": service.dim,
        "nodes_indexed": sum(store.count(c) for c in store.collections),
        "build_seconds": build_seconds,
        "concepts": {
            "rows": concept_rows,
            "dense_agg": summarize(concept_rows, "dense_metrics"),
            "final_agg": summarize(concept_rows, "final_metrics"),
        },
        "ica_gold": {
            "rows": gold_rows,
            "dense_agg": summarize(gold_rows, "dense_metrics"),
            "final_agg": summarize(gold_rows, "final_metrics"),
        },
    }


def print_tables(results: dict) -> None:
    for group, title in (
        ("concepts", "Concept queries (9)"),
        ("ica_gold", "ICA gold dataset (9 lookup queries)"),
    ):
        block = results[group]
        print(f"\n=== {title} ===")
        print(
            f"\n{results['provider']} DENSE:   "
            + "  ".join(
                f"{k}={block['dense_agg'].get(k)}"
                for k in ("top1", "top3", "top5", "mrr", "r@5", "r@10")
            )
        )
        print(
            f"{results['provider']} FINAL:  "
            + "  ".join(
                f"{k}={block['final_agg'].get(k)}"
                for k in ("top1", "top3", "top5", "mrr", "r@5", "r@10")
            )
        )
        for row in block["rows"]:
            print(
                f"    {row['query'][:48]:<50} D{row['dense_metrics']} F{row['final_metrics']} "
                f"conf={row['confidence']} rel={row['relevance']} "
                f"suff={row['sufficiency']} {row['grounding']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="only concept query set")
    parser.add_argument(
        "--model", default=settings.EMBEDDING_MODEL, help="semantic model (default EMBEDDING_MODEL)"
    )
    parser.add_argument("--suffix", default="v243")
    parser.add_argument(
        "--only", default=None, help="run a single provider: deterministic or the --model name"
    )
    args = parser.parse_args()

    providers = ["deterministic", args.model]
    if args.only:
        providers = [args.only]
    results = {}
    for provider in providers:
        print(f"\n>>> Building corpus with provider {provider!r} ...", flush=True)
        results[provider] = run_provider(provider, allow_fallback=False, quick=args.quick)

    out_dir = REPO / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"embed_retrieval_comparison_{args.suffix}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")

    for provider, block in results.items():
        print_tables(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
