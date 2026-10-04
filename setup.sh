#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ requis ; définir PYTHON_BIN."'
command -v node >/dev/null || { printf 'Node.js 20+ requis.\n' >&2; exit 1; }
command -v npm >/dev/null || { printf 'npm requis.\n' >&2; exit 1; }
node -e 'if(Number(process.versions.node.split(".")[0])<20){console.error("Node.js 20+ requis");process.exit(1)}'
if [ ! -x .venv/bin/python ]; then "$PYTHON_BIN" -m venv .venv; fi
.venv/bin/python -c 'import sys; assert sys.version_info >= (3,12), "Ancienne .venv : recréer cet environnement avec Python 3.12+."; assert sys.prefix != sys.base_prefix, "Python doit être isolé dans .venv."'
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.lock.txt
.venv/bin/python -m pip check
# TypeScript/Vite are build dependencies, required even when NODE_ENV=production.
(cd frontend && npm ci --include=dev --no-audit --no-fund && npm run build)
test -s frontend/dist/index.html || { printf 'Build Vite incomplet.\n' >&2; exit 1; }
# Reference fixtures are optional; production installs do not overwrite examples.
if [ "${RESONANT_SETUP_FIXTURES:-0}" = '1' ]; then
  PYTHONPATH=backend .venv/bin/python scripts/make_fixtures.py
fi
printf '\nInstallation terminée. Production : run-web.sh et worker.sh via leurs services. Local : ./run.sh\n'
