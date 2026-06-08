#!/usr/bin/env bash
# C11 — idempotent rootless bootstrap for the analytics VPS (no sudo/apt/Docker).
#
# Installs uv to ~/.local, clones/updates the repo to ~/qa, syncs the report
# extra, and prepares ~/qa/.env (chmod 600) for the operator to fill in. Safe to
# re-run. NEVER writes secrets — the operator edits ~/qa/.env by hand.
#
# Usage:  bash scripts/vps_bootstrap.sh
# Override defaults via env: REPO_URL=… BRANCH=… APP_DIR=… bash scripts/vps_bootstrap.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/fahadfahim13/voice-ai-qa-automation.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-$HOME/qa}"

log() { printf '\033[1;35m[bootstrap]\033[0m %s\n' "$*"; }

# 1) uv → ~/.local (no root needed)
if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv to ~/.local …"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# 2) ensure ~/.local/bin is on PATH for future shells
if ! grep -qs 'HOME/.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  log "Adding ~/.local/bin to PATH in ~/.bashrc"
  printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >>"$HOME/.bashrc"
fi

command -v uv >/dev/null 2>&1 || { log "uv not on PATH after install — open a new shell and re-run."; exit 1; }

# 3) clone or update the repo
if [ -d "$APP_DIR/.git" ]; then
  log "Updating existing checkout at $APP_DIR"
  git -C "$APP_DIR" pull --ff-only
else
  log "Cloning $REPO_URL ($BRANCH) → $APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# 4) dependencies (report extra = Streamlit + reporting; no browser needed)
log "uv sync --extra report …"
uv sync --extra report

# 5) .env scaffold (operator fills it; never write secrets here)
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  log "Created ~/qa/.env (chmod 600) — EDIT IT before starting (secrets, JWT_SECRET, ADMIN_*)."
else
  log ".env already present — leaving it untouched."
fi

# 6) link the SFTP audio dir into the repo if it exists
if [ -d "$HOME/recordings" ] && [ ! -e "$APP_DIR/recordings" ]; then
  ln -s "$HOME/recordings" "$APP_DIR/recordings"
  log "Symlinked ~/qa/recordings → ~/recordings"
fi

cat <<EOF

[bootstrap] Done. Next steps:
  1. Edit secrets:           nano $APP_DIR/.env
       (set JWT_SECRET, ADMIN_EMAIL/ADMIN_PASSWORD, OPENROUTER_API_KEY, QA_SHARED_SECRET;
        leave HARNESS_RUNS_ENABLED=false for Phase A reporting-only)
  2. Start the dashboard:    bash $APP_DIR/scripts/vps_start.sh
  3. Check it:               bash $APP_DIR/scripts/vps_status.sh
  4. From your laptop:       ssh -L 8501:127.0.0.1:8501 -p 2203 analytics@38.247.189.143
                             then open http://localhost:8501
EOF
