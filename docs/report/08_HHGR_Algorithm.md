# 08 — HHGR Algorithm

**HHGR = Hybrid Hierarchical Graph Retrieval.** This document gives a formal specification of
the algorithm, its signal definitions, its parameters, its pseudo-code, and its complexity. It
is the technical core of the project.

Primary sources: `src/retrieval/scorer.py`, `src/retrieval/ranker.py`,
`src/retrieval/context.py`, `src/embeddings/retriever.py`.

---

## 8.1 Motivation

Flat vector retrieval ranks provisions by semantic similarity to the query. In law this is
insufficient because: (a) legal meaning is carried by **structure** (a definition in §2 governs
every later use of the term), (b) provisions **cite** other provisions, and (c) some sections
are intrinsically more important to a query type (definitions for "what is", penalty sections
for "punishment"). HHGR makes those non-semantic signals **first-class inputs to ranking**.

---

## 8.2 Formal model

### 8.2.1 The legal graph

Let the corpus be a directed graph

```text
G = (V, E),   V = ⋃_d V_d
```

where each vertex `v ∈ V` is a legal unit (Document, Chapter, Section, or Clause), and edges
`E` are:

```text
E = E_PART_OF  ∪  E_CITES  ∪  E_REFERENCES
```

- `E_PART_OF` — structural containment (child → parent).
- `E_CITES` — explicit cross-references between provisions.
- `E_REFERENCES` — weaker references.

Each vertex carries `text(v)`, `level(v) ∈ {doc, chapter, section, clause}`,
`number(v)`, and `document(v)`.

### 8.2.2 Query

A query `q` is parsed into

```text
q = (t, T, R, a, i)
```

where `t` = normalised text, `T` = token set, `R` = explicitly referenced section numbers,
`a` = detected Act (or ∅), and `i` = intent label.

---

## 8.3 The four HHGR signals

For a candidate vertex `v` and query `q`:

### (1) Text signal `S_text(v, q)`
Semantic/lexical relevance of the node text to the query, combining dense cosine similarity and
token-overlap:

```text
S_text(v, q) = λ · cos(e(v), e(q)) + (1 − λ) · overlap(T, tokens(v))
```

where `e(·)` is the embedding function and `overlap` is a normalised legal-aware token
overlap.

### (2) Citation signal `S_citation(v, q)`
Rewards nodes that cite, or are cited by, the query's anchor sections:

```text
S_citation(v, q) = max over anchor a∈R∪seeds of  f( dist_cite(v, a) )
```

where `dist_cite` is graph distance over `E_CITES` and `f` is a decreasing kernel
(e.g. `f(0)=1`, halving per hop). Nodes with no citation relation score `0`.

### (3) Hierarchy signal `S_hierarchy(v, q)`
Rewards nodes structurally close to anchors within the same document:

```text
S_hierarchy(v, q) = g( dist_partof(v, A) ) · sameDocument(v, A)
```

where `A` is the set of anchor nodes, `dist_partof` is distance over `E_PART_OF`, and the
`sameDocument` guard prevents cross-Act leakage.

### (4) Structural signal `S_struct(v)`
Intrinsic importance of the node, query-independent (with intent modulation):

```text
S_struct(v) = σ( i1·isDefinition(v) + i2·isPenalty(v)
               + i3·degreeCentrality(v) + i4·isChapterHeader(v) )
```

where `isDefinition`/`isPenalty` are lexical markers ("means", "shall be punished",
"defined in") and `degreeCentrality` counts incident `CITES`/`PART_OF` edges. Intent `i`
modulates the coefficients (definitions up-weighted for definitional queries, penalties up for
penalty queries).

### HHGR graph score

```text
H(v, q) = α · S_text(v, q) + β · S_citation(v, q)
        + γ · S_hierarchy(v, q) + δ · S_struct(v)
```

with default `α + β + γ + δ = 1`. This `H(v, q)` is emitted as the **graph signal** of the
retrieval fusion layer.

---

## 8.4 Hierarchy propagation

Seeds `S₀ ⊆ V` are expanded to a context set:

```text
Prop(S₀) = S₀ ∪ ancestors(S₀) ∪ descendants(S₀) ∪ siblings(S₀)
```

with decayed contribution:

```text
H_prop(x) = max_{s ∈ S₀} H(s, q) · ρ^{dist_partof(x, s)}
```

`ρ ∈ (0,1)` is the propagation decay (default ≈ 0.5). Propagation is bounded to
`document(s)` for every seed `s`.

---

## 8.5 Retrieval fusion

The three top-level signals are fused:

```text
F(v, q) = w_d · D(v, q) + w_g · H_prop(v, q) + w_h · S_hierarchy(v, q)
```

where `D(v,q)` is the dense Qdrant similarity, `H_prop` is the propagated HHGR graph score, and
`S_hierarchy` is the structural-proximity signal. Evaluation defaults (from
`data/eval/config/experiment.json`):

```text
w_d = 0.40,  w_g = 0.35,  w_h = 0.25
threshold τ = 0.45,  k = 5
```

---

## 8.6 Final ranking

```text
Rank(q) = sort_desc( { (v, F(v,q)) : v ∈ Prop(S₀) }, key = F )
Trim(q) = top_k( Rank(q) )                        if  F_1 ≥ τ
        = ∅ (no evidence / no_answer)             otherwise
```

Ties break on structural importance, then section order.

---

## 8.7 Explainability re-fusion

The explanation engine re-ranks evidence by **usefulness** with a five-signal score:

```text
E(v, q) = Σ_{s ∈ {dense, graph, hierarchy, keyword, citation}}  w_s · s(v, q)
```

then applies interpretation rules (definition promotion, fragment demotion, chain relevance)
and computes the confidence factors used for verification (`src/llm/explanation.py`). This is
the ranking shown to the user.

---

## 8.8 Pseudo-code

```text
Algorithm HHGR-Retrieve(q, G, Vectors, params)
  Input : query q; graph G=(V,E); vector index; params (weights, τ, k, ρ)
  Output: ranked evidence E*; per-signal breakdown; provenance

  # Stage 1–3: query understanding
  q ← Parse(q)                       # text, tokens, R, act, intent
  q ← Expand(q, G)                   # corpus-verified expansions

  # Stage 4: seeds
  S_dense ← DenseSearch(Embed(q), Vectors, k')
  S_lex   ← LexicalSearch(tokens(q), V, k')
  S0      ← Dedup(S_dense ∪ S_lex)

  # Stage 5: HHGR signals
  for v in S0:
      S_text[v]     ← λ·cos(e(v), e(q)) + (1−λ)·overlap(tokens(q), tokens(v))
      S_cite[v]     ← CitationKernel(v, anchors(q), E_CITES)
      S_hier[v]     ← HierarchyKernel(v, anchors(q), E_PART_OF)
      S_struct[v]   ← StructuralImportance(v, intent(q))
      H[v]          ← α·S_text[v] + β·S_cite[v] + γ·S_hier[v] + δ·S_struct[v]

  # Stage 6: propagation
  C ← Propagate(S0, E_PART_OF, decay=ρ, boundedByDocument=true)
  for x in C:
      H_prop[x] ← max over s in S0 of H[s]·ρ^{dist_partof(x,s)}

  # Stage 7: fusion
  for v in C:
      F[v] ← w_d·Dense(v) + w_g·H_prop[v] + w_h·S_hier[v]

  # Stage 8: rank + threshold
  R ← SortDesc(F)
  if R[0].score < τ: return NoEvidence(reason="below threshold")
  E* ← TopK(R, k)

  # Stage 9–10: context + explanation re-fusion
  E* ← AssembleContext(E*, G)
  E* ← ExplainRefuse(E*, q)          # five-signal re-fusion + interpretation
  return E* with provenance
```

---

## 8.9 Complexity

Let `n = |V|` (corpus nodes), `c = |S₀|` (seed candidates, ≈ `2k'`), and `h` the maximum
hierarchy depth (small, ≈ 3–4).

| Stage | Cost |
|-------|------|
| Parsing / expansion | `O(|q| + |R|)` |
| Dense search | `O(log n)` per query with ANN index |
| Lexical search | `O(c · |T|)` over candidates |
| Signal computation | `O(c · (|CITES| + h))` |
| Propagation | `O(c · h)` (bounded by document) |
| Fusion + sort | `O(c log c)` |
| Explanation | `O(k · |text|)` |

Total is dominated by retrieval and is effectively `O(c log c + c·h)` after ANN search —
sub-linear in corpus size, which is what allows a CPU-only deployment to stay responsive.

---

## 8.10 Parameters and defaults

| Symbol | Meaning | Default | Source |
|--------|---------|---------|--------|
| `α, β, γ, δ` | HHGR signal weights | tuned; sum 1 | settings / scorer |
| `w_d, w_g, w_h` | fusion weights | 0.40 / 0.35 / 0.25 | `experiment.json` |
| `λ` | text signal dense/lexical mix | tuned | scorer |
| `ρ` | propagation decay | ≈ 0.5 | context |
| `τ` | confidence threshold | 0.45 | `experiment.json` |
| `k` | top-k evidence | 5 | `experiment.json` |

---

## 8.11 Why HHGR (design rationale)

1. **Structure is signal** — `S_hierarchy` and `E_PART_OF` encode legal containment that flat
   retrieval discards.
2. **Cross-references matter** — `S_citation` surfaces provisions that the query's anchor
   sections depend on.
3. **Not all sections are equal** — `S_struct` promotes definitions/penalties appropriately.
4. **Two-level fusion is robust** — the robust, interpretable graph score feeds a semantic
   fusion, and the whole thing is re-ranked by an explainable five-signal score, so failures at
   one level are recoverable at another.
5. **Auditability** — every signal is exposed in provenance, so any ranking can be justified.
