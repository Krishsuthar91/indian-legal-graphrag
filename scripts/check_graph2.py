import sys, pathlib
sys.path.insert(0, str(pathlib.Path('.').resolve()))
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
    print("  id=%s label=%s num=%s doc=%s title=%s" % (nid, label, num, docid[:12], title))
# Count nodes with numbering
with_num = [n for n in nodes if n.get("numbering")]
print("Nodes with numbering:", len(with_num))
# Count by document_id
from collections import Counter
doc_counts = Counter(n.get("document_id", "NONE")[:12] for n in nodes)
for doc, count in doc_counts.most_common(10):
    print("  doc=%s count=%d" % (doc, count))
