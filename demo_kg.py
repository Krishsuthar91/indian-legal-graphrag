"""Demo: build a Knowledge Graph from hierarchy JSON."""

from pathlib import Path

from src.knowledge_graph.entity_resolver import resolve_duplicates
from src.knowledge_graph.importer import import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph
from src.knowledge_graph.schema import NodeLabel
from src.knowledge_graph.stats import export_stats
from src.knowledge_graph.traversal import (
    citation_chain,
    get_children,
    get_parent,
)


def _find_hierarchy_file() -> Path | None:
    h_dir = Path("data/hierarchy")
    if not h_dir.exists():
        return None
    files = sorted(h_dir.glob("*.json"))
    return files[0] if files else None


def _print_graph(g):
    print(f"\n{'='*60}")
    print("GRAPH NODES")
    print(f"{'='*60}")
    for label in NodeLabel:
        nodes = g.get_nodes_by_label(label.value)
        if nodes:
            print(f"\n  {label.value} ({len(nodes)}):")
            for n in nodes[:5]:
                title = n.get("title") or n.get("name") or n.get("citation") or n.get("node_id")
                print(f"    - {title}")

    print(f"\n{'='*60}")
    print("GRAPH EDGES")
    print(f"{'='*60}")
    from src.knowledge_graph.schema import RelType
    for rel in RelType:
        count = g.edge_count(rel.value)
        if count > 0:
            print(f"  {rel.value}: {count}")


if __name__ == "__main__":
    h_file = _find_hierarchy_file()
    if not h_file:
        print("No hierarchy files found in data/hierarchy/. Run demo_hierarchy.py first.")
        exit(1)

    print(f"Using hierarchy: {h_file}")

    # 1. Create graph
    graph = InMemoryGraph()

    # 2. Import
    print("\n[1] Importing hierarchy into graph...")
    counts = import_hierarchy_json(graph, h_file)
    print(f"    Nodes created: {counts['nodes_created']}")
    print(f"    Edges created: {counts['edges_created']}")

    # 3. Resolve duplicates
    print("\n[2] Resolving duplicate entities...")
    for label in [NodeLabel.COURT.value, NodeLabel.LEGAL_CONCEPT.value]:
        merged = resolve_duplicates(graph, label, "name")
        if merged:
            print(f"    Merged {merged} duplicate {label} nodes")

    # 4. Show graph
    _print_graph(graph)

    # 5. Traversal demo
    doc_id = h_file.stem
    print(f"\n{'='*60}")
    print("TRAVERSAL DEMO")
    print(f"{'='*60}")

    parent = get_parent(graph, "n3") if graph.get_node("n3") else None
    if parent:
        print(f"\n  Parent of n3: {parent.get('title', parent.get('node_id'))}")

    children = get_children(graph, doc_id)
    print(f"  Children of document: {[c.get('title', c['node_id']) for c in children]}")

    # 6. Citation chain
    for node in graph.get_nodes_by_label("Section"):
        nid = node["node_id"]
        chain = citation_chain(graph, nid)
        if chain:
            print(f"\n  Citation chain from {nid}:")
            for item in chain[:5]:
                n = item["node"]
                title = n.get("title") or n.get("name") or n.get("citation")
                print(f"    -> {title} (depth {item['depth']}, via {item['rel_type']})")

    # 7. Stats
    print(f"\n{'='*60}")
    print("GRAPH STATISTICS")
    print(f"{'='*60}")
    stats = export_stats(graph, Path("data/graph_stats.json"))
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\nStats saved to data/graph_stats.json")
