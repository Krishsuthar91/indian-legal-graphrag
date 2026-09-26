import json

import _bootstrap  # noqa: F401 -- prepares sys.path for src imports

from src.llm.service import build_default_graph

# Load the ICA hierarchy file
d = json.load(open("data/hierarchy/0d1934142f67c5f5.json", encoding="utf-8"))
nodes = d["nodes"]

# Find the actual Section 10
sec10 = [n for n in nodes if n.get("numbering") == "10"]
print("Section 10 in hierarchy JSON:")
for n in sec10:
    print("  node_id:", n["node_id"])
    print("  title:", n.get("title", "")[:60])
    print("  node_type:", n.get("node_type", ""))
    print("  parent_id:", n.get("parent_id", ""))

# Check n_0018
n0018 = [n for n in nodes if n["node_id"] == "n_0018"]
print("\nn_0018 in hierarchy JSON:")
for n in n0018:
    print("  numbering:", n.get("numbering", ""))
    print("  title:", n.get("title", "")[:60])
    print("  node_type:", n.get("node_type", ""))

# Now build graph and check the SAME node_id
graph = build_default_graph()
g_sec10 = graph.get_node("n_0018")
print("\nn_0018 in GRAPH:")
if g_sec10:
    print("  numbering:", g_sec10.get("numbering", "")[:60])
    print("  title:", g_sec10.get("title", "")[:60])
    print("  label:", g_sec10.get("label", ""))
    print("  document_id:", g_sec10.get("document_id", ""))
    print("  ALL KEYS:", list(g_sec10.keys()))

# Find the actual Section 10 node_id in graph
ica_doc_id = "0d1934142f67c5f5"
ica_nodes = [n for n in graph.all_nodes() if n.get("document_id") == ica_doc_id]
print("\nICA nodes in graph:", len(ica_nodes))
# Find one with numbering that looks like section 10
for n in ica_nodes:
    if n.get("numbering", "").strip() == "10":
        print("  FOUND numbering=10:", n.get("node_id"), n.get("title", "")[:50])
        break
else:
    print("  No node with numbering='10' found among ICA nodes")
    # Show a few ICA section nodes
    secs = [n for n in ica_nodes if n.get("label") == "Section"]
    print("  ICA Section nodes:", len(secs))
    for s in secs[:5]:
        print(
            f"    id={s['node_id']} num={s.get('numbering', '')[:30]} "
            f"title={s.get('title', '')[:40]}"
        )
