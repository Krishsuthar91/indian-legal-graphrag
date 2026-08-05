"""Demo: Embedding & Vector Retrieval Layer — Qdrant + hybrid dense/graph/hierarchy.

Uses the deterministic embedding provider so no model download is needed.
Swap EMBEDDING_MODEL (e.g. BAAI/bge-m3) for real multilingual vectors.
"""

import sys
from pathlib import Path

from src.config.settings import settings
from src.embeddings import (
    EmbeddingService,
    HierarchyIndexer,
    QdrantStore,
    VectorRetriever,
    benchmark_retrieval,
    format_report,
    get_provider,
)
from src.knowledge_graph.importer import import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph

QUERIES = [
    "what does the act say about performance of contracts",
    "section 4 performance",
    "how is a contract defined",
    "communication of proposals",
    "अनुबंध प्रदर्शन",  # "contract performance" (Hindi) — exercises the multilingual path
]


def _find_hierarchy_file() -> Path | None:
    h_dir = Path("data/hierarchy")
    if not h_dir.exists():
        return None
    files = sorted(h_dir.glob("*.json"))
    return files[0] if files else None


def _print_hits(hits, top_k: int = 5) -> None:
    if not hits:
        print("    (no results)")
        return
    for i, h in enumerate(hits[:top_k], 1):
        title = h.payload.get("title") or h.node_id
        print(f"\n  {i}. {title}  (score={h.score:.3f})")
        print(f"      collection: {h.collection}  node_id: {h.node_id}")
        print(f"      level: {h.payload.get('level')}  language: {h.payload.get('language')!r}")
        text = h.payload.get("text", "")
        if text:
            print(f"      text: {text[:120].strip()}...")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    h_file = _find_hierarchy_file()
    if not h_file:
        print("No hierarchy files found in data/hierarchy/. Run demo_hierarchy.py first.")
        exit(1)

    print(f"Using hierarchy : {h_file}")
    print(f"Configured model: {settings.EMBEDDING_MODEL}")

    # 1. Build the knowledge graph from hierarchy JSON
    print("\n[1] Building knowledge graph...")
    graph = InMemoryGraph()
    counts = import_hierarchy_json(graph, h_file)
    print(f"    Nodes: {counts['nodes_created']}, Edges: {counts['edges_created']}")

    # 2. Embedding service + vector store
    print("\n[2] Embedding service & Qdrant vector store")
    provider = get_provider(model_name=settings.EMBEDDING_MODEL, force_deterministic=True)
    service = EmbeddingService(provider=provider)
    store = QdrantStore(dim=service.dim, in_memory=True)
    store.ensure_collections()
    print(f"    provider : {provider.name}  dim={service.dim}")
    print(f"    qdrant   : in-memory  collections={list(store.collections)}")

    # 3. Index the graph
    print("\n[3] Indexing graph nodes into collections")
    indexer = HierarchyIndexer(graph, store, service)
    result = indexer.index_graph()
    print(f"    doc_id: {result['doc_id']}")
    for collection, n in result["collections"].items():
        print(f"    {collection:<12} {n} points")
    total = sum(store.count(c) for c in store.collections)
    print(f"    total points: {total}")

    # 4. Incremental re-index (no changes -> everything skipped)
    print("\n[4] Incremental re-index")
    inc = indexer.index_incremental()
    print(f"    indexed={inc['indexed']}  skipped={inc['skipped']}")

    # 5. Multilingual dense retrieval
    print("\n[5] Dense multilingual retrieval")
    retriever = VectorRetriever(graph, store, service)
    for raw in QUERIES[:3]:
        print(f"\n  QUERY: {raw}")
        hits = retriever.dense_search(raw, top_k=5)
        _print_hits(hits)

    # 6. Hybrid retrieval (dense + graph + hierarchy)
    print("\n[6] Hybrid retrieval (dense + graph + hierarchy)")
    for raw in QUERIES[:3]:
        print(f"\n  QUERY: {raw}")
        hits = retriever.hybrid_retrieve(raw, top_k=5)
        for i, h in enumerate(hits, 1):
            print(f"  {i}. {h.title or h.node_id}  (score={h.score:.3f})")
            print(f"      dense={h.dense_score:.2f} graph={h.graph_score:.2f} "
                  f"hierarchy={h.hierarchy_score:.2f} sources={h.sources}")

    # 7. Benchmark
    print("\n[7] Retrieval benchmark")
    reports = benchmark_retrieval(retriever, QUERIES, top_k=5)
    print(format_report(reports))

    store.close()
    print("\nDone.")
