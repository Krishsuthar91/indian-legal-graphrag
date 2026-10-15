# 14 — Project Features

This document describes each feature of the system: what it does, why it matters, where it is
implemented, and how it manifests to the user. Every feature is grounded in repository code.

---

## 14.1 Feature map

| # | Feature | Primary code | User surface |
|---|---------|--------------|--------------|
| F1 | Hybrid Hierarchical Graph Retrieval (HHGR) | `src/retrieval/scorer.py`, `ranker.py` | Better-ranked evidence |
| F2 | Hierarchy-aware retrieval | `src/retrieval/context.py` | Hierarchy path / tree |
| F3 | Dense multilingual retrieval | `src/embeddings/*` | Cross-lingual answers |
| F4 | Explainability engine | `src/llm/explanation.py` | Reasoning chain, scores |
| F5 | Full provenance | `src/llm/provenance.py`, `src/api/qa.py` | Provenance panel / by id |
| F6 | Legal knowledge graph | `src/knowledge_graph/*` | Cytoscape graph |
| F7 | Confidence scoring & calibration | `src/llm/explanation.py`, `src/evaluation/calibration.py` | Confidence gauge |
| F8 | Verification framework | `src/llm/service.py`, `docs/VerificationFramework.md` | Verification badge |
| F9 | Hallucination prevention / grounding guard | `src/llm/service.py` | Grounded refusals |
| F10 | Counter-authority detection | `src/llm/explanation.py:1433-1452` | Counter-authority markers |
| F11 | Multilingual support | `src/ingestion/detection/language_detector.py`, `src/retrieval/query.py` | Answers in Hindi/Tamil/… |
| F12 | Document upload & indexing | `src/api/documents.py`, `src/ingestion/` | Upload page |
| F13 | NVIDIA Nemotron integration | `src/llm/llm.py:563-616` | Answer generation |
| F14 | Web dashboard | `ui/src/` | SPA |
| F15 | Monitoring & deployment | `deploy/`, `monitoring/` | Ops |
| F16 | Offline evaluation harness | `eval/`, `src/evaluation/` | Paper tables |
| F17 | Deterministic reproducible mode | `src/embeddings/models.py`, `experiment.json` | Reproducible benchmarks |
| F18 | Canonical corpus management | `src/knowledge_graph/canonical.py` | Consistent retrieval |

---

## F1 — Hybrid Hierarchical Graph Retrieval (HHGR)

**What:** a four-signal graph scoring function (text, citation, hierarchy, structural) whose
output is fused with dense and hierarchy signals (`src/retrieval/scorer.py:18-24`,
`src/embeddings/retriever.py:23-27`). Fully specified in `08_HHGR_Algorithm.md`.

**Why:** flat similarity ignores legal structure; HHGR makes structure a ranking signal.

**Implementation:** `scorer.py` computes signals; `ranker.py` sorts/thresholds; `retriever.py`
fuses. Weights are configurable and ablatable (`eval/ablation.py`).

---

## F2 — Hierarchy-aware retrieval

**What:** seed matches propagate to ancestors, descendants, and siblings along `PART_OF`,
bounded to one document (`src/retrieval/context.py:89-149`).

**Why:** a Section's meaning depends on its Chapter and its Clauses; retrieving in isolation
loses context.

**Surface:** the `HierarchyTree.tsx` view highlights the active path; evidence items carry a
`hierarchy_path`.

---

## F3 — Dense multilingual retrieval

**What:** semantic search over four Qdrant collections using a configurable multilingual
embedding model (`src/embeddings/models.py:37-84`, `store.py`, `indexer.py`).

**Why:** paraphrases and cross-lingual queries need semantic, not just lexical, matching.

---

## F4 — Explainability engine

**What:** builds a reasoning chain, re-fuses five signals for usefulness ranking, applies
definition promotion/fragment demotion, and computes confidence
(`src/llm/explanation.py:62-76`, `567-872`, `1107-1123`). Fully specified in
`09_Explainability.md`.

**Surface:** `ReasoningChain.tsx`, `EvidenceCard.tsx`, per-signal score breakdowns.

---

## F5 — Full provenance

**What:** every query persists an immutable provenance record; it is re-fetchable by id
(`src/llm/provenance.py`, `GET /api/v1/provenance/{id}`).

**Why:** legal users must audit and reproduce answers.

**Surface:** `ProvenancePanel.tsx`, `Provenance.tsx` page.

---

## F6 — Legal knowledge graph

**What:** a graph of `Document/Chapter/Section/Clause` nodes with `PART_OF` and `CITES` edges
(`src/knowledge_graph/importer.py`, `schema.py`, `traversal.py`, `citation_extractor.py`), on
Neo4j or `InMemoryGraph`.

**Why:** cross-references and containment are the connective tissue of legal reasoning.

**Surface:** `KnowledgeGraph.tsx` (Cytoscape).

---

## F7 — Confidence scoring and calibration

**What:** a composite confidence from retrieval strength, signal agreement, sufficiency,
entailment ratio, and counter-authority penalty, calibrated with ECE/MCE
(`src/llm/explanation.py:1857-2017`, `src/evaluation/calibration.py`).

**Why:** a stated confidence must mean something empirically.

**Surface:** `ConfidenceGauge.tsx`; `results/reliability_diagram.png`.

---

## F8 — Verification framework

**What:** staged verification (sufficiency via bigram Dice → relevance judge → claim-level
entailment → calibration → counter-authority → badge)
(`src/llm/service.py:275-328`, `docs/VerificationFramework.md`).

**Badges:** `supported`, `insufficient_evidence`, `contradicted`, `no_evidence`, `no_answer`.

**Surface:** `VerificationBadge.tsx`.

---

## F9 — Hallucination prevention / grounding guard

**What:** the guard compares the generated answer against evidence; if unsupported, it
downgrades the badge and may return a grounded refusal instead of an answer
(`src/llm/service.py:275-328`).

**Plus:** corpus-verified expansion (`src/retrieval/query_expansion.py:453-532`) ensures no
invented sections. Fully discussed in `09_Explainability.md §9.10`.

---

## F10 — Counter-authority detection

**What:** flags provisions containing overruled/superseded/repealed/void/not-in-force markers
and biases verification toward caution (`src/llm/explanation.py:1433-1452`).

**Why:** citing repealed or overruled law is a serious legal error.

---

## F11 — Multilingual support

**What:** script/language detection (`src/ingestion/detection/language_detector.py:12-33`) plus
multilingual tokenization (`src/retrieval/query.py:155-172`) and multilingual embeddings
(bge-m3 / MuRIL / LaBSE / IndicBERT).

**Why:** Indian legal questions are asked in many languages.

---

## F12 — Document upload and indexing

**What:** `POST /api/v1/documents/upload` validates, stores, and runs the full ingestion →
hierarchy → graph → index pipeline (`src/api/documents.py:165`, `src/ingestion/`).

**Surface:** `Upload.tsx` with indexing status.

**Detail:** `06_Document_Ingestion.md`.

---

## F13 — NVIDIA Nemotron integration

**What:** production generation via NVIDIA NIM
(`nvidia/nemotron-3-super-120b-a12b`) with a single-source-of-truth model id
(`src/llm/llm.py:563-616`, `src/config/settings.py`).

**Why:** a strong, hosted, OpenAI-compatible model without self-hosting.

---

## F14 — Web dashboard

**What:** a React SPA with five pages and rich visualisations (KG, hierarchy, confidence,
provenance) (`ui/src/`). Detail in `04_Frontend_Architecture.md`.

**Surface:** Home, Explain, Upload, Provenance, Settings.

---

## F15 — Monitoring and deployment

**What:** Docker Compose stack (`api`, `react`, `nginx`, `neo4j`, `qdrant`, `redis`) with
Prometheus/Grafana monitoring, health checks, and a validated production entrypoint
(`docker-compose.yml`, `deploy/`, `monitoring/`).

**Detail:** `15_Configuration.md`.

---

## F16 — Offline evaluation harness

**What:** `eval/` compares HHGR against dense/BM25/graph/naive-RAG baselines and runs six
ablations, producing tables and figures in `evaluation/` (`eval/harness.py`, `ablation.py`,
`figures.py`, `reports.py`).

**Why:** the paper's claims must be reproducible without network or GPU.

**Detail:** `16_Experiments.md`.

---

## F17 — Deterministic reproducible mode

**What:** a deterministic hash embedding plus pinned seeds/runs
(`experiment.json`: `seed 42`, `runs 3`, `force_deterministic true`), gated in production by
`EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK`.

**Why:** benchmarks must be bit-reproducible; production must not degrade silently.

---

## F18 — Canonical corpus management

**What:** duplicate hierarchy files are grouped by normalised Act title and reduced to one
canonical file per Act (`src/knowledge_graph/canonical.py`; e.g. `indian contract act` →
`0d1934142f67c5f5`).

**Why:** duplicate artifacts otherwise pollute retrieval and evaluation.

---

## 14.2 Feature-to-report mapping

| Feature cluster | Paper/report section |
|-----------------|----------------------|
| F1, F2 | Methodology / HHGR algorithm |
| F3, F13 | Retrieval & generation stack |
| F4, F5, F10 | Explainability & provenance |
| F7, F8, F9 | Verification & trustworthiness |
| F11 | Multilingual evaluation |
| F16, F17 | Experiments & results |
| F14, F15 | System/deployment description |

Full mapping in `20_Report_Mapping.md`.
