# 20 — Report and Paper Mapping

This final document maps the repository to the two deliverables the project targets: a
**university research report** and an **IEEE conference paper**. It shows which code and which
of the 20 technical documents support each report/paper section.

---

## 20.1 The 20-document package

| File | Subject | Primary sources |
|------|---------|-----------------|
| `01_Project_Overview.md` | Problem, users, objectives, innovations, stack | `README.md`, `pyproject.toml`, `src/` |
| `02_Folder_Structure.md` | Every folder's purpose and interactions | whole repo |
| `03_Backend_Architecture.md` | FastAPI, routes, services, middleware | `src/main.py`, `src/api/`, `src/config/` |
| `04_Frontend_Architecture.md` | React structure, components, hooks | `ui/` |
| `05_Database_Design.md` | Neo4j schema, Qdrant collections, blobs | `src/knowledge_graph/`, `src/embeddings/` |
| `06_Document_Ingestion.md` | Upload → OCR → clean → parse → store | `src/ingestion/`, `src/hierarchy/` |
| `07_Retrieval_Pipeline.md` | Every retrieval stage | `src/retrieval/`, `src/embeddings/retriever.py` |
| `08_HHGR_Algorithm.md` | Formal HHGR spec + pseudo-code | `src/retrieval/scorer.py`, `ranker.py` |
| `09_Explainability.md` | Evidence, provenance, verification | `src/llm/` |
| `10_AI_Models.md` | Every model used | `src/llm/llm.py`, `src/embeddings/models.py` |
| `11_Dataset.md` | Corpus and gold data | `data/`, `docs/Dataset.md` |
| `12_API_Documentation.md` | Every endpoint | `src/api/` |
| `13_System_Workflow.md` | End-to-end workflow | all `src/` |
| `14_Project_Features.md` | Feature-by-feature | all `src/`, `ui/` |
| `15_Configuration.md` | Env, Docker, dependencies | `src/config/`, `deploy/`, `docker-compose.yml` |
| `16_Experiments.md` | Evaluation protocols + measured results | `eval/`, `results/`, `evaluation/` |
| `17_Repository_Statistics.md` | Counts and inventory | whole repo |
| `18_Research_Contributions.md` | Novelty vs prior art | `paper/`, `src/`, results |
| `19_Limitations.md` | Limitations + future work | results + source |
| `20_Report_Mapping.md` | This mapping | — |

---

## 20.2 University research report mapping

| Report chapter | Content | Supporting docs | Code / artefacts |
|----------------|---------|-----------------|------------------|
| **Abstract** | HHGR for Indian legal QA | 01, 08, 18 | `README.md`, `paper/abstract.tex` |
| **1. Introduction** | Problem, motivation, objectives, contributions | 01, 18 | `README.md:20-28`, `paper/introduction.tex` |
| **2. Literature Review** | RAG, GraphRAG, RAGAS, BGE-M3, BM25 | 18 §18.3 | `paper/references.bib` |
| **3. Requirements & Scope** | Users, functions, non-functions | 01 §2–6, 14 | `ui/src/pages/`, `src/api/` |
| **4. System Design** | 9-module architecture, data stores, workflows | 02, 03, 04, 05, 13 | `src/`, `ui/`, `docs/ARCHITECTURE.md` |
| **5. Data & Dataset** | Corpus, hierarchy, gold sets | 11 | `data/`, `data/eval/gold/` |
| **6. Methodology — Retrieval** | HHGR algorithm, signals, fusion | 07, 08 | `src/retrieval/`, `src/embeddings/` |
| **6. Methodology — Ingestion** | Load/OCR/clean/parse/store | 06 | `src/ingestion/`, `src/hierarchy/` |
| **6. Methodology — Explainability** | Verification, confidence, provenance | 09 | `src/llm/` |
| **7. Implementation** | API, frontend, config, deployment | 03, 04, 12, 15 | `src/`, `ui/`, `deploy/` |
| **8. Models** | LLM, embeddings, OCR | 10 | `src/llm/llm.py`, `src/embeddings/models.py` |
| **9. Experiments & Results** | Protocols, tables, ablations, calibration | 16 | `eval/`, `results/`, `evaluation/` |
| **10. Discussion** | Interpretation, trade-offs | 16 §16.10, 19 | results |
| **11. Limitations & Future Work** | Gaps, roadmap | 19 | — |
| **12. Conclusion** | Contributions recap | 18, 01 | — |
| **Appendices** | API, statistics, config | 12, 17, 15 | `src/api/`, repo |

---

## 20.3 IEEE paper mapping

The repository already contains a LaTeX paper skeleton (`paper/`); the table maps each file to
its supporting evidence.

| Paper section | LaTeX file | Sources in repo | Supporting docs |
|---------------|-----------|-----------------|-----------------|
| Title/Abstract | `paper.tex`, `abstract.tex` | `README.md`, `src/config/settings.py` | 01, 18 |
| I. Introduction | `introduction.tex` | `README.md:20-28` | 01, 18 |
| II. Related Work | (in intro/`references.bib`) | `paper/references.bib` | 18 §18.3 |
| III. Methodology | `methodology.tex` | `src/retrieval/`, `src/embeddings/`, `src/llm/` | 07, 08, 09 |
| IV. System Architecture | (methodology) | `src/`, `ui/`, `docs/ARCHITECTURE.md` | 02, 03, 04, 05, 13 |
| V. Experimental Setup | `experiments.tex` | `data/eval/config/experiment.json`, `eval/` | 11, 16 |
| VI. Results | `results.tex` | `evaluation/reports/benchmark.md`, `results/evaluation_report.md` | 16 |
| VII. Discussion | (results/future) | results, ablations | 16 §16.10 |
| VIII. Future Work | `future-work.tex` | — | 19 |
| References | `references.bib` | — | 18 |
| Poster | `poster/poster.tex` | figures in `evaluation/figures/` | 16 |
| Slides | `presentation/slides.tex` | figures, architecture | 01, 16 |

---

## 20.4 Key results for the paper

Quote these **exact measured values** (from the repository):

**Offline systems comparison** (`evaluation/reports/benchmark.md`, 10 items):
- HHGR — MRR 0.7500, MAP 0.7500, NDCG@K 0.7631, Recall@K 0.8000, mean latency 2.569 ms.
- Dense — MRR 0.7000, MAP 0.6750, NDCG 0.7139.
- BM25 — MRR 0.7583, MAP 0.7283, NDCG 0.7781, Recall@K 0.9000.
- Graph — MRR 0.6500, MAP 0.6200, NDCG 0.6743.
- Naive-RAG — MRR 0.7000, MAP 0.6750, NDCG 0.7139.

**Ablation** (same file):
- full HHGR MRR 0.7500; `no_graph` 0.7000; `no_dense` 0.6500; `no_multilingual` 0.6500
  (citation accuracy 0.95 → 0.75); `no_hierarchy`/`no_explainability` unchanged on retrieval.

**Production run** (`results/evaluation_report.md`, 50 questions, **mock LLM**):
- Overall 0.6271 (Retrieval 0.5830 / Generation 0.4955 / Performance 0.9784).
- Retrieval: MRR 0.7400, section_accuracy 0.8700, hierarchy_accuracy 1.0000, recall@5 0.3316.
- Calibration: ECE 0.1792, MCE 0.1896.
- Performance: avg 108.09 ms, P95 146.94 ms.
- **Caveat to state explicitly:** generation metrics were produced with the mock LLM and do not
  reflect the Nemotron model.

---

## 20.5 Figures available for the report/paper

Ready-made figures in `evaluation/figures/` (SVG + PNG):

| Figure | Use |
|--------|-----|
| `architecture.{svg,png}` | System architecture section |
| `retrieval_flow.{svg,png}` | Retrieval pipeline section |
| `eval_comparison.{svg,png}` | Results — systems comparison |
| `ablation_chart.{svg,png}` | Results — ablation study |
| `latency_chart.{svg,png}` | Results — performance |
| `ragas_radar.{svg,png}` | Results — RAGAS-style metrics |
| `hierarchy_tree.{svg,png}` | Methodology — hierarchy |
| `kg_example.{svg,png}` | Methodology — knowledge graph |

Plus `results/reliability_diagram.png` for calibration.

---

## 20.6 Claims-to-evidence matrix (for reviewer defence)

| Claim | Defend with |
|-------|-------------|
| HHGR ranks correct provisions highest | `benchmark.md` MRR/MAP/NDCG |
| Graph signal matters | ablation `no_graph` |
| Dense signal matters | ablation `no_dense` |
| Multilingual path aids citation quality | ablation `no_multilingual` |
| Hierarchy paths are correct | `hierarchy_accuracy 1.0` |
| Explanations are complete | provenance-completeness column |
| Fast enough for interactive use | P95 146.94 ms; throughput 389 q/s (offline) |
| Trustworthy (honest) | ECE/MCE table; explicit mock-LLM caveat |

---

## 20.7 Reporting cautions

1. **Do not cite generation metrics** from the mock-LLM production run as model quality (L2).
2. **Report the small gold-set size** (10 grounded items) wherever retrieval numbers are used
   (L1).
3. **Report calibration honestly** — the system is currently over-confident (L3).
4. **Acknowledge BM25's higher raw recall** on the small set while explaining HHGR's better
   rank ordering (L5).
5. **State scope** — Indian statutes/judgments, public law text, research prototype, not legal
   advice (`19 §19.8`).

---

## 20.8 Where each deliverable lives in the repo

| Deliverable | Location |
|-------------|----------|
| This technical documentation package | `docs/report/01…20_*.md` |
| Hand-written developer docs | `docs/*.md` |
| IEEE paper source | `paper/*.tex`, `paper/references.bib` |
| Poster / slides | `paper/poster/`, `paper/presentation/` |
| Evaluation report (offline) | `evaluation/reports/benchmark.md` |
| Evaluation report (production) | `results/evaluation_report.md` |
| Figures | `evaluation/figures/`, `results/reliability_diagram.png` |
| Reproduction instructions | `scripts/reproduce.sh`, `16_Experiments.md §16.9` |
