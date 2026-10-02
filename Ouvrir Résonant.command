#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
url='http://127.0.0.1:8000/'
ready() {
  /usr/bin/curl --fail --silent --max-time 2 "${url}api/health" 2>/dev/null | /usr/bin/grep -q '"status":"ok"'
}
open_site() {
  if [ "${RESONANT_NO_BROWSER:-0}" != '1' ]; then /usr/bin/open "$url"; fi
}
if ready; then
  printf 'Résonant est déjà actif. Ouverture du site…\n'
  open_site
  exit 0
fi
if /usr/sbin/lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  printf 'Le port 8000 est occupé par un autre serveur. Fermez-le puis réessayez.\n'
  exit 1
fi
mkdir -p .local
./run.sh >.local/server.log 2>&1 &
server_pid=$!
cleanup() {
  if kill -0 "$server_pid" 2>/dev/null; then kill "$server_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP
for attempt in {1..60}; do
  if ready; then
    printf '\nRésonant est prêt : %s\nGardez cette fenêtre ouverte pendant l’utilisation.\nCtrl+C arrête le serveur.\n\n' "$url"
    open_site
    wait "$server_pid"
    exit 0
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    printf 'Le serveur n’a pas démarré :\n'
    cat .local/server.log
    exit 1
  fi
  sleep 1
done
printf 'Le serveur ne répond pas après une minute. Détails :\n'
cat .local/server.log
exit 1
