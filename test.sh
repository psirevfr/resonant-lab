#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/backend"
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
.venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend .venv/bin/python scripts/client_fixtures.py
(cd frontend && node tests/run.mjs && npm run build)
