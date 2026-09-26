import json
from collections import Counter

import _bootstrap  # noqa: F401 -- prepares sys.path for src imports

from src.llm.service import build_default_graph

d = json.load(open("data/hierarchy/0d1934142f67c5f5.json", encoding="utf-8"))
nodes = d["nodes"]
print("Total nodes:", len(nodes))
with_num = [n for n in nodes if n.get("numbering")]
print("Nodes with numbering:", len(with_num))
sec10 = [n for n in nodes if n.get("numbering") == "10"]
print("Section 10:", len(sec10))
if sec10:
    n = sec10[0]
    print("  node_id:", n["node_id"])
    print("  title:", n.get("title", "")[:80])
    print("  text:", n.get("text", "")[:150])
    print("  node_type:", n.get("node_type", ""))
print()
print("All nodes with numbering:")
for n in with_num:
    num = n["numbering"]
    ntype = n.get("node_type", "?")
    title = n.get("title", "")[:50]
    print(f"  num={num:6s} type={ntype:12s} title={title}")
print()
# Check what labels graph nodes have
graph = build_default_graph()
all_nodes = [n for n in graph.all_nodes() if n.get("node_id")]
print("Graph node count:", len(all_nodes))
labels = Counter(n.get("label", "?") for n in all_nodes)
print("Graph labels:", dict(labels))
# Check if any graph nodes have numbering
with_num_graph = [n for n in all_nodes if n.get("numbering")]
print("Graph nodes with numbering:", len(with_num_graph))
# Check IPC document
ipc_nodes = [n for n in all_nodes if n.get("document_id") == "2062cb82a313930e"]
print("IPC nodes with document_id:", len(ipc_nodes))
# Check how many graph nodes have document_id at all
with_doc = [n for n in all_nodes if n.get("document_id")]
print("Graph nodes with document_id:", len(with_doc))
without_doc = [n for n in all_nodes if not n.get("document_id")]
print("Graph nodes WITHOUT document_id:", len(without_doc))
# Sample some without doc_id
for n in without_doc[:5]:
    print(
        f"  id={n['node_id'][:20]:20s} label={n.get('label', '?'):12s} "
        f"title={n.get('title', '')[:40]}"
    )
