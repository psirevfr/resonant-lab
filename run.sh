#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ] || [ ! -f frontend/dist/index.html ]; then
  printf 'Installation absente : lancer ./setup.sh avec Python 3.12+ et Node.js 20+.\n' >&2
  exit 1
fi
export PYTHONPATH="$PWD/backend"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
printf 'Résonant : http://127.0.0.1:8000 — Ctrl+C pour arrêter.\n'
exec .venv/bin/python -m uvicorn lab.app:app --host 127.0.0.1 --port 8000
