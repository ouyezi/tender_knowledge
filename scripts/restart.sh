#!/usr/bin/env bash
# Restart all tender_knowledge services (stop then start).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/stop.sh"
sleep 1
"${SCRIPT_DIR}/start.sh"
