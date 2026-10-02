#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12 ou plus récent requis ; définir PYTHON_BIN si nécessaire."'
if [ ! -x .venv/bin/python ]; then "$PYTHON_BIN" -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.lock.txt
(cd frontend && npm ci && npm run build)
PYTHONPATH=backend .venv/bin/python scripts/make_fixtures.py
printf '\nInstallation terminée. Lancer ./run.sh puis ouvrir http://127.0.0.1:8000\n'
