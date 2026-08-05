# Deployment Guide

This document describes how to build and deploy the Explaintool stack for
production and development environments.

## Architecture

```
                ┌─────────────────────────────┐
   :80/:443     │  nginx (edge reverse proxy) │
   ───────────▶ │  TLS · gzip · security hdrs │
                └──────────┬──────────────────┘
                ┌──────────┴────────────┐
                ▼                       ▼
        ┌─────────────┐         ┌─────────────┐
        │   react     │         │    api      │
        │ (static SPA)│         │  (FastAPI)  │
        │  :80        │         │   :8000     │
        └─────────────┘         └──────┬──────┘
                 ┌─────────┬──────────┼──────────┐
                 ▼         ▼          ▼          ▼
             neo4j      qdrant      redis      prometheus
                 │                                    │
                 └────────────────────────────────────┘
                                   └── grafana (dashboards)
```

- `nginx` is the only publicly exposed container (ports `80`/`443`).
- `react` serves the static UI bundle on the internal network.
- `api` runs the FastAPI backend (uvicorn, 2 workers).
- Neo4j, Qdrant, and Redis are internal datastores (no public ports).
- Prometheus + Grafana are an optional overlay stack (see Monitoring).

## Prerequisites

- Docker Engine 24+ with Docker Compose v2 (`docker compose`).
- Ports `80` (and optionally `443`) free on the host.
- For real LLM inference: an API key (OpenAI / Mistral) or a local
  OpenAI-compatible endpoint (vLLM / Ollama).

## Quick start (production)

```bash
# 1. Prepare production secrets
cp deploy/env/.env.production deploy/env/.env.production
#    edit: NEO4J_PASSWORD, LLM_API_KEY, API_KEY, CORS_ORIGINS

# 2. Validate configuration (fails fast if secrets are missing)
python -m deploy.config.cli validate --env production

# 3. Build and start the six services
docker compose up --build -d

# 4. Verify
docker compose ps
curl http://localhost/healthz            # -> {"status":"ok", ...}
curl http://localhost/api/v1/health
curl http://localhost/docs
```

## Building images

```bash
# Backend image
docker build -f deploy/backend/Dockerfile -t explaintool-api:latest .

# Frontend image
docker build -f deploy/frontend/Dockerfile -t explaintool-ui:latest .
```

Both Dockerfiles are multi-stage:

- `deploy/backend/Dockerfile` — Python 3.11-slim, installs wheels in a
  cached dependency layer, copies only `src/`, runs as an unprivileged
  `app` user, includes a container `HEALTHCHECK` hitting `/api/v1/health`.
- `deploy/frontend/Dockerfile` — Node 20 builder runs `npm ci` +
  `npm run build`, then a `nginx:alpine` runtime serves `dist/` using
  `deploy/nginx/nginx-frontend.conf`.

## Environment profiles

| Profile      | File                          | Use                                          |
|--------------|-------------------------------|----------------------------------------------|
| production   | `deploy/env/.env.production`  | Real deployment secrets (never commit)       |
| development  | `deploy/env/.env.development` | Local dev (mock LLM, relaxed security)       |
| docker       | `deploy/env/.env.docker`      | Compose runtime defaults (service hostnames) |

Production validation (`deploy/config/loader.py`) fails fast when:

- `LLM_API_KEY` is empty while `LLM_PROVIDER` is a real provider
  (`openai` / `llama` / `mistral` / `qwen`).
- `API_KEY_AUTH_ENABLED=true` but `API_KEY` is empty.
- `APP_DEBUG=true` while `APP_ENV=production`.

## Reverse proxy (nginx)

`deploy/nginx/nginx.conf` is the edge config and is mounted read-only into
the `nginx` service. Highlights:

- `/api/*`, `/docs`, `/redoc`, `/openapi.json`, `/healthz` → `api:8000`
- everything else → `react:80` (SPA)
- gzip, `client_max_body_size`, security headers (CSP, X-Frame-Options, …)
- WebSocket upgrade support
- commented TLS server block — uncomment and mount certificates to enable
  HTTPS (see `docs/PRODUCTION.md`).

`deploy/nginx/nginx-frontend.conf` serves the static bundle inside the
`react` container (immutable caching for `/assets/`, SPA fallback to
`index.html`).

## Health checks

| Endpoint                  | Purpose                                      |
|---------------------------|----------------------------------------------|
| `/api/v1/health`          | Process is alive                             |
| `/api/v1/ready`           | Readiness for orchestrators                  |
| `/api/v1/live`            | Kubernetes-style liveness probe              |
| `/api/v1/check/database`  | Neo4j connectivity (short timeout)           |
| `/api/v1/check/vector`    | Qdrant connectivity                          |
| `/api/v1/check/llm`       | LLM provider reachability                    |

All dependency checks return `200` with a `ServiceHealth` body
(`status`, `ok`, `detail`, `latency_ms`) even on failure, so orchestrators
can distinguish dependency degradation from process death.

## Development workflow

```bash
# Same Compose file but with a dev override
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build

# or run the backend directly (hot reload) + infra only
docker compose -f docker-compose.override.yml up neo4j qdrant redis
uvicorn src.main:app --reload          # http://localhost:8000

cd ui
npm install
npm run dev                             # http://localhost:5173
```

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for common issues (containers not starting,
secrets validation, CORS, datastore connectivity).

## Deploying on a VM / bare metal

1. Build images and export, or run `docker compose up -d` on the host.
2. Put a reverse proxy (nginx, Traefik, or a load balancer) in front of
   port `80`/`443` with TLS.
3. Point `CORS_ORIGINS` at the real origin and set `API_KEY_AUTH_ENABLED=true`.
4. Back up the named volumes:
   `docker run --rm -v explaintool_neo4j_data:/data -v $PWD:/backup alpine tar czf /backup/neo4j.tgz -C /data .`
