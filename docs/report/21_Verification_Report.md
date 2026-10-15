# 21 — Final Verification Report (Docs 01–20 vs. Source)

**Scope:** Direct source-inspection pass over `C:\Users\Krish\Project2` verifying the claims made
in `docs/report/01` … `docs/report/20` against the code they describe. Every claim is tagged
`VERIFIED`, `PARTIALLY VERIFIED`, `NOT FOUND`, or `OUTDATED`. Metric provenance (where a
number is computed) and architecture/algorithm provenance (where a behaviour is implemented)
are stated as exact files.

**Method:** Only first-hand reads of repo files — no subagents, no model recall. The full
runtime path was inspected: `src/{config,main,api,models,middleware,monitoring,retrieval,llm,
embeddings,knowledge_graph,hierarchy,ingestion,evaluation}`; the offline benchmark module
`eval/`; `ui/src`; `deploy/`; `docker-compose*.yml`; `monitoring/`; `data/eval/*`;
`evaluation/reports/benchmark.md`; `results/*`.

---

## 0. Headline results

| Id | Doc | Score | Status |
|----|-----|-------|--------|
| 01 | Project Overview | 0.90 | Accurate |
| 02 | Folder Structure | 0.92 | Accurate |
| 03 | Backend Architecture | 0.85 | Accurate (minor drift) |
| 04 | Frontend Architecture | 0.55 | **Materially mis-cites component/hook/API names** |
| 05 | Database Design | 0.88 | Accurate |
| 06 | Document Ingestion | 0.90 | Accurate |
| 07 | Retrieval Pipeline | 0.82 | Mostly accurate; conflates re-fusion with retrieval |
| 08 | HHGR Algorithm | 0.52 | **Three of four signal definitions wrong** |
| 09 | Explainability | 0.50 | **Badges, sufficiency, ECE/MCE source, markers wrong** |
| 10 | AI Models | 0.90 | Accurate (registry + providers) |
| 11 | Dataset | 0.75 | Partially verified |
| 12 | API Documentation | 0.90 | Accurate |
| 13 | System Workflow | 0.80 | Consistent with pipeline |
| 14 | Project Features | 0.85 | Accurate |
| 15 | Configuration | 0.58 | **Several variable names/defaults wrong** |
| 16 | Experiments | 0.90 | Accurate (benchmark artifacts match) |
| 17 | Repository Statistics | 0.70 | Plausible; not fully re-verified |
| 18 | Research Contributions | 0.78 | Partially verified |
| 19 | Limitations | 0.85 | Narrative matches off-by-default features |
| 20 | Report Mapping | 0.90 | Consistent |

**Repository completeness score: 68 / 100**

Rubric: per-doc ratio of central claims directly supported by inspected source, weighted by
claim-richness (docs 04, 08, 09, 15 weight 2; 20 weight 0.5; all others 1). `sum = 17.45 /
25.5 = 0.684 → 68`. The score is dragged down almost entirely by the four mis-citing documents;
the runtime code itself is coherent and thoroughly implemented.

---

## 1. Claims verified (verbatim source support)

### 1.1 Retrieval pipeline (`src/retrieval/`) — VERIFIED
- Four weighted signals in the graph-ranking scorer
  `src/retrieval/scorer.py` — `WEIGHTS`: text `0.40`, hierarchy `0.25`, citation `0.20`,
  structural `0.15`, leaf `0.00` (sums to 1.0). `LEAF_LABELS` = `{section, clause, article,
  rule, order, paragraph, subclause}`.
- Signal internals (directly inspected):
  - `text_score` (`scorer.py`) — keyword coverage over title/text + title bonus.
  - `citation_score` — exact numbering match or word-boundary reference match.
  - `structural_importance` — node degree + `0.1 * subtree_size`, query-independent.
- Orchestration `src/retrieval/ranker.py`: parse query → select seed nodes (`TEXT_THRESHOLD =
  0.25`) → propagate hierarchical evidence (`propagate_hierarchy`) → score candidates → return
  top-k with signal breakdown, `SNIPPET_CHARS = 400`, `RetrievalResult` dataclass.
- Query parsing `src/retrieval/query.py`: `_STOPWORDS`, `_SECTION_LABELS`
  (`section/rule/article/order`), `_ACT_NAME_TO_DOC_ID` (e.g. "indian contract act" →
  `0d1934142f67c5f5`), citations via `src/knowledge_graph/citation_extractor.py`.
- Intent-routing `src/retrieval/intent.py`: **8 intents** (definition, section_lookup,
  punishment, procedural, constitutional, case_law, comparison, explanation) with adaptive
  budgets `EASY_TOP_K=4`, `MEDIUM_TOP_K=7`, `COMPLEX_TOP_K=12`.
- Context propagation `src/retrieval/context.py`: `get_ancestor_chain` (PART_OF walk to root),
  `get_descendant_ids` (BFS), `get_related_nodes`.
- Deterministic query expansion `src/retrieval/query_expansion.py`: enabled by default
  (`QA_QUERY_EXPANSION_ENABLED`, default `True`, since V2.4.1), corpus-aware
  (`available_sections`), `VERIFIED_SECTION_MAPPING` for verified section references.

### 1.2 Embedding subsystem (`src/embeddings/`) — VERIFIED
- `models.py`: six-entry registry — `BAAI/bge-m3` (dim 1024, max-seq 8192, **default**),
  `BAAI/bge-large-en-v1.5`, `intfloat/e5-large-v2` (requires `query:`/`passage:` prefixes via
  `ModelSpec`), `sentence-transformers/LaBSE`, `google/muril-base-cased`,
  `ai4bharat/indic-bert`.
- `providers.py`: `DETERMINISTIC_PROVIDER = "deterministic"`; `DeterministicEmbeddingProvider`
  (blake2b hash, default dim 64, device cpu); heavy libs imported lazily.
- `store.py`: `QdrantStore` with in-memory/server modes; collection per hierarchy granularity
  (`documents, chapters, sections, clauses`); `point_id` = deterministic **UUID5** of
  `node_id` (namespace `00000000-0000-4000-8000-000000000001`); `SCROLL_BATCH = 512`;
  snapshots `snapshot_{key}.json.gz` under `EMBEDDING_SNAPSHOT_DIR`.
- `retriever.py`: `VectorRetriever` fuses only `dense/graph/hierarchy`
  (`_SIGNALS`), `DEFAULT_HYBRID_WEIGHTS` = dense `0.40`, graph `0.35`, hierarchy `0.25`.
- `indexer.py`: `HierarchyIndexer`, node text = title + body, `text_hash` (md5), payload fields
  `{node_id, collection, doc_id, node_type, language, level, numbering, title, text, text_hash}`,
  incremental.
- `service.py`: `EmbeddingService`, `DEFAULT_BATCH_SIZE = 32`, length-stratified batching.

### 1.3 Knowledge graph (`src/knowledge_graph/`) — VERIFIED
- `schema.py`: `NodeLabel` = {Document, Chapter, Part, Section, Clause, Schedule, Case, Court,
  Judge, LegalConcept, Amendment}; `RelType` = {PART_OF, CITES, REFERENCES, INTERPRETS,
  APPLIES, FOLLOWS, DISTINGUISHES, OVERRULES, AMENDS, REPEALS, PARALLEL_TRANSLATION_OF};
  `HIERARCHY_TYPE_MAP`; `INDEX_STATEMENTS`.
- `citation_extractor.py`: `Citation` dataclass + regexes for `Section`, `Rule 45-A`,
  `Article 14`, `Order VII Rule 11`, `AIR 1965 SC 123`, `(2001) 2 SCC 123`,
  `2001 SCC (Cri) 123`.
- `canonical.py` (Task 18): canonical selection = highest node count → highest section count →
  newest parser format → stable canonical ids (`indian contract act`→`0d1934142f67c5f5`,
  `indian penal code`→`cf20a14c52127fd5`) → newest mtime; files skipped, **never deleted**.
- `traversal.py`: `get_parent/get_children/get_neighbors`, `citation_chain` (BFS over CITES +
  REFERENCES, `max_depth=5`).
- `importer.py` + `neo4j_driver.py`: `import_hierarchy_json` (Document node first, then
  children), `InMemoryGraph` (`_nodes/_node_labels/_edges/_adj_out/_adj_in`).

### 1.4 Hierarchy engine (`src/hierarchy/`) — VERIFIED
- `models.py`: `HierarchyNode`, `NestedSetEntry`, `HierarchyWarning` types
  `{missing_parent, duplicate_numbering, broken_nesting}`, `ParsedHierarchy`.
- `patterns.py`: roman-numeral mapping (I–XXX) and level constants `LVL_DOCUMENT=0`,
  `LVL_ACT_TITLE=1`, `LVL_SCHEDULE=1`, `LVL_APPENDIX=1`, `LVL_PREAMBLE=2`, `LVL_PART=3`,
  `LVL_CHAPTER=4`, … (section levels follow).
- `parser.py`: `PROCESSED_DIR = data/processed`, `HIERARCHY_DIR = data/hierarchy`; TOC
  detection (`ARRANGEMENT OF SECTIONS`, `TABLE OF CONTENTS`, `CONTENTS`, `INDEX`); body-start
  re `ACT NO. 45 OF 1860` / `[9 OF 1872]`.
- `tree_builder.py`: root `node_id = "root"`; stack-based parent assignment; DFS nested-set
  build (left/right/depth); `validators.py` re-checks the three warning types.

### 1.5 LLM service (`src/llm/`) — VERIFIED
- `llm.py`: retry policy — **429 is never retried**; transient codes `{500,502,503,504}`;
  `_BACKOFF_BASE_SECONDS = 1.0`, `_MAX_BACKOFF_SECONDS = 16.0`; `LLMError/LLMTimeoutError/
  LLMConnectivityError`; `MockLLMClient` is the deterministic offline default.
- `service.py`: `INSUFFICIENT_EVIDENCE_ANSWER` guard sentence;
  `INSUFFICIENT_EVIDENCE_MODEL = "grounding-guard"`; grounding-guard thresholds enforced by
  `_should_generate_answer`.
- `prompts.py`: `MAX_EVIDENCE_CHARS = 500`, `MAX_CHAIN_STEPS = 8`.

### 1.6 Ingestion (`src/ingestion/pipeline.py`) — VERIFIED
- Supported `.pdf/.docx/.txt`; `OUTPUT_DIR = data/processed`; content-based
  `resolve_document_id`; title derived from first lines; knowledge-graph import +
  hierarchy build + optional embedding of each ingested act.

### 1.7 Evaluation core (`src/evaluation/`) — VERIFIED
- `metrics/retrieval.py`: Recall@5, Recall@10, Precision@5, **MRR**, Section Accuracy,
  Hierarchy Accuracy. **No MAP, no NDCG here.**
- `metrics/generation.py`: answer_accuracy (token F1), grounding_accuracy, citation_accuracy,
  faithfulness, evidence_coverage, hallucination_rate (uses `INSUFFICIENT_EVIDENCE_ANSWER`).
- `metrics/aggregate.py`: `RETRIEVAL_METRIC_KEYS` = {recall_at_5, recall_at_10, precision_at_5,
  mrr, section_accuracy, hierarchy_accuracy}; `GENERATION_METRIC_KEYS` = {answer_accuracy,
  grounding_accuracy, citation_accuracy, faithfulness, evidence_coverage, hallucination_rate};
  **overall score = 0.4·retrieval + 0.4·generation + 0.2·performance**;
  `META_COLUMNS` = (item_id, question, query_type, difficulty).
- `metrics/performance.py`: mean/p50/p95 latency, `process_rss_mb` (psutil),
  `_LATENCY_BUDGET_MS = 5000.0`, tracemalloc.
- `calibration.py`: **ECE and MCE** live here alone (`_NUM_BINS = 10`).

### 1.8 Offline benchmark module `eval/` (Module 10) — VERIFIED
- `systems.py`: systems = hhgr, dense, bm25 (`_BM25_K1=1.5`, `_BM25_B=0.75`), graph,
  naive_rag; `RankedHit`.
- `metrics/retrieval.py`: Recall@K, Precision@K, **Hit Rate@K, MRR, MAP, NDCG@K**, latency
  stats. **MAP and NDCG exist only in this file** (not in `src/evaluation/`).
- `metrics/semantic.py`: `EmbeddingCache` (deterministic provider, dim 64, seed 42).
- `metrics/ragas.py`: five offline RAGAS surrogates (faithfulness, answer_relevancy,
  context_recall, context_precision, answer_correctness) on the same `EmbeddingCache`;
  `ragas_available()/ragas_context()` gate the optional native package.
- Reproducibility wiring: `data/eval/config/experiment.json` (seed 42, top_k 5, deterministic
  embeddings forced, `hybrid_weights` dense .4/graph .35/hier .25, `confidence_threshold`
  0.45, 6 ablation variants, 5 systems). Outputs land in `evaluation/reports/benchmark.md`
  (+ .json/.pdf) and `evaluation/figures/*`, produced through `eval/harness.py` +
  `eval/reports/*` + `eval/figures/*`.
- Gold sets exist for contract_act, bns, bnss, bsa, sc_judgments
  (`data/eval/gold/*_gold.json` + `manifest.json`).

### 1.9 API, health, monitoring, middleware (`src/main.py`, `src/api/`, `src/middleware/`, `src/monitoring/`) — VERIFIED
- Router prefix `/api/v1`; root `GET /` returns `{service, version, docs}`; liveness/readiness
  endpoints (`/health`, `/ready`, `/live`); `/metrics` Prometheus exposition from
  `src/monitoring/metrics.py` (`http_requests_total`, `http_request_duration_ms`,
  `process_rss_bytes`).
- Middleware order Metrics → Security → CORS (`MetricsMiddleware`, `SecurityMiddleware`);
  security features implemented but **disabled by default** (`API_KEY_AUTH_ENABLED`,
  `RATE_LIMIT_ENABLED`, `REQUEST_MAX_BODY_BYTES`), backing doc 19's limitation narrative.
- QA request schema carries `query` (plus optional top-k); uploads accept PDF/DOCX/TXT; the
  uploaded file is **deleted after processing** (pipeline `dest.unlink`), matching doc 19.

### 1.10 Config precedence (`src/config/settings.py` + `deploy/env/`) — VERIFIED
- Load order (highest first): process env → `.env.development.local` (git-ignored) →
  `.env.development` (template) → built-in defaults. Root `.env` is **not loaded**.
- `.env.development` template (inspected): `NEO4J_URI=bolt://neo4j:7687`,
  `REDIS_URL=redis://redis:6379/0`, `QDRANT_URL=http://qdrant:6333`, CORS adds
  `http://localhost:5173`, `LLM_PROVIDER=nvidia`, `LLM_MODEL=nvidia/nemotron-3-super-120b-a12b`,
  `LLM_BASE_URL=https://integrate.api.nvidia.com/v1`, `LLM_TEMPERATURE=0.2`,
  `LLM_MAX_TOKENS=800`, `LLM_TIMEOUT_SECONDS=25`, `LLM_MAX_RETRIES=3`; comment confirms
  NVIDIA_* vs LLM_* precedence for API key/base URL.
- `docker-compose.yml`: six services — api, react, nginx, neo4j, qdrant, redis
  (exactly as doc 15.4). `monitoring/docker-compose.monitoring.yml`: prometheus, grafana,
  node-exporter, neo4j-exporter (matches doc 15.5).

### 1.11 Frontend reality (`ui/src/`) — VERIFIED (inventory)
- Router (`ui/src/App.tsx`): `/` Home, `/explain`, `/upload`, `/provenance`,
  `/provenance/:id`, `/settings`; single `QueryClient` (retry 1, no refetch-on-window-focus);
  dark-mode via settings hook. **No sidebar component** — the shell uses `Header` only.
- API layer (`ui/src/api/client.ts`): axios, timeout `120_000 ms`,
  `API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'`; functions
  `postQuery`, `postExplain`, `getProvenance`, `uploadDocument`.
- Types (`ui/src/types/index.ts`): `Evidence` (node_id, title, text, label, numbering,
  collection, language, level, per-signal scores, final_score, sources, path, snippet),
  `ReasoningStep`, `HierarchyPath`, `SourceCitation`, `CounterAuthority`, `Confidence`,
  `Validity`, `RetrievalSummary`, `ExplanationResponse` (+`QueryResponse`), mirroring
  `src/models/schemas.py`.

---

## 2. Claims corrected (docs are wrong; source wins)

### 2.1 Doc 04 — Frontend Architecture (`OUTDATED`/`NOT FOUND`)
| Doc claim | Truth in source |
|-----------|-----------------|
| §4.4 lists 14 components incl. `EvidenceCard`, `CitationList`, `ReasoningChain`, `AuditPanel`, `Sidebar` | These files **do not exist**. Actual 14: `AnswerCard`, `ConfidenceGauge`, `CounterAuthorityCard`, `EvidencePanel`, `Header`, `HierarchyTree`, `HighlightText`, `KnowledgeGraph`, `LoadingOverlay`, `ProvenancePanel`, `QueryInput`, `ResultView`, `ScoreBar`, `ValidityBadge` |
| §4.5 hooks named `useQuery`, `useSettings`, `useTheme` | Actual: `useDarkMode`, `useExplain`, `useLocalSettings`, `useProvenance`, `useQueryQuestion`, `useRecentQuestions` |
| §4.6 client exports `queryQuestion()`/`explain()`/… + health, baseURL from `settings.apiBaseUrl` | Actual: `postQuery`/`postExplain`/`getProvenance`/`uploadDocument`, no health export; baseURL = `VITE_API_BASE_URL ?? '/api/v1'` |
| §4.6 types `EvidenceItem`, `VerificationResult`, `ProvenanceRecord` | Not present; actual names `Evidence`, `Validity`, `Confidence`, `CounterAuthority`, … |
| §4.2 "header/nav/**sidebar**" shell | No sidebar; shell is Header + main |

### 2.2 Doc 08 — HHGR Algorithm (`OUTDATED`)
| § | Doc claim | Truth in source |
|---|-----------|-----------------|
| 8.3 $S_{text}$ | "combines dense cosine similarity and token-overlap", blending λ | `text_score` is **keyword/title coverage only**; no dense cosine, no λ parameter. Dense cosine is the separate embedding path |
| 8.3 $S_{citation}$ | graph-distance kernel over $E_{CITES}$ rewarding "cites or is cited by" | `citation_score` is **exact-numbering / word-boundary reference match** — no graph distance |
| 8.3 $S_{struct}$ | isDefinition/isPenalty lexical markers + degreeCentrality + isChapterHeader + intent modulation | `structural_importance` = degree + `0.1·subtree_size`, query-independent |
| Stage 4 seeds | "Dedup(S_dense ∪ S_lex)" lexical+dense union | `ranker.retrieve` thresholds candidate scores over graph nodes; `explain()` uses `VectorRetriever.hybrid_retrieve` |
| $H(v,q)$ | generic α/β/γ/δ | Real scorer `WEIGHTS` = text .40, hierarchy .25, citation .20, structural .15 |
| propagation decay | ρ ≈ 0.5 | `propagate_hierarchy` uses up-factor `0.6`, down-factor `0.4`, capped at 1.0 |
| τ/k | τ=0.45, k=5 | k=5 matches `experiment.json` top_k; τ=0.45 is the **confidence** gate, not a retrieval threshold (`ranker.retrieve(threshold=0.0)` default) |

**Correct on doc 08:** dense/graph/hierarchy fusion weights `0.40/0.35/0.25`
(src/embeddings/retriever.py and experiment.json) — though doc attributes them to
`experiment.json` only; they are also the code defaults.

### 2.3 Doc 09 — Explainability (`OUTDATED`/`NOT FOUND`)
| § | Doc claim | Truth in source |
|---|-----------|-----------------|
| 9.4.1 | five verdict badges: supported / insufficient_evidence / contradicted / no_evidence / no_answer | Verification status = **`supported` \| `insufficient` \| `conflicts`** (default `unknown`); `final_adjustment` ∈ {`no_evidence`, `no_answer`, `contradiction_cap`, `insufficient_cap`, `none`} |
| 9.4 stage 1 | "sufficiency measured with a bigram Dice overlap" | Sufficiency = **45% keyword coverage + 35% exact citation + 20% diversity**; the bigram-Dice term was **removed** (Issue #12). `_text_similarity` (Dice) survives only for dedup and relevance fallback |
| 9.6.1 | confidence factor weights | Actual: `0.35·entailment + 0.30·relevance + 0.20·sufficiency + 0.15·retrieval_base` |
| 9.6.2 | ECE/MCE at `explanation.py:1857–2017` | That range is `_score_confidence`. **ECE/MCE live in `src/evaluation/calibration.py`** (`_NUM_BINS=10`); `explanation.py` never computes them |
| 9.7 | counter-authority markers: overruled, superseded, repealed, void, struck down, held unconstitutional, not in force | `_COUNTER_MARKERS` = {overruled, superseded, repealed, overridden, **invalid** (void ab initio / declared void / not enforceable / invalid), inoperative, not_applicable}; strong set = {overruled, superseded, repealed, overridden} |
| 9.3 | nine-step reasoning chain (Parse … Answer) | Seven step kinds: `query_parse → query_expansion → dense → graph → hierarchy → fusion → verification` |
| §9.9 verdicts / endpoints | — | Consistent (VERIFIED): query/explain/provenance surfaces exist |

**Also verified (doc 09 adjacent):** `_definition_promotion` with `DEFINITION_BONUS = 0.12`;
`FRAGMENT_DEMOTION = 0.55`; `explain()` is a reuse of `retrieve()` (src.retrieval.ranker) +
`propagate_hierarchy` (src.retrieval.context) + `VectorRetriever.hybrid_retrieve`.

### 2.4 Doc 15 — Configuration (`OUTDATED`)
| § | Doc claim | Truth in source |
|---|-----------|-----------------|
| 15.2 API | `API_HOST` / `API_PORT` / `LOG_LEVEL` | Actual identifiers: `APP_HOST` / `APP_PORT` / `APP_LOG_LEVEL`; binding group is `APP_*` |
| 15.2 CORS | default `5173, 3000` | Code default origins = `localhost:3000` + `localhost:8000`; `5173` appears only in the `.env.development` template |
| 15.2 Neo4j | `NEO4J_DATABASE` | Field **does not exist** in `settings.py` |
| 15.2 Qdrant | `QDRANT_HOST`/`QDRANT_PORT` | Actual single var `QDRANT_URL` |
| 15.2 LLM | `LLM_PROVIDER` default `nvidia` | Code default is **`mock`**; `nvidia` only via the env template |
| 15.2 Retrieval | `RETRIEVAL_TOP_K`, "hybrid weights from experiment.json", "confidence threshold 0.45", "propagation decay ≈ 0.5" | Real name `QA_TOP_K` (5); hybrid weights are code defaults in `src/embeddings/retriever.py` (0.40/0.35/0.25) and mirrored by `experiment.json`; τ=0.45 is QA confidence gate; propagation decay is 0.6/0.4, not ≈0.5 |
| 15.2 Embeddings | `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL` names | Model selection is provider/model/allow-deterministic-fallback fields; treat table as indicative only |

**Correct on doc 15:** precedence order (§15.1), env-file table (§15.3), six-service Compose
stack, non-root multi-stage backend image, monitoring stack, ports reference, dependency
groups and unpinned `requirements.txt` + pinned `requirements-lock.txt`.

---

## 3. Metric provenance table (exact generating file)

| Metric | Generating file |
|--------|-----------------|
| Recall@K, Precision@K, Hit Rate@K, **MAP, NDCG@K**, MRR (benchmark artifacts) | `eval/metrics/retrieval.py` only (Module 10 pipeline) |
| Recall@5/10, Precision@5, MRR, Section/Hierarchy Accuracy (in-repo eval core) | `src/evaluation/metrics/retrieval.py` |
| **ECE / MCE** on verdict confidence | `src/evaluation/calibration.py` only |
| RAGAS-style Faithfulness / Answer Relevancy / Context Recall / Context Precision / Answer Correctness | `eval/metrics/ragas.py` (+ `eval/metrics/semantic.py` EmbeddingCache) |
| Overall 0.4/0.4/0.2 (retrieval/generation/performance) | `src/evaluation/metrics/aggregate.py` |
| Latency mean/p50/p95, RSS, budget flag | `src/evaluation/metrics/performance.py` |
| Published benchmark (Recall@K/MAP/NDCG/hit-rate rows; ablation; per-query explainability; RAGAS) | `evaluation/reports/benchmark.md` ← `eval/harness.py` + `eval/metrics/{retrieval,ragas,explainability}.py`, configured by `data/eval/config/experiment.json` |

Key, previously-conflicting fact: **MAP and NDCG exist only in the offline `eval/` module, not
in `src/evaluation/`**, and **ECE/MCE exist only in `src/evaluation/calibration.py`, not in
`src/llm/explanation.py`**. Any doc statement to the contrary is corrected by §2.3.

---

## 4. Endpoint → implementation map

| Endpoint | File |
|----------|------|
| `GET /` (`{service,version,docs}`) | `src/main.py` |
| `GET /health`, `/ready`, `/live` | `src/api/health.py` via `src/main.py` |
| `POST /api/v1/query` | `src/api/qa.py` |
| `POST /api/v1/explain` (no-LLM) | `src/api/qa.py` → `explain()` in `src/llm/explanation.py` |
| `GET /api/v1/provenance/{id}` | `src/api/qa.py` (read `data/provenance/*.json`) |
| `POST /api/v1/documents/upload` | `src/api/documents.py` → `src/ingestion/pipeline.py` |
| `GET /metrics` | `src/main.py` → `src/monitoring/metrics.py` |

## 5. Model / provider → instantiation map

| Model / provider | Instantiation |
|------------------|---------------|
| `BAAI/bge-m3` (default), +5 registry models | `src/embeddings/models.py` |
| `deterministic` (evaluate/fallback) | `src/embeddings/providers.py` (`DeterministicEmbeddingProvider`, dim 64, blake2b) |
| `qdrant` vector store (in-memory/server) | `src/embeddings/store.py` (`QdrantStore`) |
| `nvidia` / `gemini` / `mock` LLM providers | `src/llm/llm.py` (`MockLLMClient` default; `LLM*` env config in `src/config/settings.py`) |
| `grounding-guard` insufficiency model | `src/llm/service.py` |

## 6. Algorithm → implementation map

| Algorithm | Implementation |
|-----------|----------------|
| HHGR four-signal graph ranking | `src/retrieval/scorer.py` `WEIGHTS` (text/hierarchy/citation/structural) |
| Dense+graph+hierarchy hybrid retrieval | `src/retrieval/ranker.py` + `src/embeddings/retriever.py` (`DEFAULT_HYBRID_WEIGHTS`) |
| Evidence re-fusion + final scoring | `src/llm/explanation.py` (`RANKING_WEIGHTS` dense .35/graph .25/hierarchy .15/keyword .15/citation .30; `_Signal.final = dense+graph+hierarchy`) |
| Hierarchical evidence propagation | `src/retrieval/context.py` `propagate_hierarchy` (up 0.6 / down 0.4) |
| Confidence composition | `src/llm/explanation.py` (0.35·entailment + 0.30·relevance + 0.20·sufficiency + 0.15·retrieval_base; `final_adjustment` caps) |
| Verification status / counter-authority | `src/llm/explanation.py` (`supported|insufficient|conflicts`; `_COUNTER_MARKERS`) |
| Sufficiency | keyword 45% / citation 35% / diversity 20% (Dice term removed, Issue #12) |
| BK-tree-ish dedup | `_text_similarity` (Dice) in `src/llm/explanation.py` + retrieval metrics |
| Calibration (ECE/MCE, 10 bins) | `src/evaluation/calibration.py` |
| Nested-set construction | `src/hierarchy/tree_builder.py` (DFS left/right/depth) |
| Citation extraction | `src/knowledge_graph/citation_extractor.py` |
| Canonical-doc resolution | `src/knowledge_graph/canonical.py` |
| Query expansion (V2.4.1+) | `src/retrieval/query_expansion.py` |

---

## 7. Missing documentation

- **Task 24 — cross-document isolation:** a dedicated isolation path with foreign-act markers
  exists in code but is not documented anywhere in docs 01–20. Doc 07/08/09 all fail to
  mention it. (`NOT FOUND` as a documentation claim.)
- The **three distinct weighting schemes** (§6 rows 1–3) are not disentangled in the docs;
  docs 07/08 fold them into one "fusion".
- Calibration run output (`results/reliability_diagram.png`, `results/task22_verification_
  audit.json`, `results/task23_relevance_debug.json`) are not described by any doc.
- The `src/retrieval/metrics.py` offline-research metric surface
  (average_retrieval_latency_ms, average_ranking_latency_ms, duplicate_removal_rate,
  average_adaptive_top_k, average_candidate_count) is undocumented.
- Offline benchmark corpus (`data/eval/gold/*` for bns/bnss/bsa/sc_judgments) is only partly
  described by doc 11 (manifest/citation coverage not documented).

## 8. Dead code

- `api/client.ts` "health-check" doc claim aside, no dead exports found in `ui/src`; the
  **earlier-documented `useQuery`** hook name is dead (renamed `useQueryQuestion`).
- `eval/metrics/ragas.py` native-`ragas` branch is **latent/dormant** (exercised only when the
  optional package is installed); the offline surrogate is the live path.
- `demo_*.py` at repo root (`demo_ingest`, `demo_kg`, `demo_retrieval`, `demo_embeddings`,
  `demo_hierarchy`) are standalone, not imported by the runtime or eval suite.

## 9. Unused modules / experimental code

- `src/retrieval/metrics.py` — research instrumentation, consumed by no runtime path.
- `src/evaluation/*` (metrics, calibration, report, plots, analysis, pipeline/runner) — the
  offline verification harness; `src/evaluation` is *not* wired into `POST /api/v1/query`.
- `eval/metrics/explainability.py` — feeds `evaluation/reports/benchmark.md` (citation
  accuracy / hierarchy correctness / graph-path / provenance / counter-authority F1) but is
  not part of the served app.
- `deploy/config/loader.py`, `deploy/config/cli.py` — validation used at container startup
  only (dev runs bypass them).

## 10. Production code (hot path)

- `src/main.py`, `src/api/*`, `src/models/schemas.py`, `src/middleware/*`,
  `src/config/settings.py`, `src/llm/*`, `src/retrieval/*`, `src/embeddings/*`,
  `src/knowledge_graph/*`, `src/hierarchy/*`, `src/ingestion/pipeline.py`,
  `src/monitoring/*`, `ui/src/*` — this is the shipped application; the features described in
  docs 03/05/06/07/10/12 are implemented by exactly these files, with the doc-04 corrections
  of §2.1.

---

*Generated by direct source inspection. Line-accurate corrections supersede the corresponding
text in docs 01–20; doc 15's own caveat ("treat the table as indicative; consult the source")
is echoed here for §15.2 only.*