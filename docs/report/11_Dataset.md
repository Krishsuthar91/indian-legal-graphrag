# 11 — Dataset

This document describes the corpus the system operates over and the gold evaluation datasets
used to benchmark it. Figures were measured directly against the working tree.

Primary sources: `data/eval/gold/*`, `data/eval/manifest.json` (inside `gold/`),
`data/eval/config/experiment.json`, `data/eval/contract_act_1872_benchmark.csv`,
`docs/Dataset.md`, `data/hierarchy/`, `data/processed/`.

---

## 11.1 Data inventory

| Artefact | Location | Count | Purpose |
|----------|----------|-------|---------|
| Parsed hierarchies | `data/hierarchy/*.json` | **295** | Document→Chapter→Section→Clause trees |
| Processed documents | `data/processed/*.json` | **1632** | Cleaned per-page text + metadata |
| Provenance records | `data/provenance/*.json` | **271** | Persisted query provenance |
| Uploaded raw files | `data/uploads/` | 2 | Retained originals |
| Gold datasets | `data/eval/gold/*.json` | 5 + manifest | Retrieval/answer evaluation |
| Benchmark questions | `data/eval/contract_act_1872_benchmark.csv` | 50 | Production benchmark |
| Experiment config | `data/eval/config/experiment.json` | 1 | Reproducible eval parameters |
| Embedding snapshots | `data/embeddings/snapshot_*.json.gz` | — | Re-index without recompute |

The large gap between 1632 processed documents and 295 hierarchy files reflects the corpus
containing many duplicates/variants; the canonical layer
(`src/knowledge_graph/canonical.py`) reduces these to one canonical file per Act.

---

## 11.2 The legal corpus

The corpus is a collection of **Indian legal documents** — statutes and judgments with a deep
hierarchical structure. Prominent Acts include:

- **The Indian Contract Act, 1872** (canonical id `0d1934142f67c5f5`)
- **The Indian Penal Code, 1860** (canonical id `cf20a14c52127fd5`)
- **The Bharatiya Nyaya Sanhita (BNS)** — successor to the IPC
- **The Bharatiya Nagarik Suraksha Sanhita (BNSS)**
- **The Bharatiya Sakshya Adhiniyam (BSA)**
- **Supreme Court judgments** (cross-referencing statutes)

The gold domains in the manifest (`bns`, `bnss`, `bsa`, `contract_act`, `sc_judgments`) mirror
these groups. A curated subset of 50 benchmark questions focuses on **Chapter V of the Indian
Contract Act, 1872** (see §11.5).

### 11.2.1 Hierarchy shape

Every document parses into four levels:

```text
Document
 └── Chapter / Part        (Roman numerals, "CHAPTER", "PART")
      └── Section / Article ("1.", "Section 3", "Art. 21")
           └── Clause / Illustration / Proviso ((a), (1), "Provided that", "Illustration")
```

### 11.2.2 Canonical corpus

Because many hierarchy files describe the same Act, `src/knowledge_graph/canonical.py` groups
them by normalised Act title and nominates a single canonical document. Verified mappings:

| Normalised term | Canonical document id |
|-----------------|-----------------------|
| `indian contract act` | `0d1934142f67c5f5` |
| `indian penal code` | `cf20a14c52127fd5` |

---

## 11.3 Gold evaluation datasets

Gold data lives in `data/eval/gold/`. The manifest
(`data/eval/gold/manifest.json`) declares **34 items total, 10 grounded**:

```json
{
  "schema_version": "1.0",
  "dataset_name": "explaintool-eval",
  "files": ["bns_gold.json","bnss_gold.json","bsa_gold.json",
            "contract_act_gold.json","sc_judgments_gold.json"],
  "total_items": 34,
  "grounded_items": 10,
  "by_domain": {"bns":6,"bnss":6,"bsa":6,"contract_act":10,"sc_judgments":6},
  "document_id": "0940d367554383c5"
}
```

| File | Domain | Items | Notes |
|------|--------|-------|-------|
| `contract_act_gold.json` | Indian Contract Act | 10 | ids `ica-001`…`ica-010`; `document_id 0940d367554383c5` |
| `bns_gold.json` | Bharatiya Nyaya Sanhita | 6 | — |
| `bnss_gold.json` | Bharatiya Nagarik Suraksha Sanhita | 6 | — |
| `bsa_gold.json` | Bharatiya Sakshya Adhiniyam | 6 | — |
| `sc_judgments_gold.json` | Supreme Court judgments | 6 | — |
| `manifest.json` | — | — | Aggregate metadata |

### 11.3.1 Gold item structure

Each gold item pairs a natural-language question with its expected grounded evidence
(section numbers / node ids) and, where applicable, an expected answer or verification status.
The 10 **grounded** items are the subset with verified expected citations, which is what
retrieval metrics (Precision@k, Recall@k, MRR, NDCG) are computed against.

---

## 11.4 Evaluation configuration

`data/eval/config/experiment.json` pins the reproducible evaluation protocol:

| Parameter | Value |
|-----------|-------|
| seed | 42 |
| top_k | 5 |
| runs | 3 |
| embedding provider | deterministic (force_deterministic = true) |
| hybrid weights | dense 0.40, graph 0.35, hierarchy 0.25 |
| confidence threshold | 0.45 |
| quick_items | 3 |
| ablation variants | full, no_graph, no_hierarchy, no_dense, no_multilingual, no_explainability |
| compared systems | hhgr, dense, bm25, graph, naive_rag |
| dataset | `data/eval/gold`, document `0940d367554383c5` |
| hierarchy file | `data/hierarchy/0940d367554383c5.json` |
| output | `evaluation/`, reports in `evaluation/reports`, figures in `evaluation/figures` |

See `16_Experiments.md` for the resulting tables.

---

## 11.5 Benchmark question set

`data/eval/contract_act_1872_benchmark.csv` contains **50 questions** (51 lines including the
header) drawn from **Chapter V of the Indian Contract Act, 1872** (void/voidable agreements,
contingent contracts, etc.). This is the dataset used by the production evaluation script
`scripts/run_final_evaluation.py`, whose results populate `results/`.

---

## 11.6 Data provenance and licence

- Uploaded documents and their derived artefacts (processed, hierarchy, provenance) are stored
  locally under `data/`; they are runtime data, not source.
- The repository is licensed **MIT** (`LICENSE`); legal source texts are public Indian statutes
  and judgments.
- Gold datasets are project-authored evaluation assets (schema version 1.0).

---

## 11.7 Data quality controls

| Control | Mechanism | Source |
|---------|-----------|--------|
| Deduplication | canonical Act grouping | `src/knowledge_graph/canonical.py` |
| Corpus integrity | audit script | `scripts/audit_corpus.py` |
| Duplicate reporting | dedup report | `scripts/corpus_dedup_report.py` |
| Retention | pruning | `scripts/prune_stale_artifacts.py`, `src/ingestion/pruning.py` |
| Reproducibility | pinned experiment config | `data/eval/config/experiment.json` |

---

## 11.8 Gaps / not found

- A single consolidated corpus manifest listing every source document with metadata is
  **not found in repository**; hierarchy and processed directories are the de-facto manifest.
- Per-document annotation for the *full* corpus (beyond the 34 gold items) is **not found in
  repository**.
