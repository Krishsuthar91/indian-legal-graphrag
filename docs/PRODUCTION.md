# Production Runbook

Operational guide for running Explaintool in production. Follow these steps
in order when deploying or operating the stack.

## 1. Configuration & secrets

Start from the template and set every required secret:

```bash
cp deploy/env/.env.production deploy/env/.env.production
# edit in place, then:
python -m deploy.config.cli validate --env production   # must exit 0
```

Required in production:

| Variable            | Notes                                              |
|---------------------|----------------------------------------------------|
| `LLM_PROVIDER`      | `openai`, `llama`, `mistral`, or `qwen`            |
| `LLM_API_KEY`       | Required for all non-mock providers                |
| `LLM_BASE_URL`      | Provider endpoint (defaults to OpenAI)             |
| `NEO4J_PASSWORD`    | Change from the compose default                    |
| `API_KEY`           | Required when `API_KEY_AUTH_ENABLED=true`          |
| `CORS_ORIGINS`      | The real public origin(s)                          |
| `APP_DEBUG`         | Must be `false`                                    |

Never commit `deploy/env/.env.production` (git-ignored) and keep it out of
image build contexts (see `.dockerignore`).

## 2. TLS / HTTPS

`deploy/nginx/nginx.conf` includes a commented `443 ssl` server block:

1. Place certificates on the host, e.g. `./certs/fullchain.pem` and
   `./certs/privkey.pem`.
2. Mount them into the `nginx` service (add a volume in
   `docker-compose.yml` or use secrets).
3. Uncomment the `listen 443 ssl http2` block and the `ssl_certificate*`
   directives, and the HTTP→HTTPS redirect server.

For automatic certificates use certbot + a volume, or terminate TLS at a
managed load balancer and keep nginx on plain HTTP internally.

## 3. Startup sequence

`docker compose up -d --build` starts services in dependency order:

```
redis ──► neo4j ──► qdrant ──► api ──► react ──► nginx
```

Each datastore exposes a healthcheck; `api` waits for all three to be
healthy, `nginx` waits for `api` and `react`.

## 4. Verification

```bash
docker compose ps                    # all services should be "healthy"/"running"
curl -fsS http://localhost/healthz   # API health via nginx
curl -fsS http://localhost/api/v1/check/database
curl -fsS http://localhost/api/v1/check/vector
curl -fsS http://localhost/api/v1/check/llm
curl -fsS http://localhost/docs
```

Expect `{"status":"ok",...}` for liveness/readiness and
`{"ok":true,...}` for dependency checks.

## 5. Monitoring

Bring up the observability overlay:

```bash
docker compose -f docker-compose.yml \
               -f monitoring/docker-compose.monitoring.yml up -d

# Prometheus  http://localhost:9090
# Grafana     http://localhost:3000   (admin / grafana — change immediately)
```

The "Explaintool Overview" dashboard ships pre-provisioned
(`monitoring/grafana/dashboards/explaintool_overview.json`) and shows API
latency, request rate by status, process memory, and storage-engine activity.

### Alerts to configure

- API p95 latency rising / error rate (5xx) threshold
- `process_rss_bytes` sustained high
- Qdrant / Neo4j target down (`up == 0`)

## 6. Backups

Named volumes are created by Compose:

```
explaintool_neo4j_data
explaintool_neo4j_logs
explaintool_qdrant_data
explaintool_redis_data
explaintool_app_data
```

Back them up with the `docker run ... alpine tar` pattern (see
`docs/DEPLOYMENT.md`). Restore by stopping the service, copying the archive
into the volume, and starting the service again.

## 7. Logs

Per-channel logs are written to the mounted `./logs` directory on the host
when using Compose (api/llm/retrieval/error/audit + app.log). With rotation
enabled (`LOG_ROTATION_ENABLED=true`) files roll daily; keep a log shipper
(e.g. Filebeat, Fluentd) pointed at `./logs` for central aggregation.

## 8. Upgrades & rollback

- **Upgrade**: pull new images (`docker compose pull`), then
  `docker compose up -d`. Datastore images stay pinned by tag; check
  release notes before bumping Neo4j/Qdrant major versions.
- **Rollback**: re-tag the previous image (`explaintool-api:prev`) and
  `docker compose up -d`. Data volumes persist across rollbacks.

## 9. Security checklist

- [ ] `APP_DEBUG=false`, `APP_ENV=production`
- [ ] `API_KEY_AUTH_ENABLED=true` with a strong `API_KEY`
- [ ] Neo4j password rotated from the compose default
- [ ] TLS enabled at the edge (or a TLS-terminating LB)
- [ ] CORS restricted to the real origin
- [ ] Grafana admin password changed
- [ ] Logs shipped off-box; secrets never committed
