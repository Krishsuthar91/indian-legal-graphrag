"""Rebuild all retrieval assets from the corrected hierarchy."""
from pathlib import Path

from src.config.settings import settings
from src.embeddings import EmbeddingService, HierarchyIndexer, QdrantStore, get_provider
from src.knowledge_graph.importer import import_hierarchy_json
from src.knowledge_graph.neo4j_driver import InMemoryGraph

HIERARCHY_FILE = Path("data/hierarchy/0d1934142f67c5f5.json")

print("=" * 60)
print("REBUILDING ALL RETRIEVAL ASSETS")
print("=" * 60)

# 1. Knowledge Graph
print("\n[1] Building knowledge graph from corrected hierarchy...")
graph = InMemoryGraph()
counts = import_hierarchy_json(graph, HIERARCHY_FILE)
print(f"    Graph nodes: {counts['nodes_created']}")
print(f"    Graph edges: {counts['edges_created']}")

# 2. Embedding service + vector store
print("\n[2] Initializing embedding service & Qdrant store...")
provider = get_provider(model_name=settings.EMBEDDING_MODEL, force_deterministic=True)
service = EmbeddingService(provider=provider)
store = QdrantStore(dim=service.dim, in_memory=True)
store.ensure_collections()
print(f"    Provider: {provider.name} dim={service.dim}")
print(f"    Qdrant collections: {list(store.collections)}")

# 3. Index hierarchy
print("\n[3] Indexing hierarchy nodes into vector collections...")
indexer = HierarchyIndexer(graph, store, service)
result = indexer.index_hierarchy_file(HIERARCHY_FILE)
print(f"    doc_id: {result['doc_id']}")
for collection, n in result["collections"].items():
    print(f"    {collection:<20} {n} points")
total = sum(store.count(c) for c in store.collections)
print(f"    Total points indexed: {total}")

# 4. Verify Section 10 and 72
print("\n[4] Verifying Section 10 and Section 72...")
import json
with open(HIERARCHY_FILE) as f:
    h = json.load(f)
sec10 = [n for n in h["nodes"] if n.get("numbering") == "10" and n["node_type"] == "section"]
sec72 = [n for n in h["nodes"] if n.get("numbering") == "72" and n["node_type"] == "section"]
print(f"    Section 10: {'FOUND as standalone' if sec10 else 'MISSING'} ({sec10[0]['node_id'] if sec10 else 'N/A'})")
print(f"    Section 72: {'FOUND as standalone' if sec72 else 'MISSING'} ({sec72[0]['node_id'] if sec72 else 'N/A'})")

# 5. Parent-child verification
print("\n[5] Verifying parent-child relationships...")
node_map = {n["node_id"]: n for n in h["nodes"]}
broken = 0
for n in h["nodes"]:
    pid = n.get("parent_id")
    if pid and pid in node_map:
        parent = node_map[pid]
        if n["node_id"] not in parent.get("children", []):
            broken += 1
    elif pid and pid not in node_map:
        broken += 1
print(f"    Broken relationships: {broken}")

store.close()
print("\n" + "=" * 60)
print("REBUILD COMPLETE")
print("=" * 60)
