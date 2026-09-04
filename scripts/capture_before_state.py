"""Capture the before-state of the hierarchy."""
import json

with open("data/hierarchy/0d1934142f67c5f5.json") as f:
    h = json.load(f)

nodes = h["nodes"]
total = len(nodes)
sections = [n for n in nodes if n["node_type"] == "section"]
chapters = [n for n in nodes if n["node_type"] == "chapter"]

print("=== BEFORE STATE ===")
print(f"Total hierarchy nodes: {total}")
print(f"Section nodes: {len(sections)}")
print(f"Chapter nodes: {len(chapters)}")
types = sorted(set(n["node_type"] for n in nodes))
print(f"All node types: {types}")
print()

for n in nodes:
    if "10" in n.get("numbering", "") and n["node_type"] == "section":
        print(f"  Section 10 standalone: {n['node_id']} - {n['title'][:60]}")
    if "72" in n.get("numbering", "") and n["node_type"] == "section":
        print(f"  Section 72 standalone: {n['node_id']} - {n['title'][:60]}")

for n in nodes:
    if n["node_type"] == "chapter":
        if "10. What" in n.get("text", "") or "10. What" in n.get("title", ""):
            print(f"  Section 10 EMBEDDED in {n['node_id']}")
        if "72. Liability" in n.get("text", "") or "72. Liability" in n.get("title", ""):
            print(f"  Section 72 EMBEDDED in {n['node_id']}")

print(f"Section numberings: {[n['numbering'] for n in sections]}")
