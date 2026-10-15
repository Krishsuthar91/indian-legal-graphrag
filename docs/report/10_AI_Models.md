# 10 — AI Models

This document inventories every model used by the system: where it is configured, what it
does, its inputs/outputs, and its role in the pipeline. Models for which no implementation
exists in the repository are explicitly marked **Not found in repository.**

Primary sources: `src/llm/llm.py`, `src/embeddings/models.py`, `src/embeddings/providers.py`,
`src/ingestion/ocr/engine.py`, `src/ingestion/detection/language_detector.py`,
`src/config/settings.py`.

---

## 10.1 Model inventory

| Category | Model / engine | Role | Location |
|----------|----------------|------|----------|
| Generation (LLM) | `nvidia/nemotron-3-super-120b-a12b` (NVIDIA NIM, OpenAI-compatible) | Answer generation | `src/llm/llm.py:563-616` |
| Generation (alt) | Gemini (Google) | Alt provider | `src/llm/llm.py` |
| Generation (dev) | Mock LLM | deterministic dev/testing | `src/llm/llm.py` |
| Relevance judge | LLM-based judge + deterministic fallback | Evidence relevance scoring | `src/llm/explanation.py`, `src/llm/service.py` |
| Embeddings (default) | `BAAI/bge-m3` (1024-d) | Multilingual dense retrieval | `src/embeddings/models.py:37-84` |
| Embeddings | `BAAI/bge-large-en-v1.5` (1024-d) | English retrieval | `src/embeddings/models.py` |
| Embeddings | `intfloat/e5-large-v2` (1024-d) | English retrieval | `src/embeddings/models.py` |
| Embeddings | `sentence-transformers/LaBSE` (768-d) | Multilingual retrieval | `src/embeddings/models.py:37-84` |
| Embeddings | `google/muril-base-cased` (768-d) | Indic retrieval | `src/embeddings/models.py` |
| Embeddings | `ai4bharat/indic-bert` (768-d) | Indic retrieval | `src/embeddings/models.py` |
| Embeddings (test) | deterministic hash embedding (384-d) | reproducible offline runs | `src/embeddings/models.py` |
| OCR (primary) | PaddleOCR | Scanned text extraction | `src/ingestion/ocr/engine.py` |
| OCR (fallback) | Tesseract (via `pytesseract`) | Scanned text extraction | `src/ingestion/ocr/engine.py` |
| Language ID | `langdetect` + Unicode script analysis | Language/script detection | `src/ingestion/detection/language_detector.py:12-33` |
| NER | **Not found in repository** | — | — |
| Dedicated reranker (cross-encoder) | **Not found in repository** | — | — |

---

## 10.2 Generation model (LLM)

### 10.2.1 NVIDIA NIM / Nemotron
- **Provider:** NVIDIA NIM (OpenAI-compatible HTTP API).
- **Model:** `nvidia/nemotron-3-super-120b-a12b`.
- **Configuration:** `src/config/settings.py` (key `NVIDIA_API_KEY`, base URL, model id,
  timeout, retries); usage in `src/llm/llm.py:563-616` (`NvidiaClient`).
- **Design note:** the model id has a **single source of truth** in settings and is propagated
  to the client, so switching models is a one-place change (see
  `final_report_llm_model_config.md`).
- **Call shape:** chat completion with a legal system prompt (`src/llm/prompts.py`), retrieved
  evidence delimited, low temperature for determinism, and a token budget.

### 10.2.2 Gemini (alternative provider)
- Selected by the LLM provider setting; same client interface as NVIDIA NIM. Present in
  `src/llm/llm.py` as an alternative generation backend.

### 10.2.3 Mock LLM
- Deterministic canned generation for tests, offline evaluation, and environments without an
  API key. It echoes/structures evidence so explainability and verification can be exercised
  without network access.

### 10.2.4 LLM-adjacent model use
- **Relevance judge:** the LLM (or a deterministic heuristic fallback) judges whether each
  retrieved evidence unit is relevant; used inside verification (`docs/Task23_Relevance_Judge_Investigation.md`).
- **Entailment check:** claims are checked against cited evidence; where a model is used it is
  the same configured LLM, otherwise a lexical/n-gram entailment surrogate applies.

---

## 10.3 Embedding models

Embedding selection is centralised in `src/embeddings/models.py:37-84` with a registry of
providers and dimensions; `src/embeddings/providers.py` loads them.

| Model | Dim | Languages | Notes |
|-------|-----|-----------|-------|
| `BAAI/bge-m3` | 1024 | 100+ | **default**; best multilingual quality |
| `BAAI/bge-large-en-v1.5` | 1024 | en | strong English baseline |
| `intfloat/e5-large-v2` | 1024 | en | strong English baseline |
| `sentence-transformers/LaBSE` | 768 | 100+ | multilingual, widely used |
| `google/muril-base-cased` | 768 | Indic | Hindi/Bengali/Tamil/etc. |
| `ai4bharat/indic-bert` | 768 | Indic | Indic-centric |
| `deterministic` | 384 | n/a | hash embedding; **off by default** |

- **Runtime:** `sentence-transformers` / `transformers` / `torch` with optional GPU.
- **Deterministic fallback:** disabled unless `EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK` (or the
  evaluation config `force_deterministic`) is enabled, preventing silent quality loss in
  production.
- **Changing provider requires re-indexing** because vector dimensions differ
  (`src/embeddings/indexer.py`, `src/embeddings/benchmark.py`).
- **Comparison harness:** `scripts/benchmark_semantic_dense.py` and
  `evaluation/embed_retrieval_comparison_v243*.json` record provider comparisons.

---

## 10.4 OCR engines

`src/ingestion/ocr/engine.py`:

1. **PaddleOCR** — primary engine; higher accuracy on legal scans.
2. **Tesseract** — fallback via `pytesseract` when PaddleOCR is unavailable.

OCR returns text plus per-page confidence; low-confidence pages are flagged in document
metadata (see `06_Document_Ingestion.md §6.5`).

---

## 10.5 Language identification

`src/ingestion/detection/language_detector.py:12-33` combines:

- **Unicode script range analysis** for Devanagari, Bengali, Tamil, Telugu, etc.
- **`langdetect`** for statistical language classification.

Output drives multilingual tokenization and expansion (`src/retrieval/query.py:155-172`).

---

## 10.6 Models that are *not* present

The following were checked for and are **not implemented** in this repository:

- **Named-entity recognition (NER) model.** Legal entity/reference extraction is done with
  pattern/regex rules (`src/knowledge_graph/citation_extractor.py`), not an ML NER model.
  → **Not found in repository.**
- **A dedicated cross-encoder / learning-to-rank reranker.** Re-ranking is performed by the
  weighted multi-signal fusion (`src/retrieval/ranker.py`, `src/llm/explanation.py`), not a
  trained reranker model. → **Not found in repository.**
- **Fine-tuned legal classifier for intent.** Intent classification is rule/heuristic-based
  (`src/retrieval/intent.py`). → **Not found in repository.**

---

## 10.7 Model lifecycle and configuration

| Setting | Controls | Default |
|---------|----------|---------|
| `LLM_PROVIDER` | generation backend (nvidia/gemini/mock) | nvidia (prod) / mock (test) |
| `NVIDIA_API_KEY` | NVIDIA NIM credential | required for NVIDIA |
| `NVIDIA_MODEL` | model id single source of truth | `nvidia/nemotron-3-super-120b-a12b` |
| embedding provider/model | dense model | `BAAI/bge-m3` |
| `EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK` | permit hash fallback | false |
| OCR engine preference | PaddleOCR → Tesseract | PaddleOCR first |

Details and full env table in `15_Configuration.md`.

---

## 10.8 Reproducibility notes

- Evaluation config `data/eval/config/experiment.json` pins
  `embedding.provider = "deterministic"`, `force_deterministic = true`, `seed = 42`, `runs = 3`,
  so offline benchmarks are deterministic and offline (no model downloads).
- Production uses real embeddings + NVIDIA NIM, so production results differ from the offline
  harness by design; the harness isolates algorithmic quality from model quality.
