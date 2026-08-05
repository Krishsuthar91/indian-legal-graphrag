#!/bin/sh
# ---------------------------------------------------------------------------
# Backend container entrypoint.
#
#  1. Optionally load the docker env profile (from deploy/env/.env.docker).
#  2. Fail fast when production secrets are missing.
#  3. Run database migrations / setup (no-op hook).
#  4. Start uvicorn.
#
# NOTE: On Windows the compose service may set a command directly; this script
# is used when the image runs outside Compose (e.g. a plain `docker run`).
# ---------------------------------------------------------------------------
set -e

PYTHON=${PYTHON:-python}
APP_MODULE=${APP_MODULE:-src.main:app}

# Load the docker profile only if APP_ENV is not already set.
if [ -z "${APP_ENV:-}" ] && [ -f /app/deploy/env/.env.docker ]; then
    . /app/deploy/env/.env.docker
fi

# Fail fast on missing production secrets.
if [ "${APP_ENV:-development}" = "production" ]; then
    "$PYTHON" -m deploy.config.cli validate --env production
fi

exec "$PYTHON" -m uvicorn "$APP_MODULE" --host 0.0.0.0 --port 8000
