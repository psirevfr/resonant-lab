#!/usr/bin/env bash
set -euo pipefail
if [ "${EUID}" -ne 0 ]; then printf 'Exécuter avec sudo.\n' >&2; exit 1; fi
case "${1:-}" in
  on)
    install -d -m 755 /var/lib/resonant-maintenance
    install -m 644 "$(dirname "$0")/maintenance.html" /var/lib/resonant-maintenance/maintenance.html
    touch /var/lib/resonant-maintenance/maintenance.flag
    printf 'Maintenance activée (si le snippet Nginx est installé).\n'
    ;;
  off)
    rm -f -- /var/lib/resonant-maintenance/maintenance.flag
    printf 'Maintenance désactivée.\n'
    ;;
  *) printf 'Usage : sudo %s on|off\n' "$0" >&2; exit 2;;
esac
