"""Diagnostic trace for 'What is Section 10?' pipeline."""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src.retrieval.query import parse_query
from src.retrieval.ranker import TEXT_THRESHOLD
from src.retrieval.ranker import retrieve
from src.retrieval.context import propagate_hierarchy
from src.retrieval.scorer import text_score, citation_score, structural_importance, combine_signals
from src.llm.service import build_default_graph

ICA_DOC = "0d1934142f67c5f5"

# ── Stage 1: Query parsing ──
print("=" * 70)
print("STAGE 1: Parsed Query")
print("=" * 70)
q = parse_query("What is Section 10?")
for attr in ("raw", "keywords", "section_refs", "section_numbers",
             "citation_texts", "act_name", "document_id", "language"):
    print(f"  {attr}: {getattr(q, attr)!r}")
print()

# ── Stage 2: Graph overview ──
print("=" * 70)
print("STAGE 2: Graph Overview")
print("=" * 70)
graph = build_default_graph()
all_nodes = [n for n in graph.all_nodes() if n.get("node_id")]
ica_nodes = [n for n in all_nodes if n.get("document_id") == ICA_DOC]
print(f"  Total nodes: {len(all_nodes)}")
print(f"  ICA nodes:   {len(ica_nodes)}")
print(f"  Other nodes: {len(all_nodes) - len(ica_nodes)}")

# Show all node types in ICA
from collections import Counter
types = Counter(n.get("label", "?") for n in ica_nodes)
print(f"  ICA node types: {dict(types)}")

# Find Section 10
sec10_list = [n for n in ica_nodes if n.get("numbering") == "10"]
print(f"\n  Nodes with numbering='10' in ICA: {len(sec10_list)}")
for sn in sec10_list:
    print(f"    node_id={sn['node_id']}  label={sn.get('label','')}  title={sn.get('title','')[:50]}")

# Find Section 10 across ALL docs
sec10_all = [n for n in all_nodes if n.get("numbering") == "10"]
print(f"  Nodes with numbering='10' across ALL docs: {len(sec10_all)}")
for sn in sec10_all[:5]:
    print(f"    node_id={sn['node_id']}  doc={sn.get('document_id','?')[:12]}  label={sn.get('label','')}  title={sn.get('title','')[:40]}")
print()

# ── Stage 3: Seed selection ──
print("=" * 70)
print("STAGE 3: Seed Selection (text_score >= 0.25 OR citation_score >= 1.0)")
print("=" * 70)
seeds = []
for node in ica_nodes:
    t = text_score(node, q)
    c = citation_score(node, q)
    if t >= TEXT_THRESHOLD or c >= 1.0:
        seeds.append((node["node_id"], node.get("numbering", ""),
                      node.get("label", ""), node.get("title", ""), t, c))
seeds.sort(key=lambda x: (-x[5], -x[4], x[1]))
print(f"  Total seeds from ICA: {len(seeds)}")
for sid, num, lbl, title, t, c in seeds[:25]:
    print(f"    num={num:5s}  text={t:.3f}  cite={c:.1f}  label={lbl:15s}  id={sid}  title={title[:40]}")
print()

# ── Stage 4: Graph retrieval (no filter) ──
print("=" * 70)
print("STAGE 4a: Graph Retrieval (no document filter)")
print("=" * 70)
graph_results = retrieve(graph, "What is Section 10?", top_k=15)
for i, r in enumerate(graph_results):
    node = graph.get_node(r.node_id)
    doc = node.get("document_id", "?") if node else "?"
    print(f"  #{i+1:2d} score={r.score:.4f} num={r.numbering:5s} label={r.label:15s} doc={doc[:12]}  id={r.node_id}  title={r.title[:40]}")
    print(f"       signals={r.signals}  is_seed={r.is_seed}")
print()

# ── Stage 4b: Graph retrieval (filtered) ──
print("=" * 70)
print("STAGE 4b: Graph Retrieval (document_id filtered to ICA)")
print("=" * 70)
graph_results_f = retrieve(graph, "What is Section 10?", top_k=15, document_id=ICA_DOC)
for i, r in enumerate(graph_results_f):
    print(f"  #{i+1:2d} score={r.score:.4f} num={r.numbering:5s} label={r.label:15s}  id={r.node_id}  title={r.title[:40]}")
    print(f"       signals={r.signals}  is_seed={r.is_seed}")
print()

# ── Stage 5: Hierarchy propagation ──
print("=" * 70)
print("STAGE 5: Hierarchy Propagation from seeds")
print("=" * 70)
seed_ids = [s[0] for s in seeds]
propagated = propagate_hierarchy(graph, seed_ids)
# Sort by evidence strength
prop_sorted = sorted(propagated.items(), key=lambda x: (-x[1], x[0]))
print(f"  Propagated nodes: {len(propagated)}")
for nid, strength in prop_sorted[:30]:
    node = graph.get_node(nid)
    if node:
        print(f"    strength={strength:.4f} num={node.get('numbering',''):5s} label={node.get('label',''):15s} id={nid}  title={node.get('title','')[:40]}")
print("  ...")
for nid, strength in prop_sorted[-5:]:
    node = graph.get_node(nid)
    if node:
        print(f"    strength={strength:.4f} num={node.get('numbering',''):5s} label={node.get('label',''):15s} id={nid}  title={node.get('title','')[:40]}")
print()

# ── Stage 6: Detailed scoring for top candidates ──
print("=" * 70)
print("STAGE 6: Detailed Scoring for Section 10 vs Top Candidates")
print("=" * 70)
# Get all candidates from propagation, score them
structural_scores = {}
for nid in propagated:
    node = graph.get_node(nid)
    if node:
        structural_scores[nid] = structural_importance(graph, node)
max_struct = max(structural_scores.values()) if structural_scores else 1.0

scored = []
for nid in propagated:
    node = graph.get_node(nid)
    if not node:
        continue
    per = {}
    for gr in graph_results_f:
        if gr.node_id == nid:
            per = gr.signals
            break
    signals = {
        "text": per.get("text", 0.0),
        "hierarchy": propagated[nid],
        "citation": per.get("citation", 0.0),
        "structural": (structural_scores.get(nid, 0.0) / max_struct) if max_struct > 0 else 0.0,
    }
    final = combine_signals(signals)
    scored.append((nid, node.get("numbering", ""), node.get("label", ""),
                   node.get("title", ""), final, signals))

scored.sort(key=lambda x: (-x[4], x[0]))
print(f"  Total scored candidates: {len(scored)}")
print(f"  {'#':>3s}  {'final':>6s}  {'text':>5s}  {'hier':>5s}  {'cite':>5s}  {'struct':>5s}  {'num':>5s}  {'label':15s}  title")
for i, (nid, num, lbl, title, final, sig) in enumerate(scored[:20]):
    print(f"  {i+1:3d}  {final:6.4f}  {sig['text']:5.3f}  {sig['hierarchy']:5.3f}  {sig['citation']:5.3f}  {sig['structural']:5.3f}  {num:5s}  {lbl:15s}  {title[:35]}")

# Find Section 10 specifically
print()
sec10_scored = [s for s in scored if s[1] == "10"]
if sec10_scored:
    s = sec10_scored[0]
    print(f"  *** Section 10 ***")
    print(f"      node_id={s[0]}  final={s[4]:.4f}  label={s[2]}")
    print(f"      signals: {s[5]}")
    rank_pos = next((i+1 for i, x in enumerate(scored) if x[0] == s[0]), None)
    print(f"      rank position: #{rank_pos} of {len(scored)}")
else:
    print("  *** Section 10 NOT in scored candidates ***")
print()
