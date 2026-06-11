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

stop_pid_file() {
  local name="$1"
  local file="$2"
  local pid
  pid="$(read_pid_file "${file}")"

  if [[ -z "${pid}" ]]; then
    log "${name}: not running (no pid file)"
    return 0
  fi

  if is_pid_running "${pid}"; then
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
  else
    log "${name}: stale pid file (${pid}), cleaning up"
  fi

  rm -f "${file}"
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
