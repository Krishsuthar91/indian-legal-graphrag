# 07 — Retrieval Pipeline

Retrieval is the backbone of HHGR. A question flows through query understanding, multi-signal
seed generation, graph scoring, hierarchy propagation, fusion, and ranking, and finally
emerges as an ordered list of evidence units with per-signal provenance.

Primary sources: `src/retrieval/` (`query.py`, `intent.py`, `query_expansion.py`,
`scorer.py`, `ranker.py`, `context.py`, `metrics.py`), `src/embeddings/retriever.py`,
and the re-fusion in `src/llm/explanation.py`.

---

## 7.1 Pipeline at a glance

```text
 user question
      │
      ▼
 [1] Query parsing & normalisation        src/retrieval/query.py
      │
      ▼
 [2] Intent classification                src/retrieval/intent.py
      │
      ▼
 [3] Corpus-aware query expansion         src/retrieval/query_expansion.py
      │
      ▼
 [4] Seed retrieval                       src/embeddings/retriever.py
      ├── dense   (Qdrant k-NN)
      └── lexical (keyword/token overlap)
      │
      ▼
 [5] HHGR graph scoring (4 signals)       src/retrieval/scorer.py
      text · citation · hierarchy · structural
      │
      ▼
 [6] Hierarchy propagation                src/retrieval/context.py
      ancestors · descendants · siblings along PART_OF
      │
      ▼
 [7] Fusion (dense + graph + hierarchy)   src/embeddings/retriever.py
      │
      ▼
 [8] Ranking & top-k selection            src/retrieval/ranker.py
      │
      ▼
 [9] Context assembly (evidence units)    src/retrieval/context.py
      │
      ▼
[10] Explainability re-fusion              src/llm/explanation.py
      dense · graph · hierarchy · keyword · citation
      │
      ▼
 evidence list + per-signal explanations + provenance
```

---

## 7.2 Stage 1 — Query parsing and normalisation

`src/retrieval/query.py`

- Normalises Unicode, case, and whitespace; preserves Devanagari/Tamil/Bengali scripts.
- Detects the **target Act** from explicit mentions or canonical mappings
  (`src/knowledge_graph/canonical.py`; e.g. "indian contract act" → `0d1934142f67c5f5`).
- Extracts **explicit legal references** (section/article numbers, "u/s 302", "Section 2(h)")
  which become strong anchors for the citation and structural signals.
- Produces a structured `ParsedQuery` (text, tokens, act filter, referenced sections,
  language), consumed by every later stage.

**Multilingual tokenization** (`query.py:155-172`) splits on script boundaries and legal
punctuation, keeping section numbers intact so they can be matched exactly.

---

## 7.3 Stage 2 — Intent classification

`src/retrieval/intent.py` classifies the question type to bias scoring:

| Intent | Example | Retrieval effect |
|--------|---------|------------------|
| definition | "What is theft?" | promote sections that contain a formal definition |
| penalty | "Punishment for theft?" | promote penalty/punishment sections |
| procedure | "How do I file X?" | promote procedural sections |
| comparison | "Difference between A and B" | retrieve multiple sections for each side |
| general | fallback | neutral weighting |

Intent labels steer the definition-promotion and fragment-demotion rules in evidence ranking
(`src/llm/explanation.py:1107-1123`).

---

## 7.4 Stage 3 — Corpus-aware query expansion

`src/retrieval/query_expansion.py:453-532`

- Expands surface phrases to **verified section numbers only when those sections exist in the
  corpus**, preventing invented references.
- Adds legal synonyms and statutory phrasing (e.g. "said", "deemed", "notwithstanding").
- Is **deterministic** and auditable: every expansion is recorded so the reasoning chain can
  justify it.

This stage is a key anti-hallucination measure: expansion cannot introduce a section the
corpus does not contain.

---

## 7.5 Stage 4 — Seed retrieval

`src/embeddings/retriever.py`

Two complementary seed sources:

1. **Dense retrieval** — the expanded query is embedded with the active provider and searched
   against the Qdrant `sections` collection (and optionally `chapters`/`clauses`) by cosine
   similarity, returning a candidate set with similarity scores.
2. **Lexical retrieval** — token/keyword overlap between the query and candidate texts
   (with legal stop-word handling) provides exact-match recall that embeddings can miss
   (statutory phrasing, numbers).

Seed candidates are merged and de-duplicated by node id.

---

## 7.6 Stage 5 — HHGR graph scoring (four signals)

`src/retrieval/scorer.py:18-24`

Each candidate node receives four signals computed over the legal graph:

| Signal | Weight key | What it measures |
|--------|-----------|------------------|
| **Text** | `text` | lexical/semantic overlap of node text with the query |
| **Citation** | `citation` | whether the node cites / is cited by anchor sections (`CITES`) |
| **Hierarchy** | `hierarchy` | proximity of the node to query anchors along `PART_OF` |
| **Structural** | `structural` | intrinsic legal importance (e.g. definitional/penalty markers, section centrality) |

The weighted combination of these four is the **HHGR score**, which is surfaced as the
`graph` signal of the fusion layer (see `08_HHGR_Algorithm.md`). Weights are configurable
(`src/config/settings.py`, retrieval weights) and are exercised in the ablation study
(`eval/ablation.py`: `no_graph`, `no_hierarchy`, `no_dense`).

---

## 7.7 Stage 6 — Hierarchy-aware propagation

`src/retrieval/context.py:89-149`

Seed matches propagate through the hierarchy, **bounded to a single document** to avoid
cross-Act leakage:

- **Ancestors** — a matched Section pulls in its Chapter and Document context.
- **Descendants** — a matched Section pulls in its Clause/illustration children.
- **Siblings** — closely numbered neighbours are considered when the query references a range.

Propagation attaches a decayed score so a Section surfaces its structural context without the
context outranking the directly matched provision.

---

## 7.8 Stage 7 — Fusion

`src/embeddings/retriever.py:23-27`

The three high-level signals are fused into a single score:

```text
fused = w_dense * dense
      + w_graph * graph          # graph = HHGR 4-signal score
      + w_hierarchy * hierarchy
```

Default hybrid weights observed in the evaluation config
(`data/eval/config/experiment.json`) are `dense 0.4 / graph 0.35 / hierarchy 0.25`. The
production weights are configurable via settings. The fused HHGR score is what downstream
ranking and confidence use.

---

## 7.9 Stage 8 — Ranking and top-k selection

`src/retrieval/ranker.py`

- Sorts by fused score, then applies tie-breakers (structural importance, section
  order, document priority).
- Applies a **confidence threshold** (evaluation default `0.45`,
  `data/eval/config/experiment.json`) to decide whether enough evidence exists.
- Selects **top-k** (evaluation default `k = 5`) for the context window.
- Records the per-signal contributions for each retained item (used in provenance).

---

## 7.10 Stage 9 — Context assembly

`src/retrieval/context.py`

Assembles the selected units into an ordered, deduplicated evidence context:

- Attaches hierarchy path, section number, title, and text.
- Deduplicates overlapping clauses that belong to the same section.
- Attaches citation targets for cross-referenced provisions.
- Produces the evidence list returned to the API and passed to the explanation engine.

---

## 7.11 Stage 10 — Explainability re-fusion

`src/llm/explanation.py:62-76`

The explanation engine performs a **second, finer fusion** over its own signal set:

```text
explain_score = w_dense * dense + w_graph * graph + w_hierarchy * hierarchy
              + w_keyword * keyword + w_citation * citation
```

It then derives the reasoning chain, counter-authority markers, definition promotion, fragment
demotion, confidence factors, and verification trace (fully described in
`09_Explainability.md`). This re-fusion lets the *explanation* rank evidence by usefulness even
when the *retriever* ranked by raw similarity.

---

## 7.12 Signals summary

| Layer | Signals | Location |
|-------|---------|----------|
| HHGR graph score | text, citation, hierarchy, structural | `src/retrieval/scorer.py` |
| Retrieval fusion | dense, graph, hierarchy | `src/embeddings/retriever.py` |
| Explanation fusion | dense, graph, hierarchy, keyword, citation | `src/llm/explanation.py` |

---

## 7.13 Configuration touch-points

| Knob | Effect | Source |
|------|--------|--------|
| hybrid weights | balance dense/graph/hierarchy | settings + `experiment.json` |
| top-k | context size | settings + `experiment.json` |
| confidence threshold | sufficiency gate | settings + `experiment.json` |
| embedding provider | dense quality/dim | settings |
| force deterministic | reproducible offline runs | settings / `experiment.json` |

---

## 7.14 Metrics

`src/retrieval/metrics.py` computes retrieval quality for offline evaluation:
Precision@k, Recall@k, MRR, NDCG, and MAP, alongside signal-contribution statistics. These feed
`src/evaluation/metrics/retrieval.py` and the `eval/` harness reports.

---

## 7.15 Key retrieval files quick reference

| File | Responsibility |
|------|----------------|
| `src/retrieval/query.py` | Parsing, normalisation, act/section detection, tokenization |
| `src/retrieval/intent.py` | Intent classification |
| `src/retrieval/query_expansion.py` | Corpus-aware expansion |
| `src/retrieval/scorer.py` | HHGR 4-signal scoring |
| `src/retrieval/ranker.py` | Ranking + top-k + threshold |
| `src/retrieval/context.py` | Hierarchy propagation + context assembly |
| `src/retrieval/metrics.py` | Retrieval metrics |
| `src/embeddings/retriever.py` | Dense + graph + hierarchy fusion |
| `src/llm/explanation.py` | 5-signal re-fusion for explanations |
