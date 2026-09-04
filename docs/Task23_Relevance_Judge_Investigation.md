# Task 23 — Relevance Judge Investigation

**Type:** Analysis-only + minimal test-harness fix
**Corpus:** ICA `0d1934142f67c5f5` (222 nodes) / IPC `cf20a14c52127fd5` (311 nodes)
**Scope of change:** `src/llm/llm.py` — `MockLLMClient` (offline test/demo client) only.
**Untouched:** production retrieval, ranking, confidence scoring, verification logic,
grounding guard, and all prompts.

---

## Executive Summary

`evidence_relevance` was `0.0` for **100% of the 90 supported queries** in the Task 22
harness. Task 23 traced that to a **single defect in the test-harness mock LLM client**,
not in the relevance pipeline, the parser, or the grounding guard:

> `MockLLMClient.complete()` returns plain prose for **every** LLM request — including
> the *relevance-judge* request, for which the pipeline expects JSON. That prose contains
> **no JSON object**, so `_parse_relevance_json()` falls through to its failure fallback
> `{"score": 0.0, ...}` and `evidence_relevance = 0.0` for every query.

This is **purely a harness artifact**. The parser itself is correct (it handles perfect
JSON, markdown-fenced JSON, and JSON embedded in commentary), and the production
`NvidiaClient` returns model text that the parser accepts.

**Quantification (mock made to behave like a production judge):** with the fixed mock,
relevance becomes **non-zero for 90/90**, and **4/90 queries** reach `supported` + guard
PASS (Task 22 baseline: **0/90**). However, only **1 of the 47 top-1-correct** cases
recovers — the other 46 still have relevance < 0.30. The remaining 86/90 stay blocked on
the `insufficient` status caused by genuinely low intrinsic relevance of the **cross-document
contaminated** top-1 evidence (Task 22 found 85.6% contamination).

**Bottom line:** the mock fix removes the fake signal, but does **not** rescue the 47
Task 22 category-D failures. Those require removal of the cross-document contamination —
fixing the judge alone (or the mock alone) is insufficient.

---

## Step 1 — Exact call chain of the relevance pipeline

```
QueryService.answer(query)
  └─ ExplainabilityEngine.explain(query)          src/llm/explanation.py
       └─ _compute_evidence_relevance(query, evidence)   explanation.py:1232
            ├─ if self.llm_client is not None:
            │    self.llm_client.chat(system=_RELEVANCE_JUDGE_SYSTEM,
            │                         user=user_msg, temperature=0.0,
            │                         max_tokens=200)          explanation.py:1250
            │    └─ LLMClient.chat(...)                        llm.py (base)
            │         └─ MockLLMClient.complete(...)           llm.py:647   <-- BUG HERE
            │                                                   (returns prose, not JSON)
            │    _parse_relevance_json(response.text)           explanation.py:174
            │         └─ json.loads(text[start:end+1])          (no '{' found -> fallback)
            │    → EvidenceRelevance(score=0.0, ...)
            └─ verification badge uses score<0.30 → "insufficient"   explanation.py:1781
                 └─ service grounding guard blocks                service.py:293
```

`_compute_evidence_relevance` (explanation.py:1232-1266):
- builds `evidence_block` = `"\n\n".join(f"[{title}] {text}")`
- `user_msg = f"Question: {query}\n\nRetrieved Evidence:\n{evidence_block}"`
- calls `self.llm_client.chat(system=..., user=..., temperature=0.0, max_tokens=200)`
- parses `response.text` with `_parse_relevance_json` and reads `parsed.get("score", 0.0)`.

Evidence (captured live for case 2.014):
```
SYSTEM PROMPT:
 You are an evidence relevance evaluator for a legal question answering system...
 Return ONLY JSON: {"score": float, "label": "...", "reason": "..."}

MOCK RETURN text:
 '[mock] Based on the retrieved legal evidence, the answer addresses:
   Question: What is a contingent contract?. No sources cited.'

_parse_relevance_json(mock) -> {'score': 0.0, 'label': 'unknown',
                                'reason': 'Failed to parse LLM response.'}
mock relevance returned in explain(): 0.0
```

---

## Step 2 — Inspect `MockLLMClient`

`MockLLMClient` (llm.py:637) overrides only `complete()`. It does **not** branch on the
task; it treats every request the same:

```python
query_line = user.split("QUESTION:", 1)[-1].splitlines()[0].strip()
text = ("[mock] Based on the retrieved legal evidence, the answer addresses: "
        f"{query_line}. {citation_note}")
```

- **Prompt it receives:** the relevance judge calls `chat(system=..., user="Question: ... Retrieved Evidence: ...")`. The mock ignores `system` and only looks at `user`.
- **Text it returns:** deterministic prose. **Not JSON** — no `{`/`}` anywhere.
- **JSON?** No.
- **Matches parser expectations?** No. It was written for the *generation* prompt
  (`"QUESTION:"`, `[SOURCE n]` markers); it has no awareness of the relevance/entailment
  judge tasks that the same client serves.

---

## Step 3 — Inspect `_parse_relevance_json`

```python
def _parse_relevance_json(raw: str) -> dict[str, Any]:          # explanation.py:174
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"score": 0.0, "label": "unknown",
            "reason": "Failed to parse LLM response."}
```

- **Accepted format:** the outermost `{ ... }` substring must be valid JSON.
- **Fallback behavior:** if no `{...}` pair present, or the extraction is malformed,
  returns `{"score": 0.0, ...}`.
- **Why score becomes 0.0:** in the harness the extraction `find("{")` returns **-1**
  (mock text has no braces) → fallback fired with `score: 0.0`.
- **Does the parser fail?** No — it never throws; it degrades to the deterministic
  fallback. Exceptions inside the `try` are swallowed and replaced by the fallback dict.

---

## Step 4 — Compare with the production NVIDIA client

`NvidiaClient` (llm.py:605) is a **plain subclass of `OpenAICompatClient`** with **no
`response_format`/JSON-mode enforcement** (verified: no `response_format=json_object` or
`json_schema` anywhere in `llm.py`). So production relies entirely on the system-prompt
instruction *"Return ONLY JSON"*.

- Production expected behavior: the real LLM returns **JSON-shaped text** (optionally
  with conversational prose / markdown fences), which `_parse_relevance_json` extracts
  correctly (`start/end` + `json.loads`).
- The parser experiments (Step 5) show prose-wrapped and markdown-fenced JSON all parse
  fine. **Therefore the issue exists only in `MockLLMClient`** — it produces no JSON at
  all, which is a shape no production judge would be expected to emit for this prompt.

---

## Step 5 — Parser experiments (empirical)

13 response shapes fed to `_parse_relevance_json`:

| Response shape | Parser output | final score |
|---|---|---|
| Perfect JSON `{"score":0.85,...}` | parsed | **0.85** |
| JSON float score | parsed | **0.75** |
| JSON int score | parsed | **1.0** |
| Malformed JSON (`reason: "` unquoted) | fallback | 0.0 |
| Plain prose | fallback | 0.0 |
| Markdown-fenced JSON ` ```json {...} ``` ` | parsed | **0.7** |
| Markdown plain ` ```markdown ... ``` ` | fallback | 0.0 |
| Commentary + JSON `I think... {JSON}` | parsed | **0.6** |
| Two separate brace objects | fallback | 0.0 |
| Empty string | fallback | 0.0 |
| Whitespace | fallback | 0.0 |
| JSON array `[1,2,3]` | fallback | 0.0 |
| Mock-echo prose (`[mock] Based on the retrieved legal evidence...`) | fallback | **0.0** |

**Conclusion:** the parser is robust to prose/fences/commentary. The only inputs it
rejects are genuinely JSON-less text (empty, prose, array, unquoted-key) — exactly what
`MockLLMClient` produced. The failure is upstream of the parser, in the mock return.

---

## Step 6 — Minimal test-harness fix (applied)

**File changed:** `src/llm/llm.py` → `MockLLMClient` only.

`complete()` now calls a new `_judge_json(user)` helper *before* the prose path. When the
prompt matches the relevance-judge format (`"Question: ...\n\nRetrieved Evidence: ..."`),
it returns **valid judge JSON**:

```python
{"score": 0.3896, "label": "tangential", "reason": "Low text overlap; topically related."}
```

The score uses the **same deterministic Dice-bigram `_text_similarity`** the engine's own
`_relevance_fallback` uses (lazily imported from `explanation.py`, avoiding a circular
import; `explanation.py` does not import `llm.py` at module load). This makes the mock a
faithful offline stand-in for a production judge (matching the pipeline's own estimate)
instead of emitting an unparseable string.

**Non-judge (generation) requests are unchanged** — still deterministic prose with source
citations. Retrieval, ranking, confidence, verification, and the guard are untouched.

---

## Quantification — how many Task 22 failures disappear if the mock behaves like production

Measured by re-running all 90 supported queries through the **fixed** mock:

| Metric | Task 22 (broken mock) | Task 23 (fixed mock) |
|---|---|---|
| `evidence_relevance > 0` | **0 / 90** | **90 / 90** |
| `evidence_relevance >= 0.30` (badge/guard gate) | 0 / 90 | **4 / 90** |
| top-1-correct AND relevance >= 0.30 | 0 / 90 | **1 / 90** |
| verification status `supported` | 0 / 90 | **4 / 90** |
| grounding-guard **PASS** | 0 / 90 | **4 / 90** |
| guard-blocked (`status_not_supported`) | 90 / 90 | 86 / 90 |

The 4 recovered queries (all Category 4 snippet queries): `4.007`, `4.011`, `4.013`
(top-1-correct), `4.015` — relevance 0.30–0.38, sufficiency ≥ 0.49, confidence ≥ 0.46.

**Cross-check via the engine's pure deterministic fallback** (`llm_client = None`):
relevance ≥ 0.30 for **3/90**, guard pass **3/90**, top-1-correct & ≥ 0.30 **0/90** —
consistent order of magnitude with the fixed-mock result (4/90; the +1 is due to the
mock's evidence-block formatting differing slightly from the engine's title+text+numbering
join).

**Interpretation:** fixing the harness mock explains the *0.0 artifact* fully, but
recovers **only ~4/90 passes** — i.e. **~46 of the 47 top-1-correct category-D failures
remain**, because their top-1 evidence is cross-document contaminated and its *intrinsic*
relevance is genuinely below 0.30. A correct judge cannot manufacture relevance the
evidence does not have.

---

## Root cause (precise)

1. `_compute_evidence_relevance` invokes the LLM client as a **judge** and expects JSON.
2. `MockLLMClient.complete()` ignores task type and returns **prose with no JSON object**.
3. `_parse_relevance_json` finds no `{...}` and returns the failure fallback `score: 0.0`.
4. `_compute_evidence_relevance` uses `parsed.get("score", 0.0)` → `evidence_relevance = 0.0`.
5. The verification badge marks `relevance < 0.30` as `insufficient` (explanation.py:1781).
6. The grounding guard blocks the `sufficient`-equivalent because status != `supported`.

**The pipe is not broken; the mock was mute.** Outside a mock, a real judge (e.g., the
NVIDIA client) produces parseable JSON and yields a real score. But the fixed mock also
reveals that the *real* problem for the 47 top-1-correct cases is evidence contamination,
not the judge.

---

## Recommendation (unchanged from Task 22)

- **Do not** lower the relevance/sufficiency/confidence thresholds — that would admit
  genuinely irrelevant evidence.
- Fix the **cross-document (ICA↔IPC) contamination** so the target document is retrieved
  (highest impact for the 47 category-D cases).
- Keep the mock JSON fix (in `llm.py`) so offline/harness runs reflect real relevance and
  future audits are not confounded by the `0.0` artifact.
