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
  wait_for_postgres_ready
}

start_backend() {
  local pid
  pid="$(read_pid_file "${BACKEND_PID_FILE}")"

  if backend_health_ok; then
    if is_pid_running "${pid}"; then
      log "backend: already running (pid ${pid})"
    else
      log "backend: already responding on :${BACKEND_PORT} (refreshing stale pid file)"
      pids_listening_on_port "${BACKEND_PORT}" | head -n 1 >"${BACKEND_PID_FILE}" || true
    fi
    return 0
  fi

  if is_port_listening "${BACKEND_PORT}" || is_pid_running "${pid}"; then
    stop_backend_processes
  fi

  if backend_health_ok; then
    log "backend: already responding on :${BACKEND_PORT} after cleanup"
    pids_listening_on_port "${BACKEND_PORT}" | head -n 1 >"${BACKEND_PID_FILE}" || true
    return 0
  fi
  if is_port_listening "${BACKEND_PORT}"; then
    die "backend: port ${BACKEND_PORT} still in use after cleanup"
  fi

  log "backend: starting on :${BACKEND_PORT} (db ${POSTGRES_PORT}, reload=${BACKEND_RELOAD:-0})"
  (
    cd "${BACKEND_DIR}"
    export DATABASE_URL
    export BACKEND_RELOAD="${BACKEND_RELOAD:-0}"
    nohup "${VENV_PYTHON}" startup.py >>"${LOG_DIR}/backend.log" 2>&1 &
    echo $! >"${BACKEND_PID_FILE}"
  )

  pid="$(read_pid_file "${BACKEND_PID_FILE}")"
  if ! is_pid_running "${pid}"; then
    die "backend: process exited immediately — check logs/backend.log"
  fi

  wait_for_backend_health "${pid}"
  pids_listening_on_port "${BACKEND_PORT}" | head -n 1 >"${BACKEND_PID_FILE}" || true
  pid="$(read_pid_file "${BACKEND_PID_FILE}")"
  log "backend: pid ${pid}, log → logs/backend.log"
}

start_frontend() {
  local pid
  pid="$(read_pid_file "${FRONTEND_PID_FILE}")"

  if is_port_listening "${FRONTEND_PORT}"; then
    if is_pid_running "${pid}"; then
      log "frontend: already running (pid ${pid})"
    else
      log "frontend: already listening on :${FRONTEND_PORT} (refreshing stale pid file)"
      pids_listening_on_port "${FRONTEND_PORT}" | head -n 1 >"${FRONTEND_PID_FILE}" || true
    fi
    return 0
  fi

  if is_pid_running "${pid}"; then
    log "frontend: stale process pid ${pid} without open port — stopping"
    kill "${pid}" 2>/dev/null || true
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
