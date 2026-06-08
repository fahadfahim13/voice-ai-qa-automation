#!/usr/bin/env bash
# C11 — stop the dashboard started by vps_start.sh (PID-file based).
#
# Usage:  bash scripts/vps_stop.sh
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/qa}"
PID_FILE="$APP_DIR/dashboard.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "[stop] No PID file ($PID_FILE) — nothing to stop."
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
  echo "[stop] Process not running (stale PID file) — cleaning up."
  rm -f "$PID_FILE"
  exit 0
fi

echo "[stop] Stopping pid $pid …"
kill "$pid" 2>/dev/null || true
for _ in $(seq 1 20); do
  kill -0 "$pid" 2>/dev/null || break
  sleep 0.5
done
if kill -0 "$pid" 2>/dev/null; then
  echo "[stop] Still alive — sending SIGKILL."
  kill -9 "$pid" 2>/dev/null || true
fi
rm -f "$PID_FILE"
echo "[stop] Stopped."
