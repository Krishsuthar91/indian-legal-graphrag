# 19 — Limitations and Future Work

This document records the known limitations of the system and repository, each tied to
evidence in the codebase or evaluation artefacts, followed by concrete future work.

---

## 19.1 Evaluation limitations

| # | Limitation | Evidence |
|---|-----------|----------|
| L1 | **Small gold set.** Only 34 gold items, of which **10 are grounded** — no statistical significance. | `data/eval/gold/manifest.json` (`total_items 34`, `grounded_items 10`) |
| L2 | **Generation not truly evaluated.** The committed production run used the **mock LLM**, so `answer_accuracy 0.23` / `hallucination_rate 0.79` describe the placeholder, not Nemotron. | `results/evaluation_report.md` (`llm_provider mock`, `model mock-llm`) |
| L3 | **Moderate calibration with over-confidence.** ECE 0.179 / MCE 0.190; every reliability bucket is over-confident by ~0.12–0.19. | `results/evaluation_report.md` → "Moderate calibration" |
| L4 | **Deterministic embeddings limit separation.** Offline results use hash embeddings, so HHGR and naive-RAG often coincide. | `data/eval/config/experiment.json` (`force_deterministic true`) |
| L5 | **BM25 beats HHGR on raw recall/hit-rate** on the small set (0.90 vs 0.80). | `evaluation/reports/benchmark.md` |
| L6 | **Modest recall in production** (`recall@5 0.33`) and **weak definition-query citation accuracy (0.0)**. | `results/evaluation_report.md` |
| L7 | **Memory usage not measured** (reported as `0.0000 MB`). | `results/evaluation_report.md` → Performance |
| L8 | **Hierarchy/explainability ablations show no retrieval change** on the small set (signals overlap with graph). | `evaluation/reports/benchmark.md` → Ablation |

---

## 19.2 Modelling limitations

| # | Limitation | Evidence |
|---|-----------|----------|
| L9 | **No NER model.** Legal entity/reference extraction is regex/pattern-based. | `src/knowledge_graph/citation_extractor.py`; no NER module |
| L10 | **No trained reranker.** Re-ranking is weighted multi-signal fusion, not a cross-encoder. | `src/retrieval/ranker.py`, `src/llm/explanation.py` |
| L11 | **Intent classification is heuristic**, not a fine-tuned classifier. | `src/retrieval/intent.py` |
| L12 | **LLM relevance judge depends on the provider**; deterministic fallback is weaker. | `docs/Task23_Relevance_Judge_Investigation.md` |
| L13 | **Entailment is claim-level and approximate** (lexical/model surrogates). | `src/llm/service.py`, `docs/VerificationFramework.md` |

---

## 19.3 Data & corpus limitations

| # | Limitation | Evidence |
|---|-----------|----------|
| L14 | **Large duplication in the corpus** (1,632 processed vs 295 hierarchy files) mitigated only by the canonical layer. | directory counts; `scripts/corpus_dedup_report.py` |
| L15 | **No consolidated corpus manifest** listing every source document with metadata. | Not found in repository |
| L16 | **Coverage concentrated** on a few Acts; the 50-question benchmark focuses on Chapter V of the Contract Act. | `data/eval/contract_act_1872_benchmark.csv` |
| L17 | **Annotated data beyond the 34 gold items** is absent. | Not found in repository |

---

## 19.4 Security & operations limitations

| # | Limitation | Evidence |
|---|-----------|----------|
| L18 | **No authentication/authorization layer.** Endpoints are open; protection relies on network placement. | Not found in repository (API docs) |
| L19 | **A live NVIDIA API key has been observed in the git-ignored local env file.** It must never be committed and any exposed key should be rotated. | `deploy/env/.env.development.local` |
| L20 | **Root `.env` is present but not loaded**, a configuration trap for operators. | `src/config/settings.py`; `docs/Configuration.md` |
| L21 | **Redis is provisioned but not a hard runtime dependency** — capacity that is currently unused. | `docker-compose.yml` |
| L22 | **Repository contains tooling/generated directories** (`.agents`, `brag-output`, `demo-output`) that are not part of the runtime. | top-level listing |

---

## 19.5 Architectural / functional limitations

| # | Limitation | Evidence |
|---|-----------|----------|
| L23 | **Hierarchy propagation is bounded to a single document**, so cross-Act reasoning is limited. | `src/retrieval/context.py:89-149` |
| L24 | **Counter-authority detection is marker-based**, not a temporal/versioned law model — it can miss implicitly overruled provisions. | `src/llm/explanation.py:1433-1452` |
| L25 | **No temporal/amendment versioning** of provisions (in-force flag is coarse). | knowledge-graph schema |
| L26 | **No user feedback loop** persisted for online learning. | Not found in repository |
| L27 | **No streaming responses**; answers are returned whole. | `src/api/qa.py` |

---

## 19.6 Design trade-offs (intentional)

- **Two nested fusion layers** add complexity but improve robustness and interpretability.
- **Offline deterministic mode** sacrifices realism for reproducibility.
- **Mock LLM by default in evaluation** prevents accidental API cost while keeping pipelines
  testable, at the cost of unmeasured generation quality.
- **Marker-based counter-authority** is cheap and transparent but incomplete.

---

## 19.7 Future work

### Near term
1. **Evaluate with the real LLM** (Nemotron) end-to-end and publish generation metrics
   (addresses L2).
2. **Expand the gold set** to hundreds of grounded items across more Acts (L1, L16, L17).
3. **Recalibrate confidence** (temperature scaling/isotonic) to reduce ECE (L3).
4. **Add authentication** (API keys / OAuth) and secret hygiene (L18, L19).
5. **Remove/clean tooling artefacts** and fix the `.env` trap (L20, L22).

### Medium term
6. **Cross-encoder reranker** on the fused top-k (L10).
7. **Legal NER** for entities, definitions, and references (L9).
8. **Learned intent classifier** (L11).
9. **Temporal law model** with amendment/version history and stronger counter-authority
   detection (L24, L25).
10. **Cross-Act propagation** with controlled leakage guards (L23).

### Long term
11. **Human evaluation** with legal professionals for answer correctness and usefulness.
12. **Online learning** from user feedback (L26).
13. **Streaming + conversational** interface (L27).
14. **Broader language and jurisdiction coverage**.

---

## 19.8 What the system does *not* claim

- It does **not** claim to be a substitute for professional legal advice.
- It does **not** claim state-of-the-art generation quality (generation was evaluated with a
  mock LLM).
- It does **not** claim complete or temporally accurate statutory coverage.
- It does **not** guarantee correctness — it guarantees **auditability and groundedness
  signalling**, which is a different and more defensible promise.
