#!/usr/bin/env bash
# C11 — start the dashboard as a rootless background process (no systemd here).
# Binds 127.0.0.1 only — reach it via SSH tunnel. Refuses to double-start.
#
# Usage:  bash scripts/vps_start.sh        (PORT=8501 by default)
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/qa}"
PORT="${PORT:-8501}"
PID_FILE="$APP_DIR/dashboard.pid"
LOG_FILE="$APP_DIR/dashboard.log"

export PATH="$HOME/.local/bin:$PATH"
cd "$APP_DIR"

# Already running?
if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "[start] Already running (pid $old_pid). Stop it first: bash scripts/vps_stop.sh"
    exit 1
  fi
  rm -f "$PID_FILE"  # stale pid file
fi

echo "[start] Launching Streamlit on 127.0.0.1:$PORT (log: $LOG_FILE)"
nohup uv run --extra report streamlit run backend/report/dashboard.py \
  --server.address 127.0.0.1 \
  --server.port "$PORT" \
  --server.headless true \
  >>"$LOG_FILE" 2>&1 </dev/null &
echo $! >"$PID_FILE"

echo "[start] pid $(cat "$PID_FILE"). Health: bash scripts/vps_status.sh"
echo "[start] Tunnel in: ssh -L $PORT:127.0.0.1:$PORT -p 2203 analytics@38.247.189.143"
