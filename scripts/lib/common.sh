#!/usr/bin/env bash
# Shared helpers for tender_knowledge service scripts.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
LOG_DIR="${ROOT_DIR}/logs"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
POSTGRES_PORT="${POSTGRES_PORT:-5433}"
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://tender:tender@127.0.0.1:${POSTGRES_PORT}/tender_knowledge}"
export DATABASE_URL

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

log() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

die() {
  log "ERROR: $*"
  exit 1
}

is_pid_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

read_pid_file() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    cat "${file}"
  fi
}

pids_listening_on_port() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

is_port_listening() {
  local port="$1"
  [[ -n "$(pids_listening_on_port "${port}")" ]]
}

stop_listeners_on_port() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(pids_listening_on_port "${port}")"

  if [[ -z "${pids}" ]]; then
    return 0
  fi

  log "${label}: freeing port ${port} (pids: $(echo "${pids}" | tr '\n' ' '))"
  # shellcheck disable=SC2046
  kill $(echo "${pids}") 2>/dev/null || true
  for _ in $(seq 1 10); do
    is_port_listening "${port}" || break
    sleep 0.5
  done
  if is_port_listening "${port}"; then
  # shellcheck disable=SC2046
    kill -9 $(pids_listening_on_port "${port}") 2>/dev/null || true
    sleep 0.5
  fi
}

stop_backend_processes() {
  local pid
  pid="$(read_pid_file "${BACKEND_PID_FILE}")"

  if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
    log "backend: stopping pid ${pid}"
    kill "${pid}" 2>/dev/null || true
    for _ in $(seq 1 10); do
      is_pid_running "${pid}" || break
      sleep 0.5
    done
    if is_pid_running "${pid}"; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  elif is_port_listening "${BACKEND_PORT}"; then
    log "backend: no pid file, but port ${BACKEND_PORT} is in use — cleaning up"
  else
    log "backend: not running"
  fi

  pkill -f "${BACKEND_DIR}/startup.py" 2>/dev/null || true
  pkill -f "uvicorn.*src.main:app" 2>/dev/null || true
  stop_listeners_on_port "${BACKEND_PORT}" "backend"
  sleep 1
  rm -f "${BACKEND_PID_FILE}"
}

backend_health_url() {
  printf 'http://127.0.0.1:%s/health' "${BACKEND_PORT}"
}

probe_backend_health() {
  local url raw http_code body
  url="$(backend_health_url)"
  raw="$(
    curl --noproxy '*' -sS --connect-timeout 2 --max-time 10 \
      -w $'\n%{http_code}' "${url}" 2>&1
  )" || {
    printf '000\t%s' "${raw}"
    return 1
  }
  http_code="${raw##*$'\n'}"
  body="${raw%$'\n'*}"
  printf '%s\t%s' "${http_code}" "${body}"
}

backend_health_ok() {
  local probe http_code body
  probe="$(probe_backend_health)" || return 1
  http_code="${probe%%$'\t'*}"
  body="${probe#*$'\t'}"
  [[ "${http_code}" == "200" ]] \
    && [[ "${body}" == *"\"status\""* ]] \
    && [[ "${body}" == *"ok"* ]]
}

wait_for_backend_health() {
  local url
  url="$(backend_health_url)"
  local pid="${1:-}"
  local retries="${2:-90}"
  local attempt=0
  local last_error=""
  local probe http_code body

  while [[ "${attempt}" -lt "${retries}" ]]; do
    attempt=$((attempt + 1))

    if [[ -n "${pid}" ]] && ! is_pid_running "${pid}"; then
      if backend_health_ok; then
        log "backend: ready at ${url} (launcher pid ${pid} replaced)"
        return 0
      fi
      die "backend: process ${pid} exited during startup — check logs/backend.log"
    fi

    if backend_health_ok; then
      log "backend: ready at ${url}"
      return 0
    fi

    if (( attempt % 10 == 0 )); then
      probe="$(probe_backend_health 2>/dev/null || true)"
      http_code="${probe%%$'\t'*}"
      body="${probe#*$'\t'}"
      if is_port_listening "${BACKEND_PORT}"; then
        last_error="port open, /health not ready (attempt ${attempt}/${retries}, http=${http_code:-n/a})"
      else
        last_error="port closed, backend still initializing (attempt ${attempt}/${retries})"
      fi
      if [[ -n "${body}" && "${http_code}" != "200" ]]; then
        last_error="${last_error}: ${body}"
      fi
      log "backend: ${last_error}"
    fi

    sleep 1
  done

  if backend_health_ok; then
    log "backend: ready at ${url} (responded after wait loop)"
    return 0
  fi

  probe="$(probe_backend_health 2>/dev/null || true)"
  http_code="${probe%%$'\t'*}"
  body="${probe#*$'\t'}"
  log "backend: last probe: http=${http_code:-n/a} ${body:-no response}"
  die "backend: timed out waiting for ${url}"
}

stop_pid_file() {
  local name="$1"
  local file="$2"
  local port="${3:-}"
  local pid
  pid="$(read_pid_file "${file}")"

  if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
    log "${name}: stopping pid ${pid}"
    kill "${pid}" 2>/dev/null || true
    for _ in $(seq 1 10); do
      is_pid_running "${pid}" || break
      sleep 0.5
    done
    if is_pid_running "${pid}"; then
      log "${name}: force killing pid ${pid}"
      kill -9 "${pid}" 2>/dev/null || true
    fi
  elif [[ -n "${pid}" ]]; then
    log "${name}: stale pid file (${pid})"
  else
    log "${name}: not running (no pid file)"
  fi

  if [[ -n "${port}" ]] && is_port_listening "${port}"; then
    stop_listeners_on_port "${port}" "${name}"
  fi

  rm -f "${file}"
}

wait_for_postgres_ready() {
  local retries="${1:-30}"

  for _ in $(seq 1 "${retries}"); do
    if (echo >/dev/tcp/127.0.0.1/"${POSTGRES_PORT}") 2>/dev/null \
      && docker compose -f "${ROOT_DIR}/docker-compose.yml" exec -T postgres \
        pg_isready -U tender -d tender_knowledge >/dev/null 2>&1; then
      log "postgres: accepting connections"
      return 0
    fi
    sleep 1
  done

  die "postgres: timed out waiting for database connections on port ${POSTGRES_PORT}"
}

wait_for_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  local retries="${4:-30}"

  for _ in $(seq 1 "${retries}"); do
    if (echo >/dev/tcp/"${host}"/"${port}") 2>/dev/null; then
      log "${label}: ready on ${host}:${port}"
      return 0
    fi
    sleep 1
  done

  die "${label}: timed out waiting for ${host}:${port}"
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local retries="${3:-30}"

  for _ in $(seq 1 "${retries}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      log "${label}: ready at ${url}"
      return 0
    fi
    sleep 1
  done

  die "${label}: timed out waiting for ${url}"
}

ensure_prerequisites() {
  command -v docker >/dev/null 2>&1 || die "docker not found"
  docker compose version >/dev/null 2>&1 || die "docker compose not found"
  [[ -x "${VENV_PYTHON}" ]] || die "missing .venv — run: python -m venv .venv && .venv/bin/pip install -e backend[dev]"
  [[ -d "${FRONTEND_DIR}/node_modules" ]] || die "missing frontend deps — run: cd frontend && npm install"
}
