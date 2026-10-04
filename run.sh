#!/usr/bin/env bash
# Local launcher: production supervisors should manage run-web.sh and worker.sh separately.
set -euo pipefail
cd "$(dirname "$0")"
worker_pid=''
web_pid=''
cleanup() {
  for child in "$web_pid" "$worker_pid"; do
    if [ -n "$child" ]; then kill -TERM "$child" 2>/dev/null || true; fi
  done
  for child in "$web_pid" "$worker_pid"; do
    if [ -n "$child" ]; then wait "$child" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
./worker.sh &
worker_pid=$!
./run-web.sh &
web_pid=$!
printf 'Résonant : http://%s:%s — serveur et worker actifs ; Ctrl+C pour arrêter.\n' "${RESONANT_HOST:-127.0.0.1}" "${RESONANT_PORT:-8000}"
# Bash 3 (macOS): monitor both children without wait -n.
while kill -0 "$web_pid" 2>/dev/null && kill -0 "$worker_pid" 2>/dev/null; do sleep 1; done
printf 'Un processus s’est arrêté ; arrêt de son compagnon.\n' >&2
exit 1
