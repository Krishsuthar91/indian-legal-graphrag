# Final Report — LLM Model Configuration Fix (NVIDIA Provider)

**Date:** 2026-09-23
**Scope:** LLM model/configuration loading only. No retrieval, ranking, verification, citation, or QA logic was modified.

## 1. Root Cause

`NvidiaClient.__init__` (`src/llm/llm.py`) resolved the model as:

```python
model = model or settings.LLM_MODEL or settings.NVIDIA_MODEL or None
```

The **generic** `LLM_MODEL` (set to `meta/llama-3.1-8b-instruct`) always shadowed the provider-specific `NVIDIA_MODEL`, so the NVIDIA endpoint received a **retired** model id and answered `HTTP 410 Gone`.

In addition, live API probes revealed the previously-targeted `meta/llama-3.3-70b-instruct` **itself reached end-of-life on 2026-08-26T09:00:00Z** and also returns 410 today. The provider replacement therefore had to be chosen from models the account can actually invoke (verified live).

## 2. Config Precedence (single source of truth)

Source order (later wins; pydantic-settings): **code defaults < `.env.development` < `.env.development.local` < OS environment**. The runtime `env_file` tuple only loads `.env.development` then `.env.development.local` (`.env.production` is NOT loaded in dev mode).

| Setting | Winner (post-fix) | Source |
|---|---|---|
| `LLM_PROVIDER` | `nvidia` | `.env.development` |
| `NVIDIA_MODEL` (**authoritative** for the model) | `nvidia/nemotron-3-super-120b-a12b` | `.env.development` (runtime); code default + `NvidiaClient.default_model` identical |
| `LLM_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | `.env.development` (kept; inert for the nvidia provider, applies to other providers) |
| API key | resolved `LLM_API_KEY or NVIDIA_API_KEY`; runtime value from **`.env.development.local`** (git-ignored) → `NVIDIA_API_KEY` | `.env.development.local` |
| Base URL | `LLM_BASE_URL or NVIDIA_BASE_URL or default` = `https://integrate.api.nvidia.com/v1` | `.env.development` |

**Client resolution (post-fix):**

```python
model    = model or settings.NVIDIA_MODEL or None            # NVIDIA_MODEL only
api_key  = api_key or settings.LLM_API_KEY or settings.NVIDIA_API_KEY
base_url = base_url or settings.LLM_BASE_URL or settings.NVIDIA_BASE_URL or None
```

## 3. Additional Fixes made during verification

- `.env.production` / `.env.docker` / `.env.development` had real `NVIDIA_API_KEY=nvapi-…` values in the working tree. These are **tracked templates** whose headers say “never commit it”. Restored to `NVIDIA_API_KEY=`; the real dev key lives only in the git-ignored `deploy/env/.env.development.local` (check-ignore confirms). Note: the key was printed in earlier session output — rotating it is advised.
- Model replaced with `nvidia/nemotron-3-super-120b-a12b` — verified **callable** with this account’s key (others such as `meta/llama-3.2-11b-vision-instruct`, `mistralai/mistral-nemotron`, `nemotron-3-nano-omni-30b-a3b-reasoning`, `nemotron-3-ultra-550b-a55b` also worked; `llama-3.3-*`, `llama-3.1-*`, `mistral-*`, `nemotron-4-*` etc. returned 404/410 for this key).

## 4. Files Changed

| File | Change |
|---|---|
| `src/llm/llm.py` | `NvidiaClient.__init__` model resolution → `settings.NVIDIA_MODEL` only; `default_model = "nvidia/nemotron-3-super-120b-a12b"`; docstrings updated (model vs key/URL precedence) |
| `src/config/settings.py` | `NVIDIA_MODEL` default → `nvidia/nemotron-3-super-120b-a12b`; doc comment update |
| `deploy/env/.env.development` | `LLM_MODEL`/`NVIDIA_MODEL` → new model; priority comment updated; empty key restored |
| `deploy/env/.env.docker` | `LLM_MODEL`/`NVIDIA_MODEL` → new model; priority comment updated; empty key restored |
| `deploy/env/.env.production` | `LLM_MODEL`/`NVIDIA_MODEL` → new model; empty key restored |
| `tests/test_llm_clients.py` | 2 tests renamed + asserts flipped (model comes from `NVIDIA_MODEL`, not generic); new regression test `test_startup_log_reports_nvidia_model_setting`; model strings updated |
| `docs/API.md` | example response `"model"` updated |
| `docs/Evaluation.md` | config snippet updated |
| `scripts/run_final_evaluation.py` | default fallback LLM string updated |

**Intentionally NOT changed** (historical / documented): `results/**` eval artifacts record runs that actually used `meta/llama-3.3-70b-instruct` (do not falsify); `src/llm/llm.py:543` `LlamaClient.default_model = "llama-3.1-8b-instruct"` (local llama.cpp default, documented example); `src/config/settings.py:67` comment lists example id formats; `logs/**` historical entries.

## 5. Before / After Evidence

BEFORE — startup config (from history, `logs/app.log`):
```
llm.client_configured  provider=nvidia model=meta/llama-3.1-8b-instruct has_api_key=True timestamp~2026-08-08T14:55:32Z
qa.answer_complete     query="What is Section 2 …?" model=meta/llama-3.1-8b-instruct (logs/api.log:2936)
```

AFTER — this run (`uvicorn_final.log`, 2026-09-23):
```
llm.client_configured  provider=nvidia model=nvidia/nemotron-3-super-120b-a12b has_api_key=True api_key_length=70
llm.request_start      model=nvidia/nemotron-3-super-120b-a12b
qa.answer_complete     model=nvidia/nemotron-3-super-120b-a12b confidence=0.78 duration_ms=12823.72
```
No `3.1-8b` / `3.3-70b` appears anywhere in the after run log.

## 6. Verification

- `pytest tests/test_llm_clients.py tests/test_deploy_config.py` → **68 passed**
- Full suite → **1047 passed** (baseline 1046 + 1 new regression test)
- Live `GET /api/v1/health` → **200** (`{"status":"ok","version":"1.0.0","environment":"development"}`)
- Live `POST /api/v1/query` “What is Section 2 of the Indian Contract Act?” → **HTTP 200**, real generated answer + citations + provenance, `model: nvidia/nemotron-3-super-120b-a12b` (previously `502`/`410`)
- `git diff` for `deploy/env/` shows only intended changes (comments + model strings); no secrets added to tracked templates

## 7. Outstanding

- Commit/push NOT performed (per constraints).
- Consider rotating `NVIDIA_API_KEY` since it appeared in earlier working-tree diffs/output.