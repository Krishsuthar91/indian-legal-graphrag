"""Demo: Hybrid Hierarchical Graph Retrieval (HHGR) over the knowledge graph."""

from pathlib import Path

from src.knowledge_graph.importer import import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.retrieval import RetrievalQuery, parse_query, retrieve

QUERIES = [
    "what does the act say about performance of contracts",
    "section 4 performance",
    "how is a contract defined",
    "communication of proposals",
    "what does section 2 mean by definitions",
]


def _find_hierarchy_file() -> Path | None:
    h_dir = Path("data/hierarchy")
    if not h_dir.exists():
        return None
    files = sorted(h_dir.glob("*.json"))
    return files[0] if files else None


def _print_query(q: RetrievalQuery) -> None:
    print(f"  keywords      : {q.keywords}")
    if q.section_refs:
        print(f"  section refs  : {q.section_refs}")
    if q.section_numbers:
        print(f"  section nums  : {q.section_numbers}")


def _print_results(results) -> None:
    if not results:
        print("    (no results)")
        return
    for i, r in enumerate(results, 1):
        marker = "*" if r.is_seed else " "
        title = r.title or r.node_id
        print(f"\n  {i}. [{marker}] {title}  (score={r.score:.3f})")
        print(f"      label: {r.label}  numbering: {r.numbering!r}")
        print(f"      signals: text={r.signals['text']:.2f} "
              f"hierarchy={r.signals['hierarchy']:.2f} "
              f"citation={r.signals['citation']:.2f} "
              f"structural={r.signals['structural']:.2f}")
        if r.matched_keywords:
            print(f"      matched: {r.matched_keywords}")
        if r.path:
            print(f"      path: {' <- '.join(r.path)}")
        if r.text:
            print(f"      text: {r.text[:120].strip()}...")


if __name__ == "__main__":
    h_file = _find_hierarchy_file()
    if not h_file:
        print("No hierarchy files found in data/hierarchy/. Run demo_hierarchy.py first.")
        exit(1)

    print(f"Using hierarchy: {h_file}")

    # 1. Build the knowledge graph from hierarchy JSON
    print("\n[1] Building knowledge graph...")
    graph = InMemoryGraph()
    counts = import_hierarchy_json(graph, h_file)
    print(f"    Nodes: {counts['nodes_created']}, Edges: {counts['edges_created']}")

    # 2. Run hybrid retrieval queries
    print("\n[2] Hybrid Hierarchical Graph Retrieval")
    for raw in QUERIES:
        print(f"\n{'='*60}")
        print(f"QUERY: {raw}")
        print(f"{'='*60}")
        query = parse_query(raw)
        _print_query(query)
        results = retrieve(graph, query, top_k=5)
        _print_results(results)
