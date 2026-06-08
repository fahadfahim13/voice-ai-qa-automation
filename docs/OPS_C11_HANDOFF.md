# C11 deploy — ops handoff checklist

One page for BizFinder ops. The dashboard code is merged; these items gate the
actual deployment of the QA dashboard on the `analytics` VPS. Phase A (reporting-only)
needs **none of the root actions** — only items 1 and 4 unblock it.

Target host: `analytics@38.247.189.143:2203` (Ubuntu 24.04, rootless jail — no sudo/apt/Docker).

## 1. Confirm the deploy host (GO / NO-GO) — *blocks everything*
The handover frames `analytics` as an SFTP-audio box. We want to run the QA dashboard
there as a rootless user process (uv venv + `nohup`, bound to `127.0.0.1`, reached by
SSH tunnel). **Please confirm this is in scope.** If not, name the intended host.

## 2. Chromium system libs (root, one-time) — *blocks Phase B live runs only*
Reporting works without a browser. Live runs (dashboard-triggered calls) need Chromium,
whose system libs are missing and require root once:

```bash
# preferred:
playwright install-deps chromium
# fallback if install-deps is unavailable — apt-get install:
libnss3 libnssutil3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libgbm1 \
libasound2 libxkbcommon0 libpango-1.0-0 libxcomposite1 libxdamage1 libxrandr2 libgtk-3-0
```
After this, the app user runs `uv run playwright install chromium` (no root) and flips
`HARNESS_RUNS_ENABLED=1`.

## 3. Rotate the leaked QA shared secret (security) — *blocks sign-off*
The previous `QA_SHARED_SECRET` was committed to git history. Please **rotate it**
(handover §17) and provide the new value out-of-band. The repo now ships only a
placeholder in `.env.example`; the real value lives solely in `~/qa/.env` (chmod 600).

## 4. Production secrets for `~/qa/.env` (out-of-band, never in git)
- `JWT_SECRET` — long random string (the dev can generate one; required or C9 logins reset on restart)
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — seeds the first dashboard user on first run
- `OPENROUTER_API_KEY` — required for real runs (Phase B)
- `QA_SHARED_SECRET` — the rotated value from item 3
- optional: `OPENAI_API_KEY`, `ELEVENLABS_*`

## 5. Ingress decision — *non-blocking for Phase A*
- **Recommended (zero-ops):** SSH tunnel — `ssh -L 8501:127.0.0.1:8501 -p 2203 analytics@38.247.189.143` → `http://localhost:8501`.
- **Phase C (optional):** route a subdomain → `:8501` with TLS; then the app binds `0.0.0.0` and relies on the C9 JWT instead of the tunnel.

---
Full deploy runbook + script reference: see `docs/DASHBOARD.md`.
