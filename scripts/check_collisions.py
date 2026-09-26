import json
import pathlib

import _bootstrap  # noqa: F401 -- prepares sys.path for src imports

hierarchy_dir = pathlib.Path("data/hierarchy")
# Find which files have n_0018
for f in sorted(hierarchy_dir.glob("*.json")):
    d = json.load(open(f, encoding="utf-8"))
    nodes = d.get("nodes", [])
    for n in nodes:
        if n.get("node_id") == "n_0018":
            doc_id = d.get("document_id", "?")
            print(
                f"File: {f.name} (doc={doc_id[:12]}) n_0018 = "
                f"num={n.get('numbering', '?')} title={n.get('title', '')[:50]}"
            )
            break
