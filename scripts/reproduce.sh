#!/usr/bin/env bash
#
# Explaintool Module 10 — one-command reproducibility script.
#
# Installs the locked evaluation dependencies, runs the full offline benchmark
# (retrieval, explainability, RAGAS, baselines, ablation), regenerates every
# report (CSV/JSON/Markdown/PDF) and figure (SVG/PNG), and runs the test suite.
#
# Usage:
#   bash scripts/reproduce.sh            # full run
#   bash scripts/reproduce.sh --quick    # quick run (first 3 items)
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

QUICK_FLAG=""
if [[ "${1:-}" == "--quick" ]]; then
  QUICK_FLAG="--quick"
  echo "[reproduce] quick mode enabled"
fi

PYTHON_BIN="${PYTHON:-python3}"

echo "[reproduce] using ${PYTHON_BIN}"

if [[ ! -d .venv ]]; then
  echo "[reproduce] creating virtual environment..."
  "${PYTHON_BIN}" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[reproduce] installing locked requirements..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements-lock.txt

echo "[reproduce] running evaluation harness..."
"${PYTHON_BIN}" -m eval.cli --config data/eval/config/experiment.json \
  --out evaluation ${QUICK_FLAG}

echo "[reproduce] running test suite..."
"${PYTHON_BIN}" -m pytest -q

echo "[reproduce] done."
echo "  reports -> $(pwd)/evaluation/reports"
echo "  figures -> $(pwd)/evaluation/figures"
