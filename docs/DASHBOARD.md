# Operator Dashboard — architecture & hand-off

Streamlit multipage app for operating the QA harness: browse reports, trigger
runs, re-run a pinned version, and smoke-test the QA Read API. Built across cards
C0/C3/C4/C5/C6/C7/C8.

## Run

```powershell
uv sync --extra dev
uv run --extra report streamlit run backend/report/dashboard.py
```

## Layout

```
backend/report/
  dashboard.py        # nav entrypoint: set_page_config → require_password → st.navigation(pages)
  auth.py             # password gate (evaluate_access + require_password)
  data.py             # suite IO (list_suites/load_suite) + qa_health — pure, never raises into UI
  aggregate.py        # pass_rate, per_criterion_averages — pure, unit-tested
  rerun.py            # pinned_scenario_ids / version_delta (Reports re-run, 4b)
  site_targeting.py   # siteId validate/persist + admin URL→siteId (Run page, 4e)
  run_form.py         # form_to_job_kwargs, status_badge (Run page seam)
  views/              # one render() per page
    overview.py  reports.py  scenarios.py  run.py  call_detail.py  placeholders.py
backend/orchestrator/
  job_manager.py      # start_job → background subprocess (python -m scripts.run_suite); poll via get_job/list_jobs/tail_log
scripts/
  qa_smoke_test.py    # evaluate_smoke (pure) + run_smoke (sync, UI-safe) + CLI
  run_suite.py        # the suite runner the dashboard launches
```

**Data flow:** each page's `render()` pulls from the pure shared layer
(`data.py` / `aggregate.py` / `rerun.py`) and never blocks on long work — runs go
through `job_manager.start_job` as a subprocess so Streamlit stays responsive and
survives reruns. Nothing in the shared layer raises into the UI.

## Run page & recordings (C10)

- **Website input, not siteId.** The Run page targets a **website** (URL/hostname),
  normalized to a canonical host (`backend/db/websites.py::normalize_url`) and stored
  in the `websites` table (`backend/db/models.py::Website`). The internal `siteId` is
  resolved by the widget at call time and **cached back** onto the row when the run
  finishes (`job_manager._wait_and_finalize` → `set_site_id`). The raw siteId, a
  Validate button, and the admin URL→siteId scan live behind the Run page's
  **Advanced (siteId / debug)** expander.
- **Full-call audio.** Recordings play `full_call.wav` — a stereo mix (left = our
  caller, right = bot) built by `backend/audio_mix.py::build_full_call`; it falls back
  to bot-only `bot.webm` if the mix is missing. **ffmpeg is required** for the mix and
  is provided by the bundled `imageio-ffmpeg` dependency (no system install needed).
  `audio_mix.backfill_full_call(call_dir)` rebuilds the mix for old runs.
- **Job names.** Jobs carry an editable `name` (defaults to `"{website} {timestamp}"`);
  the `{timestamp}_{uuid}` `job_id` stays the internal key. Rename via the Run page's
  **✏️ Rename** control (`job_manager.rename_job`).

## Auth gate

**Per-user accounts (C9).** `backend/report/auth.py::require_auth()` is called once
at the top of `main()`. Standard stack — [PyJWT](https://pyjwt.readthedocs.io)
HS256 tokens, [passlib](https://passlib.readthedocs.io) bcrypt hashing,
[SQLAlchemy](https://docs.sqlalchemy.org) `users` table in SQLite
(`backend/db/`). Users log in with email + password; a signed JWT is stored in a
browser cookie (survives refresh) and validated on every page. `JWT_SECRET` unset →
an ephemeral key + a warning banner (tokens won't survive a restart). Manage users
with `scripts/manage_users.py` (`create-user` / `list-users` / `deactivate-user` /
`reset-password`); `ADMIN_EMAIL`/`ADMIN_PASSWORD` seed the first user on first run.
`require_password()` remains as a deprecated shim that calls `require_auth()`.

## Smoke test

`scripts/qa_smoke_test.py` reuses the typed QA client
(`health` / `list_conversations` / `auth_gate_check`). `evaluate_smoke(...)` is a
pure pass/fail function (unit-tested); `run_smoke()` runs the live probes and never
raises (UI-safe). Surfaced as the **🩺 Run smoke test** button on Overview and as a
CLI (`uv run python -m scripts.qa_smoke_test`, exit non-zero on failure).

## Adding a page

1. Add `def render() -> None:` in `backend/report/views/<name>.py` (read from
   `data.py`/`aggregate.py`; don't block — use `job_manager` for long work).
2. Register it in `dashboard.py`:
   `st.Page(<name>.render, title="…", icon="…", url_path="…")`.

## Deploy notes (Priority 4 / C11) — rootless bare-metal on the `analytics` VPS

A live audit (2026-06-05) of `analytics@38.247.189.143:2203` showed an **unprivileged
jail**: 72 vCPU / 251 GB RAM but **no `sudo`, `apt`, `systemd`, or Docker** — so a
Docker/Coolify deploy **cannot run on this box**. We deploy **bare-metal** (uv venv +
`nohup`), bind `127.0.0.1`, and reach it via an **SSH tunnel**; the C9 login gates the UI.

### Tiered rollout
- **Phase A — reporting-only (today, zero ops).** `HARNESS_RUNS_ENABLED=false` hides the
  Run / Re-run pages (no Chromium needed). Reports / Scenarios / smoke test all work.
- **Phase B — full runner (after one ops step).** Chromium + its system libs are missing
  and `playwright install-deps` needs **root**, so ops runs once on the host:
  `playwright install-deps chromium` (root), then on the box
  `uv run playwright install chromium`; set `HARNESS_RUNS_ENABLED=1` and restart.
  If `install-deps` is unavailable, the apt packages are: `libnss3 libnssutil3
  libatk1.0-0 libatk-bridge2.0-0 libcups2 libgbm1 libasound2 libxkbcommon0
  libpango-1.0-0 libxcomposite1 libxdamage1 libxrandr2 libgtk-3-0`.
- **Phase C — optional managed ingress.** Ask ops to route a subdomain → `:8501` with
  TLS; then bind `0.0.0.0` and rely on the C9 JWT instead of the tunnel.

### Scripts (`scripts/vps_*.sh`)
| Script | What it does |
|--------|--------------|
| `vps_bootstrap.sh` | idempotent: install `uv`→`~/.local`, clone/pull repo→`~/qa`, `uv sync --extra report`, scaffold `~/qa/.env` (chmod 600), link `~/recordings`. **Never writes secrets.** |
| `vps_start.sh` | launch Streamlit via `nohup` bound to `127.0.0.1:8501`, PID→`~/qa/dashboard.pid`, log→`~/qa/dashboard.log`. Refuses to double-start. |
| `vps_stop.sh` | TERM→KILL the PID-file process; clears stale PIDs. |
| `vps_status.sh` | PID liveness + `curl /_stcore/health`. |

**No boot persistence** (no systemd/cron) — after a container restart, re-run
`vps_start.sh` manually. Optional: `npx pm2` for crash-restart only (won't survive a host reboot).

### Phase-A access (SSH tunnel)
```
ssh -L 8501:127.0.0.1:8501 -p 2203 analytics@38.247.189.143
# then open http://localhost:8501 and log in (C9)
```

### Env vars (set real values only in `~/qa/.env`, chmod 600 — never commit)
| Var | Purpose |
|-----|---------|
| `QA_SHARED_SECRET` | QA Read API (`X-QA-Secret`). The value in `.env.example` is a placeholder; the previously-committed live secret must be **rotated** (handover §17). |
| `OPENROUTER_API_KEY` | caller persona + judges (real runs) |
| `OPENAI_API_KEY` | TTS/STT (real runs) |
| `JWT_SECRET` | **set in prod** — long random string signing auth tokens (C9); unset → logins reset on restart |
| `JWT_ACCESS_MINUTES` | token TTL (default `720` = 12h) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | seed the first dashboard user on first run |
| `QA_DB_URL` | user DB (default `sqlite:///reports/qa.db`) |
| `HARNESS_RUNS_ENABLED` | `false` = reporting-only (Phase A); `true` = full runner (Phase B) |
| `HARNESS_HEADLESS` | `1` forces `--headless` for dashboard-launched runs (set on headless hosts) |
| `HARNESS_CONCURRENCY` | parallel scenario workers (default `2`) |
| `DASHBOARD_PASSWORD` | legacy C8 shared gate (superseded by per-user auth) |

On boot, open the dashboard and click **🩺 Run smoke test** (Overview) to confirm the
deployment can reach the QA API and the secret is enforced.

> **Future managed option:** a publicly-reachable, auto-restarting deploy fits Coolify
> on a *different* ops host (with root/Docker) — not this rootless jail.
