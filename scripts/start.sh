#!/usr/bin/env bash
# Start PostgreSQL, backend API, and frontend dev server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

SKIP_DOCKER="${SKIP_DOCKER:-0}"

start_postgres() {
  if [[ "${SKIP_DOCKER}" == "1" ]]; then
    log "postgres: skipped (SKIP_DOCKER=1)"
    return 0
  fi

  log "postgres: starting via docker compose"
  docker compose -f "${ROOT_DIR}/docker-compose.yml" up -d postgres
  wait_for_port "127.0.0.1" "${POSTGRES_PORT}" "postgres"
}

start_backend() {
  local pid
  pid="$(read_pid_file "${BACKEND_PID_FILE}")"
  if is_pid_running "${pid}"; then
    log "backend: already running (pid ${pid})"
    return 0
  fi
  rm -f "${BACKEND_PID_FILE}"

  log "backend: starting on :${BACKEND_PORT} (db ${POSTGRES_PORT})"
  (
    cd "${BACKEND_DIR}"
    export DATABASE_URL
    nohup "${VENV_PYTHON}" startup.py >>"${LOG_DIR}/backend.log" 2>&1 &
    echo $! >"${BACKEND_PID_FILE}"
  )

  pid="$(read_pid_file "${BACKEND_PID_FILE}")"
  wait_for_http "http://127.0.0.1:${BACKEND_PORT}/health" "backend"
  log "backend: pid ${pid}, log → logs/backend.log"
}

start_frontend() {
  local pid
  pid="$(read_pid_file "${FRONTEND_PID_FILE}")"
  if is_pid_running "${pid}"; then
    log "frontend: already running (pid ${pid})"
    return 0
  fi
  rm -f "${FRONTEND_PID_FILE}"

  log "frontend: starting on :${FRONTEND_PORT}"
  (
    cd "${FRONTEND_DIR}"
    nohup npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}" \
      >>"${LOG_DIR}/frontend.log" 2>&1 &
    echo $! >"${FRONTEND_PID_FILE}"
  )

  pid="$(read_pid_file "${FRONTEND_PID_FILE}")"
  wait_for_port "127.0.0.1" "${FRONTEND_PORT}" "frontend"
  log "frontend: pid ${pid}, log → logs/frontend.log"
}

main() {
  ensure_prerequisites
  start_postgres
  start_backend
  start_frontend

  cat <<EOF

tender_knowledge is up:
  API:      http://127.0.0.1:${BACKEND_PORT}/health
  OpenAPI:  http://127.0.0.1:${BACKEND_PORT}/docs
  Frontend: http://127.0.0.1:${FRONTEND_PORT}/

Logs:  logs/backend.log  logs/frontend.log
Stop:  ./scripts/stop.sh
EOF
}

main "$@"
