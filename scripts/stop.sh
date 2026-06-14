#!/usr/bin/env bash
# Stop frontend, backend, and optionally PostgreSQL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

STOP_POSTGRES="${STOP_POSTGRES:-1}"

main() {
  stop_pid_file "frontend" "${FRONTEND_PID_FILE}" "${FRONTEND_PORT}"
  stop_backend_processes

  if [[ "${STOP_POSTGRES}" == "1" ]]; then
    if command -v docker >/dev/null 2>&1; then
      log "postgres: stopping docker compose service"
      docker compose -f "${ROOT_DIR}/docker-compose.yml" stop postgres 2>/dev/null || true
    fi
  else
    log "postgres: left running (STOP_POSTGRES=0)"
  fi

  log "all services stopped"
}

main "$@"
