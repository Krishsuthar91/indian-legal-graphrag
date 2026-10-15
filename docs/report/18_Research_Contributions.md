# 18 — Research Contributions

This document states the project's research contributions, positions them against prior art,
and grounds each in repository code and measured results. Prior-art references are the ones the
repository itself cites (`paper/references.bib`: RAG, GraphRAG, RAGAS, BGE-M3, BM25).

---

## 18.1 Problem setting

Legal question answering over Indian statutes requires (i) structure-aware retrieval,
(ii) answers that are grounded in cited provisions, and (iii) auditability. Standard
Retrieval-Augmented Generation (RAG, Lewis et al.) optimises single-vector similarity and
provides no structural, citation, or verification guarantees. GraphRAG introduces graph
structure but for corpus-level summarisation rather than per-query legal ranking and
auditing. This project contributes a **hybrid hierarchical graph retrieval + verification**
stack specialised for law.

---

## 18.2 Contributions

### C1 — HHGR: Hybrid Hierarchical Graph Retrieval
A four-signal graph scoring function (`text`, `citation`, `hierarchy`, `structural`) whose
output feeds a dense/graph/hierarchy fusion layer, then a five-signal explainability
re-ranking (`src/retrieval/scorer.py`, `src/embeddings/retriever.py`,
`src/llm/explanation.py`). Formalised in `08_HHGR_Algorithm.md`.

**Evidence.** In the controlled offline benchmark, HHGR achieves the **best MRR/MAP/NDCG**
among HHGR, dense, BM25, graph, and naive-RAG (`MRR 0.75`, `MAP 0.75`, `NDCG 0.7631`;
`evaluation/reports/benchmark.md`).

### C2 — Two-layer signal fusion
A robust, interpretable graph score is fused with dense similarity, and the result is
re-ranked by an explainable five-signal usefulness score. This separation lets the system
recover from failures at either level and exposes every contribution
(`src/embeddings/retriever.py:23-27`, `src/llm/explanation.py:62-76`).

### C3 — Verification-gated generation for law
A six-stage verification framework (sufficiency via bigram Dice, LLM relevance judge +
fallback, claim-level entailment, calibration, counter-authority detection, verification
badge) gates generation and produces one of five trust labels
(`src/llm/service.py:275-328`, `docs/VerificationFramework.md`). Contributions F8/F9 in
`14_Project_Features.md`.

### C4 — Counter-authority detection
Automatic detection of overruled/superseded/repealed/void/not-in-force markers with ranking
and verification impact (`src/llm/explanation.py:1433-1452`). To our knowledge this is not a
standard component of RAG pipelines, yet it is essential in law.

### C5 — Corpus-verified query expansion (anti-hallucination)
Expansion to section numbers only when those sections exist in the corpus, and all expansions
are recorded (`src/retrieval/query_expansion.py:453-532`). Expansion cannot invent
references — a structural guarantee rather than a probabilistic one.

### C6 — Explainability-first provenance
Per-signal scores, hierarchy paths, numbered citations, confidence factors, counter-authority
markers, and a full decision trace are emitted for every answer and persisted immutably for
re-fetch (`src/llm/provenance.py`, `GET /api/v1/provenance/{id}`). Measured provenance
completeness is high (0.95 typical; `evaluation/reports/benchmark.md`).

### C7 — Multilingual legal retrieval
Script/language detection plus multilingual embeddings and tokenization give cross-lingual
retrieval (`src/ingestion/detection/language_detector.py`, `src/retrieval/query.py:155-172`).
The ablation shows removing the multilingual path lowers citation accuracy from **0.95 to
0.75** (`evaluation/reports/benchmark.md`).

### C8 — Canonical corpus management
Duplicate hierarchy artefacts are grouped by normalised Act title and reduced to one canonical
document per Act, making imports and evaluation deterministic
(`src/knowledge_graph/canonical.py`).

### C9 — Open, reproducible evaluation harness
A deterministic, offline benchmark compares HHGR against four baselines and runs six
ablations, producing tables and figures (`eval/`, `evaluation/`). The protocol is pinned in
`data/eval/config/experiment.json` (`seed 42`, `runs 3`, `force_deterministic`).

### C10 — Integrated open-source system
A complete, deployable system (FastAPI backend, React SPA, Docker Compose, monitoring,
94+ backend tests, CI) that operationalises C1–C9 (`src/`, `ui/`, `deploy/`, `tests/`).

---

## 18.3 Positioning against prior art

| Prior work | What it does | Gap this project addresses |
|-----------|--------------|----------------------------|
| **RAG** (Lewis et al.) | Retrieve dense passages → generate | No structure, no citation grounding, no verification |
| **GraphRAG** (Microsoft) | Build entity graph → community summaries | Corpus-level summarisation, not per-query legal ranking/auditing |
| **RAGAS** | Metrics for RAG evaluation | A metric suite, not a retrieval/verification method |
| **BGE-M3** | Multilingual embeddings | Used here as the dense component; not a full retrieval algorithm |
| **BM25** | Lexical ranking | Used here as a baseline; no hierarchy/citation signals |
| **Legal QA systems** (general) | Domain QA | Typically lack verification gating, counter-authority handling, and provenance |

**Where HHGR differs:** it treats legal **structure and cross-references** as first-class
ranking signals (not context to be flattened) and treats **verification and provenance** as
part of the algorithm, not an afterthought.

---

## 18.4 Claims vs. evidence

| Claim | Evidence | Status |
|-------|----------|--------|
| HHGR ranks correct provisions highest among baselines | MRR 0.75 / MAP 0.75 / NDCG 0.763 (offline) | supported (small gold set) |
| Graph signal improves ranking | ablation `no_graph`: MRR 0.75→0.70 | supported |
| Dense signal is essential | ablation `no_dense`: MRR 0.75→0.65 | supported |
| Multilingual path aids citations | ablation `no_multilingual`: citation acc 0.95→0.75 | supported |
| Hierarchy/graph paths are correct | hierarchy_accuracy 1.0 (offline & production) | supported |
| End-to-end generation quality | not established (committed run used mock LLM) | **not yet demonstrated** |
| Calibration | ECE 0.179 / MCE 0.190 (moderate) | partial — over-confident |

---

## 18.5 Novelty summary

The strongest, cleanly demonstrable novelties are:

1. **HHGR** — multi-signal hierarchical graph retrieval specialised for legal structure (C1,
   C2).
2. **Verification-gated legal generation with counter-authority awareness** (C3, C4).
3. **Corpus-verified expansion as a hallucination-prevention guarantee** (C5).
4. **Explainability-first provenance** integrated end-to-end (C6).

C7–C10 are engineering/empirical contributions that make the system usable and reproducible.

---

## 18.6 Suggested paper framing

- **Title:** HHGR — Hybrid Hierarchical Graph Retrieval for Indian Legal Document Intelligence.
- **Core claim:** structural legal signals materially improve ranking and enable auditable,
  verifiable legal QA.
- **Primary results table:** the offline systems comparison (MRR/MAP/NDCG) plus the ablation
  study; report the production retrieval metrics (MRR 0.74, hierarchy accuracy 1.0) and state
  clearly that generation was evaluated with a mock LLM.
- **Limitations:** small gold set, mock-LLM generation in the committed run, moderate
  calibration (see `19_Limitations.md`).

See `20_Report_Mapping.md` for section-by-section mapping.
