import _bootstrap  # noqa: F401 -- prepares sys.path for src imports

from src.llm.service import build_default_graph

graph = build_default_graph()
nodes = [n for n in graph.all_nodes() if n.get("node_id")]
# Check a few ICA section nodes by ID
ica_sec = graph.get_node("n_0018")  # Section 10
if ica_sec:
    print("Section 10 (n_0018):")
    for k, v in ica_sec.items():
        print(f"  {k} = {str(v)[:80]}")
else:
    print("Section 10 (n_0018) NOT FOUND")

# Check another
ica_sec23 = graph.get_node("n_0036")
if ica_sec23:
    print("\nSection 23 (n_0036):")
    for k, v in ica_sec23.items():
        print(f"  {k} = {str(v)[:80]}")
else:
    print("\nSection 23 (n_0036) NOT FOUND")

# Check IPC section
ipc = graph.get_node("cf20a14c52127fd5")
if ipc:
    print("\nIPC Document:")
    for k, v in ipc.items():
        print(f"  {k} = {str(v)[:80]}")

# Count how many section nodes lack document_id
secs = [n for n in nodes if n.get("label") == "Section"]
secs_with_doc = [n for n in secs if n.get("document_id")]
secs_no_doc = [n for n in secs if not n.get("document_id")]
print("\nSections total:", len(secs))
print("Sections WITH document_id:", len(secs_with_doc))
print("Sections WITHOUT document_id:", len(secs_no_doc))
if secs_no_doc:
    print("Sample WITHOUT doc_id:")
    for n in secs_no_doc[:3]:
        print(
            f"  id={n.get('node_id', '?')} num={n.get('numbering', '?')} "
            f"title={n.get('title', '')[:40]}"
        )
