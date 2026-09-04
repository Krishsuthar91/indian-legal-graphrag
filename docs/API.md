# API Reference

The HHGR backend exposes a REST API via FastAPI at `http://localhost:8000`. All business endpoints are prefixed with `/api/v1/`. Interactive docs are available at `/docs` (Swagger UI) and `/redoc`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Application root (service name, version, docs link) |
| GET | `/metrics` | Prometheus-compatible metrics (served by middleware) |
| POST | `/api/v1/query` | Generate an explainable answer with full verification and provenance |
| POST | `/api/v1/explain` | Run retrieval and explain the pipeline without calling the LLM |
| GET | `/api/v1/provenance/{provenance_id}` | Fetch a stored provenance record |
| POST | `/api/v1/documents/upload` | Upload a document for ingestion and indexing |
| GET | `/api/v1/health` | Application health check |
| GET | `/api/v1/ready` | Readiness probe |
| GET | `/api/v1/live` | Liveness probe |
| GET | `/api/v1/check/database` | Neo4j connectivity check |
| GET | `/api/v1/check/vector` | Qdrant connectivity check |
| GET | `/api/v1/check/llm` | LLM provider connectivity check |

### POST `/api/v1/query`

Generate an answer to a legal question with full verification and provenance.

**Request:**

```json
{
  "query": "What is the definition of a contract under the Indian Contract Act?",
  "language": "en",
  "top_k": 5,
  "temperature": 0.2,
  "max_tokens": 800
}
```

All fields except `query` are optional. Constraints:
- `query`: required, non-empty (whitespace-only is rejected with 422).
- `top_k`: integer 1–20.
- `temperature`: float 0.0–2.0.
- `max_tokens`: integer 1–4000.
- `language`: optional string language filter (e.g. `en`, `hi`).

**Response:** `QueryResponse` — extends `ExplanationResponse` with `provenance_id`, `answer`, `model`, `duration_ms`.

```json
{
  "query": "What is the definition of a contract under the Indian Contract Act?",
  "query_language": "en",
  "retrieval": {
    "keywords": ["contract", "definition"],
    "section_refs": ["2(h)"],
    "dense_hits": 8,
    "graph_hits": 5,
    "hierarchy_propagated": 2,
    "candidates": 20,
    "returned": 5,
    "intent": "definition",
    "adaptive_top_k": 5,
    "retrieval_strategy": "adaptive",
    "ranking_breakdown": {},
    "duplicates_removed": 0,
    "duplicate_details": []
  },
  "evidence": [
    {
      "node_id": "0d1934142f67c5f5__n_0001",
      "title": "Interpretation-clause",
      "text": "...",
      "label": "Section",
      "numbering": "2(h)",
      "collection": "sections",
      "language": "en",
      "level": 5,
      "dense_score": 0.92,
      "graph_score": 0.88,
      "hierarchy_score": 0.75,
      "final_score": 0.86,
      "sources": ["dense", "graph", "hierarchy"],
      "path": ["0d1934142f67c5f5", "n_0001"],
      "snippet": "an agreement enforceable by law is a contract"
    }
  ],
  "reasoning_chain": [
    {"step": 1, "kind": "parse", "description": "...", "node_ids": [], "detail": {}}
  ],
  "hierarchy_paths": [
    {"node_id": "n_0001", "entries": []}
  ],
  "citations": [
    {
      "index": 0,
      "node_id": "0d1934142f67c5f5__n_0001",
      "title": "Interpretation-clause",
      "label": "Section",
      "numbering": "2(h)",
      "score": 0.86,
      "citation_text": "[0]",
      "snippet": "an agreement enforceable by law is a contract"
    }
  ],
  "counter_authorities": [],
  "confidence": {
    "score": 0.72,
    "label": "high",
    "factors": {}
  },
  "validity": {
    "is_valid": true,
    "supported": true,
    "has_conflicts": false,
    "cites_counter_authority": false,
    "insufficient_evidence": false,
    "reasons": [],
    "status": "supported",
    "reason": "Evidence is sufficient and relevant",
    "support_score": 0.85,
    "relevance_score": 0.78,
    "sufficiency_score": 0.65,
    "contradiction_found": false
  },
  "retrieval_weights": {"dense": 0.4, "graph": 0.35, "hierarchy": 0.25},
  "verification_trace": {
    "verification_status": "supported",
    "verification_reason": "...",
    "confidence_score": 0.72,
    "confidence_label": "high",
    "evidence_relevance_score": 0.78,
    "evidence_relevance_label": "relevant",
    "evidence_sufficiency_score": 0.65,
    "citation_entailment_score": 0.9,
    "contradiction_found": false,
    "retrieval_base_score": 0.6,
    "final_adjustment": "entailment_boost",
    "decision_path": []
  },
  "provenance_id": "prov-abc123",
  "answer": "A contract is defined under Section 2(h) as an agreement enforceable by law.",
  "model": "meta/llama-3.1-8b-instruct",
  "duration_ms": 1850.0
}
```

Notes:
- `confidence` is an object `{score, label, factors}`, not a scalar.
- `citations` is an array of citation objects, not plain strings.
- Latency is reported as `duration_ms` (not `latency_ms`).

### POST `/api/v1/explain`

Run retrieval and return the explanation without invoking the LLM.

**Request:**

```json
{
  "query": "What are the remedies for breach of contract?",
  "top_k": 5,
  "language": "en"
}
```

`query` is required; `top_k` (1–20) and `language` are optional.

**Response:** `ExplanationResponse` — same shape as the `QueryResponse` above minus the LLM-specific fields (`answer`, `model`, `provenance_id`, `duration_ms`).

```json
{
  "query": "What are the remedies for breach of contract?",
  "query_language": "en",
  "retrieval": {"keywords": ["breach", "remedies", "contract"], "section_refs": [], "dense_hits": 8, "graph_hits": 3, "hierarchy_propagated": 2, "candidates": 20, "returned": 5, "intent": "", "adaptive_top_k": null, "retrieval_strategy": "fixed", "ranking_breakdown": {}, "duplicates_removed": 0, "duplicate_details": []},
  "evidence": [],
  "reasoning_chain": [],
  "hierarchy_paths": [],
  "citations": [],
  "counter_authorities": [],
  "confidence": {"score": 0.0, "label": "unknown", "factors": {}},
  "validity": {"is_valid": true, "supported": false, "has_conflicts": false, "cites_counter_authority": false, "insufficient_evidence": false, "reasons": [], "status": "unknown", "reason": "", "support_score": 0.0, "relevance_score": 0.0, "sufficiency_score": 0.0, "contradiction_found": false},
  "retrieval_weights": {"dense": 0.4, "graph": 0.35, "hierarchy": 0.25},
  "verification_trace": null
}
```

The retrieval summary is nested under `retrieval` (keywords live in `retrieval.keywords`); the fused weight constants are returned in `retrieval_weights`.

### GET `/api/v1/provenance/{provenance_id}`

Retrieve the full provenance record for a previous query. Returns the same `QueryResponse` shape as `/query`. Missing records return 404.

### POST `/api/v1/documents/upload`

Upload a document for ingestion and indexing. Accepts `multipart/form-data` with a single file field `file`. Supported extensions are PDF, DOCX, and TXT.

**Request:** `multipart/form-data`, field `file`.

**Response:** `DocumentUploadResponse` (HTTP 200 on success).

```json
{
  "document_id": "new-doc-id",
  "title": "2026-08-30 Contract Act Sample",
  "language": "en",
  "num_pages": 120,
  "file_name": "contract_act.pdf",
  "nodes_indexed": 222,
  "collections": {"sections": 192, "chapters": 5, "documents": 1, "subsections": 24},
  "message": "Indexed 222 nodes"
}
```

Unsupported extensions and missing files return 422.

### Health & Monitoring Endpoints

| Endpoint | Method | Response |
|----------|--------|----------|
| `/api/v1/health` | GET | `{"status", "version", "environment"}` |
| `/api/v1/ready` | GET | `{"ready": "ok"}` |
| `/api/v1/live` | GET | `{"status", "version", "environment"}` |
| `/api/v1/check/database` | GET | `ServiceHealth` (`status`, `service`, `ok`, `detail`, `latency_ms`) |
| `/api/v1/check/vector` | GET | `ServiceHealth` |
| `/api/v1/check/llm` | GET | `ServiceHealth` |
| `/metrics` | GET | Prometheus text format |
| `/` | GET | `{"service", "version", "docs"}` |

Probe-style health checks (`/check/*`) return HTTP 200 with `"ok": false` when a dependency is down so orchestrators can report details; they do not return 503.

## Error Responses

Application errors are returned as:

```json
{
  "detail": "Error message describing what went wrong",
  "code": "ERROR_CODE"
}
```

LLM provider quota/rate-limit errors return HTTP 429 with a provider-specific envelope:

```json
{
  "error": "Provider quota exceeded",
  "provider": "nvidia",
  "details": "HTTP 429: ...",
  "retry_after": 30.0
}
```

(`retry_after` is only present when the provider supplies it.)

Common HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 401 | Missing or invalid API key |
| 404 | Not found (provenance ID, route) |
| 413 | Request body too large |
| 422 | Validation error (Pydantic schema / invalid parameters) |
| 429 | Rate limit exceeded or LLM quota exceeded |
| 500 | Internal server error / request timeout |
| 502 | LLM provider connection or auth error |
| 504 | LLM provider response timeout |

## Rate Limiting

When enabled (`RATE_LIMIT_ENABLED=true`), a per-IP sliding window of `RATE_LIMIT_PER_MINUTE` (default **120** requests/minute) is enforced. Exceeding it returns HTTP 429:

```json
{
  "detail": "Rate limit exceeded. Please retry later.",
  "code": "rate_limited"
}
```

## Authentication

When enabled (`API_KEY_AUTH_ENABLED=true`), protected routes require the header `X-API-Key: <your-api-key>`. Health and probe paths (`/api/v1/health`, `/api/v1/ready`, `/api/v1/live`) remain public; `/api/v1/check/*` accepts an optional API key. Requests without a valid key return HTTP 401:

```json
{"detail": "Missing or invalid API key"}
```

Note: the QA, provenance, and documents endpoints require the API key when authentication is enabled.

## Configuration

Key environment variables for API behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | 8000 | Server port |
| `QA_TOP_K` | 5 | Default top-K for retrieval |
| `QA_CONFIDENCE_THRESHOLD` | 0.45 | Minimum confidence for "supported" badge |
| `QA_REQUEST_TIMEOUT_SECONDS` | 30 | Request timeout |
| `LLM_TEMPERATURE` | 0.2 | LLM temperature |
| `LLM_MAX_TOKENS` | 800 | Maximum tokens in response |
| `LLM_TIMEOUT_SECONDS` | 25 | LLM API timeout |
| `RATE_LIMIT_PER_MINUTE` | 120 | Requests-per-minute per IP |
| `REQUEST_MAX_BODY_BYTES` | 1048576 | Maximum request body size (1 MiB) |
