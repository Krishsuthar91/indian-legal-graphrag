# GitHub Actions CI/CD

This repository uses GitHub Actions for continuous integration and delivery. All workflows start only after secrets are configured (`NVIDIA_API_KEY` is never required for CI — tests run against the deterministic/mock providers).

## Workflows

| Workflow | File | Trigger | Jobs |
|----------|------|---------|------|
| **CI** | `.github/workflows/ci.yml` | push to `main`/`develop`, pull requests to `main`/`develop` | Backend (ruff lint, ruff format, pytest), Frontend (vitest, production build) |
| **Docker** | `.github/workflows/docker.yml` | push to `main`/`develop`, `v*` tags, pull requests | Builds `api` + `react` images and verifies they compile (no registry push) |

## What CI runs

### Backend job

```bash
pip install -r requirements.txt matplotlib
ruff check src tests
ruff format --check src tests
pytest -q
```

- `requirements.txt` pins `ruff` so the CI ruff version matches the local one.
- Lint rules live in `pyproject.toml`: `select = ["E","F","I","N","W","UP"]`, line length 100, target `py311`.
- `pytest` runs the full suite (1047 tests) with `asyncio_mode = "auto"`.
- Formatting and linting also run against non-`src` tooling as part of the repo standard (`scripts/`, `eval/`, `validation/`) — keep them `ruff check .` / `ruff format .` clean.

### Frontend job

```bash
cd ui
npm ci
npm test
npm run build
```

- Uses the repository's pinned npm `package-lock.json` (`npm ci`).
- 53 Vitest + Testing Library tests, then a production `tsc -b && vite build`.

## Local equivalence

Before opening a PR, run the same gates locally:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
cd ui && npm ci && npm test && npm run build
```

CI is deliberately **deterministic**: no live network calls, no real LLM keys, in-memory datastores — so a green local run predicts a green CI run.

## Secrets & registry

- CI uses **no** secrets by default. A real `NVIDIA_API_KEY` would only be needed for a workflow that exercises live LLM calls, which CI intentionally avoids.
- The Docker workflow **builds** the `api` and `react` images (with docker layer caching and compose validation) to prove a clean checkout compiles; it does **not** push to a registry. Publishing would require adding a push step plus `DOCKER_REGISTRY`/credentials secrets.

## Adding a job

1. Add the job to `.github/workflows/ci.yml`.
2. Keep it hermetic (no network-dependent assertions, no secrets).
3. Mirror the job's commands as a local `scripts/` or documented step so it stays reproducible.