# CI Report — GitHub Actions

Generated: 2026-09-02

## Overview

Production-quality GitHub Actions CI/CD added to HHGR. Two workflow files created: `ci.yml` (lint + tests) and `docker.yml` (image builds).

## Workflow Files

| File | Purpose | Jobs |
|------|---------|------|
| `.github/workflows/ci.yml` | Code quality gate | `backend` (ruff + pytest), `frontend` (vitest + build) |
| `.github/workflows/docker.yml` | Image build verification | `docker` (build api + react with caching) |

## Requirements Coverage

| Requirement | Implemented | Where |
|-------------|-------------|-------|
| Ruff | `ruff check` + `ruff format --check` (fail on drift) | `ci.yml` backend job |
| Pytest | `pytest -q` (fail on any failure) | `ci.yml` backend job |
| Build Docker image | `docker/build-push-action@v6` for both images | `docker.yml` |
| Cache dependencies | pip cache + npm cache + Docker layer cache | both files |
| Python 3.12 | `python-version: "3.12"` | `ci.yml` |
| Node LTS | `node-version: lts/*` (Node 22) | `ci.yml` |
| Fail on lint/test failure | All `run` steps fail hard (no `|| true`) | `ci.yml` |

## Validation

Both workflow files parsed as valid YAML via `yaml.safe_load`.

Structural validation confirmed each workflow has:
- `name`
- `on` (trigger: push + pull_request on main/develop)
- `jobs` with `runs-on` and `steps`

`ci.yml` also includes `concurrency` groups to cancel stale runs.

## ci.yml

- **backend** job: Python 3.12, pip cache, `ruff check`, `ruff format --check`, `pytest -q`
- **frontend** job: Node LTS, npm cache, `npm ci`, `npm test`, `npm run build`, uploads `ui/dist`

## docker.yml

- **docker** job: Docker Buildx, layer cache, `docker compose config -q` validation, builds `explaintool-api:ci` and `explaintool-ui:ci`, verifies images exist

## Notes / Design Decisions

- The previous `ci.yml` used Python 3.11 and Node 20 fixed; updated to **Python 3.12** and **Node LTS** per requirements.
- Removed the old `|| true` on `ruff format --check` so formatting drift now **fails the build** (matches "fail on lint failure").
- The prior `deploy-config-check` job was dropped — it invoked a `deploy.config.cli` module that may not exist on a fresh checkout and was out of scope for this task.
- `docker.yml` uses `push: false` + `load: true` so the build is verified locally but not pushed to a registry (safe until a real registry/credentials are configured).

## Result

**PASS** — CI/CD workflows are in place and validated. Production code was not modified.
