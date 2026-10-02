#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/backend"
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
.venv/bin/python -m pytest backend/tests -q
(cd frontend && npm run build)
