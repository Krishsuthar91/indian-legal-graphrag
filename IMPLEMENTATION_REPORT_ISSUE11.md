# Implementation Report — Issue #11: Eliminate Residual Parser Fragments (V2.3)

Generated: 2026-09-18

---

## 1. Root Cause

`data/hierarchy/*.json` still contained _parser fragments_: nodes that are not
independent legal provisions and must never appear as retrieval evidence. Four
fragment classes were produced by `src/hierarchy/parser.py`'s structural matcher
(`match_line` / `_merge_consecutive_body` / `_split_embedded_sections`):

| Fragment class | Description | Pre-fix count |
|---|---|---|
| `annotation_isolated` | Explanation / Illustration / Proviso headings with **empty** body text (e.g. `n_0004`–`n_0006` of the eval corpus `0940d367554383c5`) | 704 (232 docs) |
| `annotation_front` | Same annotation headings whose whole content line got captured as `numbering` (`m.group(1)` = the `(.*)` body group — the literal keyword is not a capture group in `src/hierarchy/patterns.py`) | 393 (19 docs) |
| `section_lowercase_title` | False section boundaries created where a body sentence wrapped across lines (e.g. `294A. of the Indian Penal Code not affected : …`, `76. to 123 — Repealed` in `0d1934142f67c5f5` / `0e178b31f7181a31`) | 39 (19 docs) |
| `section_body_fragment` | Footnote-editing note parsed as a section heading (IPC `n_0072` title `The words "Thirdly,"`) | 1 (1 doc) |

**Total: 1137 fragment nodes = 26.8% of the 4238 hierarchy nodes.** The largest
individual loss was the Indian Penal Code (`cf20a14c52127fd5`, −209 nodes), then
the Indian Contract Act 1872 (`0d1934142f67c5f5`, −13), 19 Act-partial
documents (−13 each) and ~194 small ICA-1892 documents (−3 each).

Because `src/embeddings/indexer.py:node_text()` embeds `title + text` per node
and `HierarchyIndexer` writes every non-`sections` unknown type into the generic
`sections` collection (`src/embeddings/models.py:collection_for`), every one of
these nodes was independently retrievable — i.e. legal evidence could be a
truncated tail like `Publishes the name or any matter which may…` (IPC `n_0328`)
or the footnote fragment `The words "Thirdly," … omitted by Act 17 of 1949`.

---

## 2. Files Modified

Source (parsing/hierarchy pipeline only):

| File | Change |
|---|---|
| `src/hierarchy/parser.py:140` | `_FRAGMENT_NODE_TYPES = frozenset({"explanation","illustration","proviso"})` |
| `src/hierarchy/parser.py:146` | `_LOWERCASE_START_RE = re.compile(r"^[a-z]")` |
| `src/hierarchy/parser.py:151` | `_FOOTNOTE_SECTION_RE = re.compile(r"^The words [\u201c\"]")` |
| `src/hierarchy/parser.py:154-186` | `suppress_fragment_nodes(nodes)` — merges fragment title+text into the nearest preceding surviving node, returns filtered list |
| `src/hierarchy/parser.py:368` | `nodes = suppress_fragment_nodes(nodes)` immediately before `build_hierarchy(...)` in `parse_document` |

Tests / fixtures whose **expected values legitimately change** with the cleaned
corpus:

| File | Change |
|---|---|
| `tests/test_eval_harness.py:22-25` | `TestCorpus.test_build_corpus_counts`: `node_count == 8`, `edge_count == 7`, `all_nodes() == 8` (was 11 / 10 / 11 — the 3 annotation nodes of `0940d367554383c5` are gone) |
| `tests/test_task21_retrieval_ranking.py:92-98` | `test_consideration_query_ranks_consideration_sections` deterministic top-5 now `["23","185","2","8","10"]`; comment updated |

Data regenerated: **all 250 `data/hierarchy/*.json`** (0 failures, 0 kept).
No changes to the embedding provider, retrieval, ranking, confidence, routing,
citation scoring, propagation, canonical IDs, LLM, or evaluation pipeline.
No git operations performed.

---

## 3. Before / After Measurements

Metric (non-root nodes over the 250 hierarchy files):

| Metric | Before | After | Δ |
|---|---|---|---|
| Total hierarchy nodes | 4238 | 3101 | **−1137 (−26.8%)** |
| `explanation` / `illustration` / `proviso` nodes | 1097 | 0 | −1097 |
| False `section` nodes (lowercase / footnote headings) | 40 | 0 | −40 |
| Fragment share of corpus | 26.8% | **0.0%** | — |
| Eval corpus `0940d367554383c5` | 10 non-root | 7 non-root | −3 |

Per-document examples:

| Document | Before | After | Removed |
|---|---|---|---|
| `cf20a14c52127fd5` (IPC) | 753 | 543 | −209 |
| `0d1934142f67c5f5` (ICA 1872, canonical) | 217 | 204 | −13 |
| 19 ICA-Act partial documents | 46 each | 33 each | −13 each |
| ~194 small ICA-1892 documents (incl. eval `0940d367554383c5`, `be2b0c714b2c98cb` 15→12) | 10 (15) | 7 (12) | −3 each |

Re-scan after regeneration: **0 fragments, 0.0%.**

---

## 4. Parser Changes

A single post-parse filter in `src/hierarchy/parser.py`, chosen as the smallest
isolated fix (Option B — keep the annotation patterns in
`src/hierarchy/patterns.py`, suppress the malformed nodes they emit):

```
def suppress_fragment_nodes(nodes):
    for node:
        is_fragment = node.node_type in _FRAGMENT_NODE_TYPES
                   or (node.node_type == "section"
                       and (_LOWERCASE_START_RE.match(title)
                            or _FOOTNOTE_SECTION_RE.match(title)))
        if is_fragment:
            merge title+text into the previous surviving node's text
        else:
            keep as-is
```

- Annotation headings are dropped **as nodes** and their content folded back
  into the section they annotate (their body was already the section's tail).
- False sections with lowercase-start titles and the single footnote fragment
  are similarly folded into the previous section — text preserved, bogus
  boundary removed.
- The clause `matching` in `src/embeddings/models.py:collection_for` uses
  `node_types.get(type, SECTIONS)`, so disappearing annotation types are safe.
- Warnings: `cf20a14c52127fd5` retains 2 pre-existing `duplicate_numbering`
  warnings (`334`, `354B` under `n_0410`) — unrelated to fragments.

---

## 5. Validation Results

All required statutory provisions survive the suppression in the regenerated
canonical files:

- IPC (`cf20a14c52127fd5`): **302** *Punishment for murder*, **304A** *Causing
  death by negligence*, **378** *Theft*, **420** *Cheating and dishonestly
  inducing delivery of property*, **425** *Mischief* ✓
- ICA 1872 (`0d1934142f67c5f5`): **10** *What agreements are contracts*, **14**
  *"Free consent" defined*, **17** *"fraud defined* , **23** *What consideration
  and objects are lawful*, **73**, **74** compensation sections ✓

No tests reference the removed node ids (`n_0004`/`n_0005`/`n_0006` in any test
file), and gold citations in `data/eval/gold/contract_act_gold.json` only
reference surviving ids (`n_0001/2/3/8/9`).

---

## 6. Retrieval Verification

Deterministic in-memory corpus built from the regenerated canonical files
(749 indexed points; 696 sections, 17 clauses, 34 chapters, 2 documents).
Seven-query regression with `top_k=5`:

| Query | Fragment evidence | Rank-1 result |
|---|---|---|
| Section 378 IPC | 0 | 378 *Theft* |
| Section 302 IPC | 0 | 302 *Punishment for murder* |
| Section 420 IPC | 0 | 420 *Cheating and dishonestly inducing delivery of property* |
| Section 10 Contract Act | 0 | 10 *What agreements are contracts* |
| What is theft? | 0 | 378 *Theft* (+ 381, 456, 105 …) |
| What is murder? | 0 | 300 *Murder* in top-5 (79, 105, 108A, 38 …) |
| What is cheating? | 0 | 415 *Cheating* in top-5 (416, 414, 417, 419 …) |

**0 of 35 top-evidence slots reference a fragment node.** Section-lookup queries
place the exact section at rank 1; concept queries surface the correct provision
family. The pre-existing fragment `n_0328` (`Whoever prints or`, IPC §228A(1)) is
still present as a legitimate `sub_section` by design (see §9).

---

## 7. Test Results

```
python -m pytest -q --durations=3
966 passed, 5 warnings in 52.98s
```

Locally-updated expectations (both deterministic locks changed only because the
corpus content legitimately changed):

- `tests/test_hierarchy_parser.py`: 24 passed
- `tests/test_eval_harness.py`, `tests/test_canonical_corpus.py`,
  `tests/test_documents_api.py`: 49 passed
- `tests/test_task21_retrieval_ranking.py`: 6 passed

---

## 8. Risks

- **Ranking drift (expected):** suppressing 26.8% of the corpus changed
  deterministic top-N orderings. Only two locks were affected
  (`test_eval_harness` counts, `test_task21` consideration ranking) — both
  updated to the new stable output; no relevance assertions were weakened.
- **Content preservation:** every suppressed node's `title` + `text` is folded
  into the preceding node, so no statutory wording is lost from the corpus —
  only the bogus node boundaries are removed.
- **Annotation patterns unchanged:** keeping the patterns (Option B) means any
  future annotation content is still captured by the parser and then suppressed
  by the same filter, so the fix is robust to re-parsing.

---

## 9. Remaining Limitations

- **Sub-clause fragments remain by design:** 27 lowercase-start
  `sub_section` / `clause` / `sub_clause` nodes are intentionally **not**
  suppressed (e.g. IPC `n_0328`, title `Whoever prints or` = real §228A(1);
  ICA `0d1934142f67c5f5` `n_0010` `be absolute and unqualified. (2) be expr`)
  to preserve legitimate provision structure. They can still be retrieved but
  carry valid numbering context.
- **Pre-existing parser quirks (not introduced by this change):** `_split_embedded_sections`
  rewrites `Section 1.` → `1. Section`, so fresh parses emit `title="Section"`,
  `numbering="1"` while older saved files kept `title="."`; footnote-editing
  notes beginning with other uppercase phrases than `The words` are not
  pattern-matched.
- **Pre-existing warnings:** IPC `duplicate_numbering` `334` / `354B` remain
  unaddressed (documented, unrelated to fragments).