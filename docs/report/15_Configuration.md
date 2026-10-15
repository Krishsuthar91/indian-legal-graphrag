# 15 — Configuration and Environment

This document covers how the system is configured: environment files, settings, Docker
services, dependencies, and the ports/volumes wiring. It also flags an important gotcha about
which env files the application actually loads.

Primary sources: `src/config/settings.py`, `.env` (root), `deploy/env/*`,
`deploy/config/loader.py`, `docker-compose.yml`, `docker-compose.override.yml`,
`requirements.txt`, `requirements-lock.txt`, `ui/package.json`, `monitoring/`.

---

## 15.1 Configuration sources and precedence

`src/config/settings.py` defines a single pydantic-settings `Settings` object. Values are read
in this precedence order (highest first):

1. **Process environment** variables.
2. **`.env.development.local`** — developer secrets (git-ignored).
3. **`.env.development`** — tracked template.
4. **Built-in defaults** in `Settings`.

> **Important:** the **root `.env` file is present but not loaded** by the application. The app
> reads the `deploy/env/`-style `.env.development[.local]` pair (and process env). Always
> configure via the environment or the `deploy/env` profiles — see `docs/Configuration.md`.

At the container level, `deploy/env/.env.docker` is used by Compose, and
`deploy/config/loader.py` (+ `deploy/config/cli.py`) loads and **validates** production config
before startup.

---

## 15.2 Settings groups

`Settings` is organised into groups (names shown are representative; the authoritative list is
`src/config/settings.py`):

### Application
| Variable | Default | Meaning |
|----------|---------|---------|
| `APP_NAME` | `explaintool` | Service name |
| `APP_VERSION` | `1.0.0` | Version string |
| `APP_ENV` | `development` | Environment profile |
| `LOG_LEVEL` | `INFO` | Log verbosity |

### API / server
| Variable | Default | Meaning |
|----------|---------|---------|
| `API_HOST` | `0.0.0.0` | Bind host |
| `API_PORT` | `8000` | Bind port |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed origins |

### Knowledge graph (Neo4j)
| Variable | Default | Meaning |
|----------|---------|---------|
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt endpoint |
| `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j` / — | Credentials |
| `NEO4J_DATABASE` | `neo4j` | Database name |

### Vector store (Qdrant)
| Variable | Default | Meaning |
|----------|---------|---------|
| `QDRANT_HOST` | `localhost` | Host |
| `QDRANT_PORT` | `6333` | REST port |
| collections | `documents,chapters,sections,clauses` | Collection names |

### Embeddings
| Variable | Default | Meaning |
|----------|---------|---------|
| `EMBEDDING_PROVIDER` | `bge-m3` | Active provider |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Model id |
| `EMBEDDING_ALLOW_DETERMINISTIC_FALLBACK` | `false` | Permit hash fallback |

### LLM
| Variable | Default | Meaning |
|----------|---------|---------|
| `LLM_PROVIDER` | `nvidia` | nvidia / gemini / mock |
| `NVIDIA_API_KEY` | — | NIM credential |
| `NVIDIA_BASE_URL` | NIM endpoint | API base |
| `NVIDIA_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | Model id (single source of truth) |
| `GEMINI_API_KEY` | — | Alt provider key |
| timeout / retries | sensible defaults | HTTP resilience |

### Retrieval
| Variable | Default | Meaning |
|----------|---------|---------|
| hybrid weights | see `experiment.json` | dense/graph/hierarchy balance |
| `RETRIEVAL_TOP_K` | `5` | Default k |
| confidence threshold | `0.45` | Sufficiency gate |
| propagation decay | ≈ `0.5` | Hierarchy decay |

### Storage / provenance
| Variable | Default | Meaning |
|----------|---------|---------|
| data paths | `data/{uploads,processed,hierarchy,provenance,embeddings}` | Blob locations |
| `PROVENANCE_RETENTION` | — | Retention policy |

> If a specific variable name above does not appear verbatim in `src/config/settings.py`, treat
> the group/default as indicative and consult the source for the exact identifier.

---

## 15.3 Environment files

| File | Tracked | Loaded by | Purpose |
|------|---------|-----------|---------|
| `.env` (root) | yes | **nothing** | Legacy; not read by the app |
| `deploy/env/.env.development` | yes | app (dev) | Development template |
| `deploy/env/.env.development.local` | **no** | app (dev) | Local secrets (NVIDIA key) |
| `deploy/env/.env.docker` | yes | Compose | Docker profile |
| `deploy/env/.env.production` | yes | app (prod) | Production template |

**Security note:** `deploy/env/.env.development.local` is git-ignored but has been observed to
contain a live NVIDIA API key during development. It must never be committed; rotate any key
that was ever committed. See `19_Limitations.md`.

---

## 15.4 Docker Compose stack

`docker-compose.yml` defines six services:

| Service | Image / build | Ports | Role |
|---------|---------------|-------|------|
| `api` | `deploy/backend/Dockerfile` (`explaintool-api`) | 8000 | FastAPI backend |
| `react` | `deploy/frontend/Dockerfile` (`explaintool-ui`) | 3000 | SPA (node/nginx) |
| `nginx` | `nginx` | 80 / 443 | Edge reverse proxy |
| `neo4j` | `neo4j:5-community` | 7474 / 7687 | Knowledge graph |
| `qdrant` | `qdrant/qdrant` | 6333 / 6334 | Vector store |
| `redis` | `redis:6` | 6379 | Cache/queue (optional) |

- All services `restart: unless-stopped` and define healthchecks.
- Named volumes persist Neo4j, Qdrant, Redis, and app data.
- `docker-compose.override.yml` provides development overrides (e.g. source mounts).
- Backend image is multi-stage (dependency wheel build → slim runtime) and runs as a
  **non-root** user.

### Backend Dockerfile (`deploy/backend/Dockerfile`)
- Stage 1 installs build deps and builds wheels.
- Stage 2 copies wheels, installs, copies `src/`, sets a non-root user, and uses
  `deploy/scripts/entrypoint.sh`.

### Frontend Dockerfile (`deploy/frontend/Dockerfile`)
- Stage 1 (`node`) builds the Vite app to `dist/`.
- Stage 2 (`nginx`) serves `dist/` with `deploy/nginx/nginx-frontend.conf`.

### Edge nginx (`deploy/nginx/nginx.conf`)
- Routes `/api/*` and `/docs` to the API, everything else to the SPA.
- TLS termination on 443.

---

## 15.5 Monitoring stack

`monitoring/docker-compose.monitoring.yml` runs Prometheus, Grafana, node-exporter, and a
Neo4j exporter. `monitoring/prometheus/prometheus.yml` defines **4 scrape targets** including
the backend `/metrics`. Grafana provisions the `explaintool_overview.json` dashboard.

---

## 15.6 Python dependencies

`requirements.txt` (unpinned, ranges) and `requirements-lock.txt` (fully pinned) include:

| Group | Packages |
|-------|----------|
| Web | fastapi, uvicorn[standard], python-multipart |
| Validation/config | pydantic, pydantic-settings, python-dotenv |
| Logging | structlog, python-json-logger |
| HTTP | httpx |
| Documents/OCR | pdfplumber, python-docx, pymupdf, Pillow, pytesseract |
| Language | langdetect |
| Graph | neo4j |
| Vectors/ML | qdrant-client, sentence-transformers, torch, transformers |
| Reporting | reportlab |
| Quality | pytest, pytest-asyncio, ruff, mypy |

Python **≥ 3.11** (`pyproject.toml`). Tool config: `ruff` line length 100 / py311;
`mypy` strict-ish with targeted overrides; `pytest` `asyncio_mode = "auto"`,
`testpaths = ["tests"]`.

---

## 15.7 Frontend dependencies

`ui/package.json` (scripts: `dev`, `build`, `preview`, `lint`, `test`):

| Group | Packages |
|-------|----------|
| Core | react 18, react-dom |
| Language/build | typescript ~5.6.3, vite 5, @vitejs/plugin-react |
| Styling | tailwindcss 3, postcss, autoprefixer |
| Data/routing | @tanstack/react-query 5, axios, react-router-dom 6 |
| Visualisation | cytoscape, @xyflow/react, recharts |
| Motion | framer-motion |
| Test | vitest, jsdom |

---

## 15.8 Ports reference

| Port | Service |
|------|---------|
| 8000 | FastAPI backend |
| 5173 | Vite dev server |
| 3000 | React container (SPA served) |
| 80 / 443 | nginx edge |
| 7474 / 7687 | Neo4j HTTP / Bolt |
| 6333 / 6334 | Qdrant REST / gRPC |
| 6379 | Redis |
| 9090 | Prometheus |
| 3001 | Grafana (mapped) |

---

## 15.9 CI/CD

`.github/workflows/ci.yml` runs backend lint (ruff), type-check (mypy), and pytest, plus
frontend lint/test. `.github/workflows/docker.yml` builds the images. See
`docs/GitHubActions.md`.

---

## 15.10 Common configuration tasks

| Goal | Action |
|------|--------|
| Point at another Act | set `document_id` / canonical mapping |
| Switch embedding model | set `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL` then re-index |
| Reproduce offline benchmark | use `data/eval/config/experiment.json` (deterministic) |
| Enable real generation | set `LLM_PROVIDER=nvidia` + `NVIDIA_API_KEY` |
| Run without external services | `InMemoryGraph` + deterministic embeddings |
| Serve publicly | `docker compose up` behind nginx + TLS |
