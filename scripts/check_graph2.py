from collections import Counter

import _bootstrap  # noqa: F401 -- prepares sys.path for src imports

from src.llm.service import build_default_graph

graph = build_default_graph()
nodes = [n for n in graph.all_nodes() if n.get("node_id")]
ica = [n for n in nodes if n.get("document_id") == "0d1934142f67c5f5"]
print("Total:", len(nodes), "ICA:", len(ica))
for n in ica[:5]:
    nid = n["node_id"]
    label = n.get("label", "")
    num = n.get("numbering", "NONE")
    title = n.get("title", "")[:50]
    docid = n.get("document_id", "MISSING")
    print(f"  id={nid} label={label} num={num} doc={docid[:12]} title={title}")
# Count nodes with numbering
with_num = [n for n in nodes if n.get("numbering")]
print("Nodes with numbering:", len(with_num))
# Count by document_id
doc_counts = Counter(n.get("document_id", "NONE")[:12] for n in nodes)
for doc, count in doc_counts.most_common(10):
    print(f"  doc={doc} count={count}")
