#!/usr/bin/env bash
# C11 — report dashboard status: PID liveness + Streamlit health endpoint.
# Exit 0 = healthy, 1 = not running / unhealthy.
#
# Usage:  bash scripts/vps_status.sh
set -uo pipefail

APP_DIR="${APP_DIR:-$HOME/qa}"
PORT="${PORT:-8501}"
PID_FILE="$APP_DIR/dashboard.pid"
HEALTH_URL="http://127.0.0.1:$PORT/_stcore/health"

rc=0

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
  echo "[status] process: RUNNING (pid $(cat "$PID_FILE"))"
else
  echo "[status] process: NOT RUNNING"
  rc=1
fi

if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
  echo "[status] health  : OK (200 from $HEALTH_URL)"
else
  echo "[status] health  : UNREACHABLE ($HEALTH_URL)"
  rc=1
fi

exit "$rc"
