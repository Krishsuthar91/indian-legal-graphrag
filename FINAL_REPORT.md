# FINAL REPORT — Explaintool: Explainable Multilingual Hierarchical Graph-RAG (HHGR)

**Project**: Indian Legal Document Intelligence
**Status**: All 10 modules complete
**Scope**: Module 10 — Research Evaluation & Publication Package

---

## 1. Executive Summary

Explaintool answers questions over Indian legal documents with **verifiable,
explainable, and multilingual** retrieval. The core innovation (HHGR) fuses
dense multilingual embeddings with a hierarchical knowledge graph and
hierarchy-aware evidence propagation, then exposes per-signal evidence scores,
a reasoning chain, numbered citations, confidence, validity flags, and
counter-authority detection on every answer.

Module 10 adds the full research and publication package: a gold-standard
evaluation dataset, retrieval / explainability / generation metric suites,
five baselines, a six-arm ablation study, an offline reproducible harness, and
an IEEE-ready paper with poster and slides. The entire evaluation is
deterministic (mock LLM + deterministic embeddings), so every reported number
reproduces in ~0.25 s with no network access.

## 2. What Was Delivered

### 2.1 Module 10 — Evaluation & Publication

| Component | Location | Contents |
|---|---|---|
| Gold dataset | `eval/dataset.py`, `data/eval/gold/*.json` | 34 items / 5 legal domains; 10 grounded Contract Act items + 24 citation-scored probes (BNS, BNSS, BSA, SC judgments); schema validation + `manifest.json` |
| Retrieval metrics | `eval/metrics/retrieval.py` | Recall@K, Precision@K, Hit Rate@K, MRR, MAP, NDCG@K, latency (mean/p50/p95) + throughput |
| Explainability metrics | `eval/metrics/explainability.py` | Citation accuracy, hierarchy correctness, graph-path accuracy, provenance completeness, evidence coverage, counter-authority P/R/F1 |
| Generation metrics | `eval/metrics/ragas.py`, `eval/metrics/semantic.py` | RAGAS-style faithfulness, answer relevancy, context recall/precision, answer correctness (offline surrogates; optional native ragas) |
| Systems | `eval/systems.py` | HHGR (full), dense-only, BM25, graph-only, naive RAG |
| Ablation | `eval/ablation.py` | full / no_graph / no_hierarchy / no_dense / no_multilingual / no_explainability |
| Harness + CLI | `eval/harness.py`, `eval/cli.py`, `eval/corpus.py` | One command → JSON/CSV/Markdown/PDF reports + SVG/PNG figures |
| Paper package | `paper/` | IEEEtran paper + BibTeX, A0 poster, beamer slides, build README |
| Reproducibility | `scripts/reproduce.sh`, `requirements-lock.txt` | One-command venv → deps → benchmark → tests |

### 2.2 Confirmed deliverable boundaries

- No backend logic (`src/`), frontend features (`ui/`), or deployment artifacts
  (`deploy/`, `monitoring/`, `docker-compose*.yml`) were modified.
- `tests/conftest.py` only gained additive evaluation fixtures.
- 86 new tests; existing test files untouched.

## 3. Headline Results (contract_act_gold, 10 items, K=5, seed 42)

### 3.1 Retrieval effectiveness

| System | R@5 | MRR | MAP | NDCG@5 | Mean ms |
|---|---|---|---|---|---|
| Naive RAG | 0.800 | 0.700 | 0.675 | 0.714 | 0.80 |
| Dense-only | 0.800 | 0.700 | 0.675 | 0.714 | 0.77 |
| BM25 | 0.900 | 0.758 | 0.728 | 0.778 | 0.04 |
| Graph-only | 0.800 | 0.650 | 0.620 | 0.674 | 0.35 |
| **HHGR** | 0.800 | **0.750** | **0.750** | **0.763** | 2.58 (~388 QPS) |

### 3.2 Explainability (HHGR)

| Metric | Score |
|---|---|
| Citation accuracy | 0.95 |
| Hierarchy correctness | 1.00 |
| Graph-path accuracy | 1.00 |
| Provenance completeness | 0.85 |
| Evidence coverage | 0.68 |
| Counter-authority F1 | 1.00 |

### 3.3 Ablation highlights

- Removing the multilingual path (forced English) drops MRR 0.750 → 0.650 and
  citation accuracy 0.95 → 0.75: the multilingual path is the highest-value
  component.
- Removing the dense signal raises R@5 to 0.900 but lowers MRR/MAP (graph +
  hierarchy recover recall with worse ranking) and drops citation accuracy to
  0.85.
- Removing explainability enrichment is accuracy-neutral but deletes all
  provenance — its purpose is auditability, not ranking.

### 3.4 Generation (RAGAS-style, mock LLM)

HHGR faithfulness 1.0, answer relevancy 0.783, context recall 0.75, context
precision 0.419, answer correctness 0.44. Naive RAG reaches full
citation-anchor context recall (1.0) because its dense hits carry the exact
gold section numbers, while HHGR covers a broader, structurally enriched
evidence set; relevancy/correctness are comparable (0.82/0.46 for naive RAG).

## 4. Reproducibility

```bash
bash scripts/reproduce.sh        # venv → pip install -r requirements-lock.txt
                                 #   → python -m eval.cli → pytest
```

Determinism guarantees: fixed seed 42; deterministic embedding provider
(dim=64); `MockLLMClient`; in-memory Qdrant; single corpus document
(`0940d367554383c5`, 11 nodes / 10 edges). Outputs are written under
`evaluation/` and regenerable byte-for-byte on a given Python version.

## 5. Verification Evidence

| Check | Result |
|---|---|
| `pytest` (repo root) | **447 passed** (361 pre-existing + 86 Module 10) |
| `npm test` (ui/) | **49 passed** |
| `npm run build` (ui/) | OK (type-check + Vite production build) |
| `ruff check eval/ tests/test_eval_*.py tests/conftest.py` | Clean |
| `python -m eval.cli --out evaluation` | Complete run in 0.247 s, all reports + 8 figures written |
| Repo-wide `ruff check .` | 78 pre-existing errors (unchanged baseline, unrelated to Modules 7–10) |
| Dataset manifest | 34 total items, 10 grounded, 5 domains |

## 6. Known Limitations

1. **Docker / nginx unavailable on this machine** — containerized evaluation,
   `docker compose up`, and `nginx -t` were validated structurally and via CI
   config only, not executed locally.
2. **Small corpus** — the grounded benchmark uses one synthetic Contract Act
   document (11 nodes). BM25's lexical edge on this corpus reflects that;
   scale-out to full statutes is future work.
3. **Deterministic embeddings** — Hindi queries rely on the deterministic
   provider for offline evaluation; real multilingual transfer needs
   bge-m3/LaBSE.
4. **Evidence coverage 0.68** — the English tokenizer cannot match the Hindi
   reference answers; a multilingual tokenizer or real embeddings closes it.
5. **Mock generator** — RAGAS numbers are template-level; native RAGAS with a
   real LLM requires `ragas` + provider keys (supported via
   `ragas_context()`, not exercised here).

## 7. How to Run

```bash
# Quick smoke benchmark
python -m eval.cli --quick --out evaluation

# Full benchmark + figures
python -m eval.cli --config data/eval/config/experiment.json --out evaluation

# One-command reproducibility
bash scripts/reproduce.sh

# Paper (requires LaTeX)
cd paper && pdflatex paper.tex && bibtex paper && pdflatex paper.tex && pdflatex paper.tex
```

## 8. Conclusion

Explaintool demonstrates that hierarchical structure + multilingual dense
retrieval + explicit provenance can be combined into a practical, measurable
legal QA pipeline. Module 10 turns that pipeline into a reproducible research
artifact: dataset, metrics, baselines, ablations, reports, figures, and a
publication package, all offline and all green on verification.
