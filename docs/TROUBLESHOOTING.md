# Troubleshooting Guide

Common issues when building, deploying, and operating the Explaintool stack.

## Container / Docker

### `docker compose up` fails: "docker is not recognized"

Docker is not installed (or not on PATH). Install Docker Desktop / Docker
Engine and start the daemon, then re-run. Until then, CI runs the compose
YAML validation and image builds instead of local container runs.

### Service exits immediately / `Restarting (1) ...`

Check the failing container's logs:

```bash
docker compose logs api        # or react / nginx / neo4j ...
docker compose ps
```

Common causes:

- Missing secrets → run `python -m deploy.config.cli validate --env production`.
- `neo4j` still starting when `api` probes it (healthchecks + `depends_on`
  with `condition: service_healthy` handle this; increase `start_period`).
- Port 80 already in use on the host → change the `nginx` port mapping.

### `Error response from daemon: ... permission denied` (Linux)

Run with a user in the `docker` group or use `sudo`.

## Configuration & secrets

### `python -m deploy.config.cli validate --env production` exits 1

Set the missing variables in `deploy/env/.env.production`:

- `LLM_API_KEY` when `LLM_PROVIDER` is not `mock`
- `API_KEY` when `API_KEY_AUTH_ENABLED=true`
- `APP_DEBUG=false` for production

### CORS errors in the browser

`CORS_ORIGINS` must include the exact origin serving the page (scheme +
host + port). Example: `CORS_ORIGINS=["https://legal.example.com"]`.
Localhost dev uses `http://localhost:5173`.

## Backend

### `curl http://localhost/healthz` hangs

nginx → api chain issue:

```bash
docker compose ps                 # is nginx healthy? is api healthy?
docker compose logs nginx
docker compose logs api
```

If the API container is healthy but nginx isn't routing, confirm
`deploy/nginx/nginx.conf` is mounted read-only and was not modified.

### `/api/v1/check/database` returns `ok: false`

Neo4j is unreachable from the `api` container. Confirm:

- Neo4j container is `healthy`
- `NEO4J_URI` in the api env is `bolt://neo4j:7687` (Compose DNS name, not
  `localhost`)

### `/api/v1/check/vector` returns `ok: false`

Same check for Qdrant: `QDRANT_URL=http://qdrant:6333`, container healthy.

### `/api/v1/check/llm` returns `ok: false`

- Provider misconfigured: `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`.
- For local models (vLLM/Ollama) confirm the endpoint serves
  `/v1/chat/completions` and is reachable from inside the container.

### 401 on API calls

`API_KEY_AUTH_ENABLED=true` requires an `X-API-Key` header on all routes
except `/health`, `/ready`, `/live`, and `/check/*`. Add the header or
disable auth (not recommended in production).

### 429 "Rate limit exceeded"

`RATE_LIMIT_ENABLED=true` and the client exceeded `RATE_LIMIT_PER_MINUTE`
requests. Either increase the limit, or ensure the edge nginx forwards
`X-Forwarded-For` so per-client (not per-nginx) limits apply.

## Frontend

### `npm install` / `npm ci` fails

Delete `ui/node_modules` and `ui/package-lock.json`, then reinstall.
Confirm Node 20+.

### Blank page after deploying react container

The bundle expects `/api` to be reachable at the same host. With the full
Compose stack, nginx serves both the SPA and `/api`, so use the nginx port
(`http://localhost/`) rather than a bare static server.

## Monitoring

### Grafana shows "No data" for a panel

- Confirm Prometheus is scraping: **Status → Targets** in Prometheus UI.
- Confirm the overlay stack was started (monitoring compose file).
- Give it a minute — first scrape interval is 15s.

### Prometheus can't reach `api:8000`

All services must share the default Compose network. The monitoring overlay
uses `-f docker-compose.yml -f monitoring/docker-compose.monitoring.yml` so
prometheus joins the same network.

## Logs & rotation

### `logs/*.log` files not rotating

`LOG_ROTATION_ENABLED` must be `true` (set in the env profile used by the
api service). Rotation rolls at midnight keeping `LOG_BACKUP_COUNT` files.
