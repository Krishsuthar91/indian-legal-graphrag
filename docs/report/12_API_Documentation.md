# 12 — API Documentation

The backend exposes a REST API built with FastAPI. All application endpoints are versioned
under `/api/v1`; the root banner and the operational `/metrics` endpoint sit outside the
version prefix.

Primary sources: `src/api/router.py`, `src/api/qa.py`, `src/api/documents.py`,
`src/api/health.py`, `src/main.py`, `src/models/schemas.py`, `src/llm/schemas.py`.
Interactive docs: `GET /docs` (Swagger UI), `GET /redoc`, `GET /openapi.json`.

Base URL (local): `http://localhost:8000`

---

## 12.1 Endpoint summary

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/` | — | Service banner |
| GET | `/api/v1/health` | — | Aggregate health |
| GET | `/api/v1/ready` | — | Readiness probe |
| GET | `/api/v1/live` | — | Liveness probe |
| GET | `/api/v1/check/database` | — | Neo4j check |
| GET | `/api/v1/check/vector` | — | Qdrant check |
| GET | `/api/v1/check/llm` | — | LLM check |
| POST | `/api/v1/query` | — | Full QA (retrieve + verify + generate) |
| POST | `/api/v1/explain` | — | Explainability only (no LLM) |
| GET | `/api/v1/provenance/{provenance_id}` | — | Re-fetch provenance |
| POST | `/api/v1/documents/upload` | — | Upload + index a document |
| GET | `/metrics` | — | Prometheus metrics |

> Authentication is **not enabled** in the repository's default configuration. For internet
> exposure the deployment relies on the nginx edge and network policy; an API-key/jwt layer is
> **not found in repository** (see `19_Limitations.md`).

---

## 12.2 GET `/`

Returns a small banner with the service name, version, and links to docs/health.

**Response 200**
```json
{
  "name": "explaintool",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/api/v1/health"
}
```

---

## 12.3 Health endpoints

### GET `/api/v1/health` → `HealthResponse`
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "database": { "status": "up", "latency_ms": 4.2 },
    "vector":   { "status": "up", "latency_ms": 3.1 },
    "llm":      { "status": "up", "latency_ms": 12.7 }
  }
}
```

### GET `/api/v1/ready` / `/api/v1/live`
Kubernetes-style probes. `/live` returns immediately if the process is up; `/ready` returns
ready once required dependencies are reachable.
```json
{ "status": "ready" }
```

### GET `/api/v1/check/database` · `/check/vector` · `/check/llm` → `ServiceHealth`
Actively probe one dependency with a short timeout.
```json
{ "status": "up", "service": "vector", "latency_ms": 3.1, "detail": "qdrant reachable" }
```
On failure:
```json
{ "status": "down", "service": "llm", "detail": "provider unreachable" }
```

---

## 12.4 POST `/api/v1/query`

Full question-answering: retrieve → verify → generate → persist provenance.

**Request body — `QueryRequest`**
```json
{
  "question": "What is the punishment for theft under the Indian Penal Code?",
  "top_k": 5,
  "document_id": null,
  "include_provenance": true
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `question` | string | yes | Natural language; any supported language |
| `top_k` | integer | no | Overrides default k (5) |
| `document_id` | string \| null | no | Restrict retrieval to one document |
| `include_provenance` | boolean | no | Return the provenance id |

**Response 200 — `QueryResponse`** (abridged)
```json
{
  "answer": "Under Section 378 … theft is defined as …; Section 379 prescribes …",
  "confidence": 0.82,
  "verification": {
    "badge": "supported",
    "sufficiency": 0.78,
    "relevance": "pass",
    "entailment": { "supported": 3, "total": 3 }
  },
  "evidence": [
    {
      "node_id": 1234,
      "document_id": "cf20a14c52127fd5",
      "section_number": "378",
      "title": "Theft",
      "text": "Whoever, intending to take dishonestly …",
      "scores": { "dense": 0.71, "graph": 0.64, "hierarchy": 0.55,
                  "keyword": 0.48, "citation": 0.30, "fused": 0.66 }
    }
  ],
  "reasoning": [
    { "step": "parse",    "detail": "act=indian penal code; intent=definition" },
    { "step": "retrieve", "detail": "6 candidates" },
    { "step": "verify",   "detail": "sufficiency 0.78" }
  ],
  "citations": [ { "n": 1, "section_number": "378" } ],
  "counter_authority": [],
  "provenance_id": "9f2c1a7b4e0d"
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `answer` | string | Generated, cited answer |
| `confidence` | number [0,1] | Calibrated composite confidence |
| `verification.badge` | enum | `supported` / `insufficient_evidence` / `contradicted` / `no_evidence` / `no_answer` |
| `evidence[]` | array | Ranked evidence with per-signal scores |
| `reasoning[]` | array | Reasoning chain steps |
| `citations[]` | array | Numbered citations |
| `counter_authority[]` | array | Detected overruled/repealed markers |
| `provenance_id` | string | Use with the provenance endpoint |

**Error responses:** `422` invalid body; `200` with `verification.badge = "no_answer"` when the
system declines (never a 5xx for a valid question).

---

## 12.5 POST `/api/v1/explain`

Explainability **without** an LLM call — returns retrieval, reasoning, evidence, and
verification synchronously. Used by Settings/debug and by offline evaluation.

**Request body — `ExplainRequest`**
```json
{ "question": "What is a void agreement?", "top_k": 5, "document_id": null }
```

**Response 200 — `ExplanationResponse`** (abridged)
```json
{
  "question": "What is a void agreement?",
  "parsed_query": { "act": "indian contract act", "intent": "definition",
                    "references": ["2(g)"] },
  "evidence": [ { "node_id": 42, "section_number": "2(g)", "title": "Void agreement",
                  "scores": { "dense": 0.69, "graph": 0.72, "hierarchy": 0.6,
                              "keyword": 0.5, "citation": 0.2 } } ],
  "reasoning": [ { "step": "expand", "detail": "2(g) verified in corpus" } ],
  "verification": { "badge": "supported", "sufficiency": 0.81 }
}
```

---

## 12.6 GET `/api/v1/provenance/{provenance_id}`

Re-fetch a persisted provenance record (immutable).

**Path parameter:** `provenance_id` (string, e.g. `9f2c1a7b4e0d`).

**Response 200** — the full provenance record (query, retrieved nodes, signal scores,
hierarchy paths, citations, verification, confidence, model metadata).
**Response 404** — `{ "detail": "provenance not found" }`.

---

## 12.7 POST `/api/v1/documents/upload`

Upload and index a legal document.

**Request:** `multipart/form-data`

| Part | Type | Required | Notes |
|------|------|----------|-------|
| `file` | binary | yes | PDF / DOCX / TXT; size-capped |

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@indian_contract_act_1872.pdf"
```

**Response 200** (abridged)
```json
{
  "document_id": "0d1934142f67c5f5",
  "status": "indexed",
  "pages": 60,
  "ocr_applied": false,
  "language": "en",
  "nodes": { "chapters": 10, "sections": 238, "clauses": 512 },
  "indexed": { "documents": 1, "chapters": 10, "sections": 238, "clauses": 512 }
}
```

**Errors:** `400` unsupported type / oversize; `500` indexing failure with a safe message.

---

## 12.8 GET `/metrics`

Prometheus text exposition (scraped by `monitoring/prometheus/prometheus.yml`). Example
metrics: `http_requests_total`, `http_request_duration_seconds`, plus retrieval/LLM counters.
This endpoint is **outside** `/api/v1`.

---

## 12.9 Schemas overview

| Schema | Location | Used by |
|--------|----------|---------|
| `QueryRequest` / `QueryResponse` | `src/api/qa.py` | `POST /query` |
| `ExplainRequest` / `ExplanationResponse` | `src/api/qa.py` | `POST /explain` |
| `HealthResponse` / `ServiceHealth` | `src/api/health.py` | health/check endpoints |
| Upload summary | `src/api/documents.py` | `POST /documents/upload` |
| Explanation/verification models | `src/llm/schemas.py` | explanation payloads |
| Shared models | `src/models/schemas.py` | cross-cutting |

All bodies are validated with **Pydantic v2**; invalid requests return FastAPI's standard
`422` validation error shape.

---

## 12.10 Versioning and conventions

- API version is carried in the path (`/api/v1`), not a header.
- Content type is `application/json` except upload (`multipart/form-data`).
- Field naming is `snake_case`.
- Enum values are lowercase snake strings (badges, statuses).
- Timestamps are ISO-8601 UTC where present.
