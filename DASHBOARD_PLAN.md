# Plan: Custom FastAPI Dashboard to control the BizFinder Voice QA harness

## Context

The voice QA harness (`D:\office\voice-ai-qa-automation`) is fully functional from the CLI: it can run scenarios against any tenant (`--site`), produce stereo call recordings (`full_call.wav`), and write structured suite reports (`report.html`, `summary.csv`, `suite.json` + per-call `text_verdict.json` / `audio_verdict.json`). A lightweight Streamlit dashboard exists at `backend/report/dashboard.py` but is read-only and visually constrained.

We are building a **modern, custom operator dashboard** on top of FastAPI to:
1. List and inspect every past suite ("reporting with version").
2. Re-run a past suite end-to-end with the same config.
3. Browse the test scenario library.
4. Start a new QA run interactively (pick scenarios, target site, headless flag).
5. Provide an arbitrary website hostname as a target without editing `.env`.

The dashboard must look professional — eye-soothing palette, fixed header, collapsible side drawer, footer, well-decorated cards/tables, smooth interactions for the inevitable client demo.

## Confirmed decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend stack | FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CSS | Single Python repo, no Node/build step, polished UI within reach, HTMX gives real-time feel without WebSockets boilerplate |
| Auth | None — single-user, local | Fastest to v1; **flagged tension with "cloud-deployable" below** |
| "Re-run a version" | Re-run a past suite end-to-end with the same persisted config | Maps naturally to a "Re-run this suite" button on every suite-detail page |
| Deployment | Cloud-deployable from day one (env-driven, Docker-ready, no hardcoded paths) | Imposes good hygiene up front; minor extra cost |

### ⚠ Tension to call out

"No auth" + "cloud-deployable" → **dashboard MUST bind to `127.0.0.1` by default**. Exposing on `0.0.0.0` or a public hostname requires a follow-up auth step (basic auth env-var → reverse-proxy auth). The Docker image will refuse to bind beyond localhost unless `DASHBOARD_ALLOW_PUBLIC=true` AND `DASHBOARD_BASIC_AUTH_PASSWORD` are both set. This is the smallest safe guard before Phase 2 auth.

## Tech stack (full)

### Backend
- **FastAPI ≥ 0.110** — HTTP framework
- **Uvicorn ≥ 0.30** — ASGI server
- **Pydantic 2.x** — already in deps; request/response models
- **Jinja2 ≥ 3.1** — already in deps; server-rendered templates
- **SQLite via `aiosqlite`** — run metadata DB at `reports/dashboard.db` (no external DB)
- **`sqlalchemy[asyncio] ≥ 2.0`** — typed ORM for the SQLite tables (optional; fall back to raw aiosqlite if we want to stay lighter)
- **`python-multipart`** — form posts from the dashboard
- **`watchfiles`** — live-reload during dev
- **`anyio`** — already in deps

### Frontend (no build step)
- **HTMX 2.x** (`htmx.org`) — partial swaps, polling, optimistic UI; loaded from CDN
- **Alpine.js 3.x** — small client-side reactivity (dropdowns, modals, toggle states); CDN
- **Tailwind CSS via Play CDN for v1** → migrate to Tailwind CLI build (`tailwindcss.exe` standalone, no Node) for production
- **Iconography**: Lucide icons (inline SVG; tiny per-icon footprint)
- **Fonts**: Inter (sans), JetBrains Mono (mono) — self-hosted under `static/fonts/` for offline-safe rendering
- **Charts**: ApexCharts.js (CDN) — only if we add the trends view in §10

### Process model
- **In-process FastAPI app** for the HTTP API + UI.
- **Out-of-process suite runner**: each run spawns `uv run python -m scripts.run_suite ...` as a subprocess so a hanging Playwright/Chromium can't take the dashboard down. PID, exit code, and stdout/stderr live in SQLite + a per-run log file under `reports/suite_*/run.log`.
- **Background tasks** via FastAPI `BackgroundTasks` only for cheap things (DB writes, suite directory parsing). Long work is always subprocessed.

## Visual design

### Color palette — "eye-soothing operator console"

Layered slates + a single indigo accent. Passes WCAG AA contrast at both light and (planned) dark modes.

| Token | Hex | Role |
|-------|-----|------|
| `bg-base` | `#f8fafc` (slate-50) | App background |
| `bg-card` | `#ffffff` | Card / table surfaces |
| `bg-sidebar` | `#0f172a` (slate-900) | Side drawer background |
| `bg-sidebar-active` | `#1e293b` (slate-800) | Active nav item |
| `bg-header` | `#ffffff` | Top header (subtle bottom border) |
| `bg-footer` | `#f1f5f9` (slate-100) | Footer band |
| `bg-soft-accent` | `#eef2ff` (indigo-50) | Chip / hover backgrounds |
| `text-primary` | `#1e293b` (slate-800) | Body |
| `text-secondary` | `#64748b` (slate-500) | Captions |
| `text-on-dark` | `#e2e8f0` (slate-200) | Sidebar text |
| `accent` | `#6366f1` (indigo-500) | Primary buttons, links, active state |
| `accent-hover` | `#4f46e5` (indigo-600) | Hover/active button |
| `success` | `#10b981` (emerald-500) | Pass badges |
| `warn` | `#f59e0b` (amber-500) | Mid-score / in-progress |
| `danger` | `#f43f5e` (rose-500) | Fail badges, error states |
| `border` | `#e2e8f0` (slate-200) | Card borders, table lines |
| `focus-ring` | `#a5b4fc` (indigo-300) | Keyboard focus |

Dark mode (Phase 2 toggle): swap bg-base → `#020617`, bg-card → `#0f172a`, text → `#e2e8f0`, keep accent → indigo-400.

### Typography
- **Inter 400/500/600** for UI, **JetBrains Mono 400** for IDs/JSON/code.
- Scale: 14px body, 12px caption, 16/18/24px h3/h2/h1.
- Line height 1.5 body, 1.3 headings.

### Layout shell

```
┌─────────────────────────────────────────────────────────────────────┐
│ HEADER (sticky, h-14)                                               │
│  • Logo + title  • Site target chip  • Run-status pill  • Settings  │
├──────────┬──────────────────────────────────────────────────────────┤
│          │ MAIN CONTENT (scrolls)                                   │
│ SIDEBAR  │   • Page title row                                       │
│ (w-60,   │   • Cards / tables / detail panes                        │
│ collap-  │                                                          │
│ sible to │                                                          │
│ w-16     │                                                          │
│ icon-    │                                                          │
│ only)    │                                                          │
│          │                                                          │
├──────────┴──────────────────────────────────────────────────────────┤
│ FOOTER (h-10)  v0.2.0  ·  16 scenarios loaded  ·  © …               │
└─────────────────────────────────────────────────────────────────────┘
```

- Header is `sticky top-0 bg-header border-b border-border z-40`.
- Sidebar is `fixed left-0 top-14 bottom-10 bg-sidebar text-on-dark` with a collapse toggle (`<` icon) that persists in `localStorage`.
- Sidebar nav items: **Dashboard · Runs · Scenarios · New run · Settings**, each with a Lucide icon + label.
- Footer is sticky on viewport bottom: shows app version, scenario count, and a tiny "Connected" dot.

### Decoration details

- Cards: `rounded-xl shadow-sm border border-border bg-card`, generous padding (`p-6`), section headers with a thin accent underline.
- Pass/Fail/Error badges as pill chips, all-caps 11px, soft background + colored text (e.g. pass = `bg-emerald-50 text-emerald-700`).
- Tables: zebra rows on hover, header `bg-slate-50 text-slate-500 uppercase text-xs tracking-wide`, sticky header on long tables.
- Buttons: primary (indigo filled), secondary (outline slate), danger (rose outline). All have `transition-colors`, `focus-visible:ring-2 focus-visible:ring-focus-ring` for accessibility.
- Audio player: native `<audio controls>` styled with a wrapper that adds a caption "caller L · bot R" under the player.
- Toast notifications: top-right, slide-in via Alpine.js, auto-dismiss after 4 s.
- Modal dialogs: centered, backdrop blur, `transform transition` open/close.
- Empty states: a Lucide illustration + helpful text + a primary CTA on every empty page.

## Architecture overview

```
                      ┌────────────────────────────┐
        HTTPS         │  Browser (Tailwind + HTMX) │
   ─────────────────► │  Alpine.js, ApexCharts     │
                      └────────────┬───────────────┘
                                   │ partial HTML / JSON
                       ┌───────────▼────────────────┐
                       │  FastAPI app (uvicorn)     │
                       │  • Jinja2 templates        │
                       │  • Pydantic models         │
                       │  • Routers: runs,          │
                       │    scenarios, settings,    │
                       │    artifacts               │
                       │  • Run manager service     │
                       └────┬────────────┬──────────┘
                            │            │ reads/writes
                            │            ▼
                            │  ┌─────────────────────┐
                            │  │  reports/           │
                            │  │   ├─ dashboard.db   │
                            │  │   └─ suite_*/       │
                            │  │       suite.json    │
                            │  │       summary.csv   │
                            │  │       call_*/       │
                            │  │         full_call.  │
                            │  │           wav       │
                            │  └─────────────────────┘
                            │
                            │ spawns
                            ▼
                ┌─────────────────────────────┐
                │  subprocess:                │
                │  uv run -m scripts.run_suite│
                │  --site … --replay-of …     │
                │   → writes reports/suite_*/ │
                └─────────────────────────────┘
```

## Folder structure (new)

```
voice-ai-qa-automation/
├── backend/
│   └── dashboard/                       NEW package
│       ├── __init__.py
│       ├── app.py                       FastAPI app factory + middleware
│       ├── config.py                    DashboardSettings (extends backend/settings.py)
│       ├── db.py                        aiosqlite/sqlalchemy session + migrations
│       ├── models.py                    SQLAlchemy models: Run, Target
│       ├── schemas.py                   Pydantic request/response models
│       ├── deps.py                      FastAPI dependencies (db session, run mgr)
│       ├── services/
│       │   ├── __init__.py
│       │   ├── suite_reader.py          Walk reports/, parse suite.json → DashboardSuite
│       │   ├── run_manager.py           Start / stop / replay subprocess runs; PID tracking
│       │   ├── scenario_loader.py       Wraps backend/scenarios/load_library() + axis grouping
│       │   └── artifact_resolver.py     Map suite_dir + scenario_id → file paths; sign URLs
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── pages.py                 HTML routes (dashboard, runs, scenarios, new-run, settings)
│       │   ├── runs.py                  /api/runs CRUD + replay + log stream
│       │   ├── scenarios.py             /api/scenarios browse
│       │   ├── artifacts.py             /artifacts/* range-supported file serving
│       │   └── htmx.py                  HTMX fragment endpoints (status pill, log tail, progress bar)
│       └── templates/
│           ├── base.html                Layout: header + sidebar + main + footer
│           ├── partials/
│           │   ├── header.html
│           │   ├── sidebar.html
│           │   ├── footer.html
│           │   ├── badge_status.html    pass/fail/error pill
│           │   ├── card_metric.html     KPI tile
│           │   ├── table_runs.html
│           │   ├── table_calls.html
│           │   ├── progress_runner.html (HTMX-polled)
│           │   ├── log_tail.html        (HTMX-polled)
│           │   └── toast.html
│           ├── pages/
│           │   ├── dashboard.html
│           │   ├── runs_list.html
│           │   ├── run_detail.html
│           │   ├── call_detail.html
│           │   ├── scenarios_list.html
│           │   ├── scenario_detail.html
│           │   ├── new_run.html
│           │   └── settings.html
│           └── errors/
│               ├── 404.html
│               └── 500.html
├── static/                              NEW
│   ├── css/
│   │   ├── tailwind.css                 Tailwind input
│   │   └── tailwind.build.css           Compiled (committed for offline use)
│   ├── js/
│   │   ├── htmx.min.js                  Local copy, no CDN dep at runtime
│   │   ├── alpine.min.js                Local copy
│   │   └── app.js                       Tiny glue: toast manager, audio sync helpers
│   ├── fonts/
│   │   ├── Inter-*.woff2
│   │   └── JetBrainsMono-*.woff2
│   └── icons/                           Inline-SVG sprite for Lucide icons
├── scripts/
│   └── dashboard.py                     NEW thin CLI: uvicorn launcher
├── deploy/                              NEW
│   ├── Dockerfile                       Python 3.13-slim + Chromium deps; multi-stage
│   ├── docker-compose.yml               Local stack
│   ├── .dockerignore
│   └── README.md                        Deploy notes incl. the auth warning
└── tests/
    └── dashboard/                       NEW
        ├── test_suite_reader.py
        ├── test_run_manager.py
        ├── test_routes_pages.py
        ├── test_routes_runs.py
        └── test_routes_artifacts.py
```

## Backend design

### Database (SQLite via SQLAlchemy async)

`reports/dashboard.db` — single file, auto-migrated on app boot.

**Table `runs`** — every suite that the dashboard knows about (existing on disk and freshly started).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `suite_dir_name` | TEXT UNIQUE | e.g. `suite_20260601T094100Z` |
| `status` | TEXT | `queued` · `running` · `completed` · `failed` · `cancelled` |
| `pid` | INTEGER NULL | subprocess PID while running |
| `started_at` | DATETIME | |
| `finished_at` | DATETIME NULL | |
| `exit_code` | INTEGER NULL | |
| `config_json` | TEXT | `{site, preview_url, biz, scenario_ids, headless, audio_judge, concurrency, replay_of}` |
| `n_total` | INTEGER NULL | denormalised from suite.json once it exists |
| `n_passed` | INTEGER NULL | |
| `n_failed` | INTEGER NULL | |
| `n_errors` | INTEGER NULL | |
| `avg_score` | REAL NULL | |
| `replay_of_id` | INTEGER NULL FK → runs.id | "v2 of run #7" |
| `note` | TEXT | user-editable label |

**Table `targets`** — sites the user has tested, for an autocomplete dropdown in "New run".

| Column | Type |
|--------|------|
| `id` | INTEGER PK |
| `hostname` | TEXT UNIQUE |
| `label` | TEXT NULL |
| `last_used_at` | DATETIME |
| `times_used` | INTEGER DEFAULT 0 |

Migration policy: idempotent `CREATE TABLE IF NOT EXISTS` at boot. No Alembic for v1.

### Suite ingest path (`services/suite_reader.py`)

On app boot **and** on every page request to `/runs`, scan `reports/suite_*/` for any directory that has a `suite.json` not yet in DB and INSERT it with `status=completed`. This makes the dashboard pick up suites started from the CLI without manual import. Cheap — `glob + stat`.

### Subprocess runner (`services/run_manager.py`)

```python
async def start_run(config: RunConfig, *, replay_of: int | None = None) -> Run:
    suite_dir_name = f"suite_{utc_ts()}"
    cmd = [
        sys.executable, "-m", "scripts.run_suite",
        *(["--site", config.site] if config.site else []),
        *(["--max", str(config.max_n)] if config.max_n else []),
        *(["--only", config.only] if config.only else []),
        *(["--headless"] if config.headless else []),
        *(["--no-audio-judge"] if not config.audio_judge else []),
        "--concurrency", str(config.concurrency),
        "--biz", config.biz,
    ]
    log_path = settings.harness_reports_dir / suite_dir_name / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=open(log_path, "ab"), stderr=asyncio.subprocess.STDOUT,
    )
    run = await db.insert_run(suite_dir_name, "running", proc.pid, config, replay_of)
    asyncio.create_task(_watch(run.id, proc, log_path))
    return run
```

- `_watch(run.id, proc, log_path)` awaits `proc.wait()` then loads `suite.json` (if present), updates `n_total / n_passed / ... / avg_score / status / exit_code / finished_at`.
- Kill path: `kill_run(run_id)` looks up PID, sends `SIGTERM`, waits 10 s, falls back to `SIGKILL`. Updates status to `cancelled`.
- **Replay**: `replay_run(run_id)` reads the old run's `config_json`, calls `start_run(...)` with `replay_of=run_id`. The new suite_dir is fresh; the relationship is recorded in `replay_of_id` so the UI can show "v2 of `suite_20260601…`".

### Persisted config inside `suite.json`

To make replay deterministic, we need `scripts/run_suite.py` to write its **effective config** (site, preview_url, biz, max_n, only, headless, audio_judge, concurrency) into `suite.json`. Today `SuiteResult` only stores `business_summary`. Add a `config: dict` field to `SuiteResult` and populate it in `run_suite()`. Tiny, additive change — see §"Companion change to suite.py" below.

### Routes

| Method | Path | Returns | Purpose |
|--------|------|---------|---------|
| GET | `/` | redirect → `/dashboard` | |
| GET | `/dashboard` | HTML | Home: KPI tiles (total runs, last 7d, avg score, scenarios), recent-runs table, big "Start a new run" CTA |
| GET | `/runs` | HTML | Paginated list of all suites; filters: site, status, date range; sort by date / score |
| GET | `/runs/{suite_id}` | HTML | Run detail: KPI strip, coverage-by-axis grid, failure breakdown table, full calls list, "Re-run" button |
| GET | `/runs/{suite_id}/calls/{scenario_id}` | HTML | Per-call drill-down: scenario card + axis chips + transcript + 10-criterion verdict table + inline `<audio>` for full_call.wav + screenshots gallery + raw JSON viewer (collapsible) |
| GET | `/scenarios` | HTML | Library browser with chip filters per axis |
| GET | `/scenarios/{scenario_id}` | HTML | Scenario detail: goal, expected outcome, axes, constraints, "Run only this" button |
| GET | `/new-run` | HTML | Form: site (with autocomplete from `targets`), business summary, scenario picker (multi-select with axis filters), headless toggle, audio-judge toggle, concurrency slider, "Start" button |
| POST | `/new-run` | redirect → `/runs/{suite_id}` | Validates, calls `start_run()`, redirects |
| GET | `/settings` | HTML | Read-only summary of `.env` (with secrets masked): models, base URL, paths |
| GET | `/api/runs` | JSON | List with filters (for future SPA / CLI) |
| GET | `/api/runs/{id}` | JSON | Full run data |
| POST | `/api/runs/{id}/replay` | JSON `{new_run_id}` | Re-run with same config |
| POST | `/api/runs/{id}/cancel` | JSON | Kill running subprocess |
| GET | `/api/runs/{id}/log` | text/plain (last N bytes) | For HTMX polling |
| GET | `/api/scenarios` | JSON | Scenario list |
| GET | `/artifacts/{suite_id}/{path:path}` | file | Serve `full_call.wav`, `bot.webm`, `scenario.wav`, screenshots — with HTTP Range support so `<audio>` can seek |
| GET | `/htmx/status-pill/{run_id}` | HTML fragment | Polled every 2 s while run is active |
| GET | `/htmx/progress/{run_id}` | HTML fragment | "Call 3 of 6 in progress" bar |
| GET | `/htmx/log-tail/{run_id}` | HTML fragment | Last 4 KB of `run.log`, pre-formatted |
| GET | `/healthz` | text "ok" | Liveness probe for cloud runtimes |

### Pydantic schemas (`backend/dashboard/schemas.py`)

```python
class RunConfig(BaseModel):
    site: str | None
    preview_url: str | None
    biz: str
    max_n: int | None
    only: str | None
    scenario_ids: list[str] | None   # selected subset; null = all
    headless: bool = True
    audio_judge: bool = True
    concurrency: int = 1

class RunSummary(BaseModel):
    id: int
    suite_dir_name: str
    status: Literal["queued","running","completed","failed","cancelled"]
    started_at: datetime
    finished_at: datetime | None
    n_total: int | None
    n_passed: int | None
    n_failed: int | None
    avg_score: float | None
    site: str | None
    replay_of_id: int | None
    note: str | None

class RunDetail(RunSummary):
    config: RunConfig
    coverage_by_axis: dict
    failure_breakdown: list[dict]
    calls: list[dict]   # CallResult.to_dict() shape
```

### Companion change to suite.py

Add `config: dict = field(default_factory=dict)` to `SuiteResult` (between `failure_breakdown` and the `to_dict` method) and populate it in `run_suite()`. The dashboard ingest layer reads this to populate `runs.config_json` for replay. Backward-compatible: ingest treats missing `config` as `{}`.

## Frontend design — page-by-page

### `/dashboard` (home)

Top of page row of 4 KPI tiles (`partials/card_metric.html`):
- **Total runs** (lifetime count)
- **Avg overall score** (last 30 d)
- **Pass rate** (last 30 d)
- **Active run** (live; pulses indigo if running)

Below: "Recent runs" table (5 latest) with columns: date, site, n_total, pass/fail/error counts, avg, status pill, [↗ open]. Filter chips above: status (all/passing/failing/running).

Floating right: a **"Start new run"** button (indigo, prominent) → /new-run.

### `/runs`

Full paginated table (20/page). Same columns as above plus a "Re-run" inline icon. Filters in a left rail: site dropdown, status checkboxes, date range picker, score-min slider. Sort by date desc / score asc.

### `/runs/{suite_id}` — the heart of "see reporting with version"

Top:
- Breadcrumb: Runs / suite_20260601T094100Z
- Status pill (live-polled if running)
- "Re-run this suite" indigo button (POSTs to `/api/runs/{id}/replay`, redirects to new run)
- "Cancel" button if running

Then four cards:
1. **Config** card (so the user knows what this version actually ran): site, business summary, scenario subset, headless, audio_judge, concurrency. If `replay_of_id` is set, a "↶ v2 of …" link.
2. **Summary KPIs** (4 metric tiles).
3. **Coverage by axis** — same grid we already build in `compute_coverage()`; render as small per-axis tables in a 3-col grid.
4. **Failure breakdown** — table of failing criterion × scenario rows (from `compute_failure_breakdown`).

Below: full **Calls table** with axis chips per row, click → call-detail page.

If status is `running`: a sticky log-tail panel at the bottom (polled every 2 s via HTMX) shows the last 4 KB of `run.log` in monospace. Progress bar above shows "Call X of N" parsed from log lines.

### `/runs/{suite_id}/calls/{scenario_id}`

The deep-dive view, used to verify QA agent performance:
- Scenario summary card (title, goal, axes).
- Top-right: status pill + overall score gauge (radial, ApexCharts).
- **10-criterion rubric table** with color-coded bars (already styled in `html_report.py`).
- **Audio panel** with the `<audio controls>` for `full_call.wav` and a caption "caller L · bot R". Also offers `scenario.wav` (caller-only) and `bot.webm` (bot-only) in collapsibles.
- **Transcript** — the `qa_messages` array, alternating user/assistant bubbles with timestamps.
- **Screenshots** gallery (01_landed, 02_panel_open, 03_in_call, after, fail) — lightbox via Alpine.
- **Raw JSON viewer** collapsible (`<details>`) with `text_verdict.json`, `audio_verdict.json`, `audio_log.json`.

### `/scenarios` and `/scenarios/{id}` — use case "see the test scenarios"

Library browser:
- Top: 8 axis-filter dropdowns (intent, persona, accent, …); each shows the value counts.
- Grid of scenario cards (3-col). Each card: title, id (mono), 3-4 axis chips, goal (1 line, truncated), and a tiny "Run only this" icon button.
- Click → detail page with full goal, expected outcome, constraints, and a prominent "Run only this scenario" button (creates a single-scenario suite via `--only {id}`).

### `/new-run`

Form, Alpine-driven:
- **Site**: text input with autocomplete from `targets` table. Below it: a small "URL pattern" toggle (`/preview?id=` vs `/?preview=`). Live preview of the resolved URL.
- **Business summary**: textarea, prefilled with the latest used value.
- **Scenarios**: an "all / pick" toggle. If pick, a chip-selector with axis filters above (similar to `/scenarios`). Selected count badge.
- **Options**: headless on/off (default on), audio judge on/off (default on), concurrency slider 1–4.
- **Estimated cost** line (LLM judge calls × scenarios × ~$0.001) — informational.
- **Start** button (indigo). On submit: POST → server validates → spawns subprocess → redirects to `/runs/{suite_id}` where the live log tail takes over.

### `/settings`

Read-only v1. Sections:
- **Models** (text + audio judge, scenario generator, caller, TTS).
- **Endpoints** (QA base URL, OpenRouter URL).
- **Paths** (recordings dir, reports dir).
- **Secrets** — masked (`sk-***********t39f`).
- A line: "to change, edit `.env` and restart the dashboard" — write-from-UI is Phase 2.

## Real-time progress streaming

Use **HTMX polling** for v1 — simpler than SSE, no server-state to leak, fits the long-poll behaviour fine for a 30-min suite. Three polled endpoints per running suite:

- `/htmx/status-pill/{run_id}` — 2 s interval, returns `<span class="pill running">running</span>` etc. When status becomes `completed`/`failed`/`cancelled`, the response includes an `HX-Refresh: true` header to reload the page (now the suite.json exists and we can show real data).
- `/htmx/progress/{run_id}` — 2 s interval, returns a progress bar fragment. Parses the log for lines like `Suite: 6 scenarios → …` and `Running call X of N`.
- `/htmx/log-tail/{run_id}` — 1 s interval, last 4 KB of `run.log`, with ANSI stripping.

HTMX wires them up declaratively:
```html
<div hx-get="/htmx/status-pill/{{ run.id }}" hx-trigger="every 2s" hx-swap="outerHTML"></div>
```

Upgrade to SSE in Phase 2 once we have the basic polling proved.

## Use-case walkthroughs (the 5 things you asked for)

| Use case | UI flow |
|----------|---------|
| **1. See reporting with version** | `/runs` → click a row → `/runs/{id}` → all coverage, failures, calls, audio. `replay_of_id` link shows lineage. |
| **2. Re-run a specific version** | On `/runs/{id}` click "Re-run this suite" → POST `/api/runs/{id}/replay` → redirect to the new run page; old run remains untouched. |
| **3. See test scenarios** | `/scenarios` → filter by axis → click a card → `/scenarios/{id}`. |
| **4. Run the QA agent from dashboard** | `/dashboard` "Start new run" → `/new-run` → fill form → submit → live progress on `/runs/{new_id}`. |
| **5. Provide specific website for testing** | `/new-run` "Site" autocompletes from prior targets but accepts any new hostname. The dashboard threads it through as `--site` to the existing `scripts/run_suite.py` (already supports `--site` from Feature 3). |

## Configuration / environment variables

New variables added to `.env` (and `.env.example`):

| Var | Default | Purpose |
|-----|---------|---------|
| `DASHBOARD_HOST` | `127.0.0.1` | Bind address. Refuses to start on non-loopback unless basic auth env is set. |
| `DASHBOARD_PORT` | `8000` | |
| `DASHBOARD_DB_PATH` | `reports/dashboard.db` | SQLite location |
| `DASHBOARD_ALLOW_PUBLIC` | `false` | Must be `true` AND password set to bind 0.0.0.0 |
| `DASHBOARD_BASIC_AUTH_USER` | `` | Optional Phase 1 hardening |
| `DASHBOARD_BASIC_AUTH_PASSWORD` | `` | Optional Phase 1 hardening |
| `DASHBOARD_LOG_LEVEL` | `INFO` | |
| `DASHBOARD_BASE_PATH` | `` | Reverse-proxy mount path (e.g. `/qa`) |

All read in `backend/dashboard/config.py` via Pydantic settings extending the existing `backend/settings.py:Settings`.

## Cloud-deployable scaffolding

- **`deploy/Dockerfile`** (multi-stage):
  - Stage 1 builder: `python:3.13-slim`, install `uv`, run `uv sync --extra dev --extra report --extra dashboard`, `uv run playwright install --with-deps chromium`.
  - Stage 2 runtime: copy venv + app + Playwright browsers; install system Chromium deps (`libnss3, libatk1.0-0, …`); `CMD ["uv","run","uvicorn","backend.dashboard.app:create_app","--factory","--host","0.0.0.0","--port","8000"]`.
- **`deploy/docker-compose.yml`**: single service, mounts `./reports` and `./recordings` as volumes, exposes 8000.
- **No hardcoded paths** anywhere — every path goes through `backend.dashboard.config.get_settings()`.
- **Logging**: structured JSON when `DASHBOARD_LOG_LEVEL` is set; loguru handles it.
- **Liveness**: `/healthz` returns `ok` and checks the DB connection works.
- **`pyproject.toml`** new `[project.optional-dependencies]` group `dashboard` with the new deps.

### The auth tension — guardrails

- `create_app()` raises on startup if `DASHBOARD_HOST != 127.0.0.1` AND (`DASHBOARD_ALLOW_PUBLIC != "true"` OR `DASHBOARD_BASIC_AUTH_PASSWORD == ""`).
- README in `deploy/` documents this in **bold**: "Do not expose this port to the public internet without enabling basic auth at minimum. Multi-user auth is a Phase 2 deliverable."

## Reuse, not rewrite

| Existing | How the dashboard reuses it |
|----------|-----------------------------|
| `scripts/run_suite.py` | Subprocess target — already takes `--site`, `--max`, `--only`, `--headless`, `--audio-judge`, `--concurrency`, `--biz` |
| `backend/scenarios/load_library()` | Powers `/scenarios` and the picker on `/new-run` |
| `backend/orchestrator/suite.py:SuiteResult` | The dashboard ingest layer reads `suite.json` (already serialised) directly |
| `backend/report/coverage.py:compute_coverage`, `compute_failure_breakdown` | Already populated into `suite.json`; UI just renders |
| `backend/report/html_report.py` styling | Template tokens (badge colors, bar component) cribbed verbatim |
| `backend/url_builder.py:build_preview_url` | New-run form uses it for the live preview line |
| `backend/audio_mix.py:build_full_call` | Already produces `full_call.wav` per call; dashboard streams it |
| `backend/settings.py:Settings` | DashboardSettings extends, doesn't replace |
| `pyproject.toml [report]` extra | New `[dashboard]` extra mirrors the pattern |

## Implementation phases

To ship in increments rather than one big bang:

### Phase A — Skeleton (1 day)
- New `backend/dashboard/` package; FastAPI app factory; base.html with header/sidebar/footer; Tailwind via Play CDN.
- Routes: `/dashboard` (just KPIs), `/runs` (list), `/runs/{id}` (read-only, no replay yet).
- Suite ingest from disk; SQLite schema + bootstrap.
- `static/` with Inter font + HTMX/Alpine local copies.

### Phase B — Run from the dashboard (1 day)
- `/new-run` form + `RunConfig` validation.
- `services/run_manager.py` subprocess spawner.
- Companion `SuiteResult.config` field in `scripts/run_suite.py` so replay later has data.
- Polled status pill + log tail.

### Phase C — Polish + replay + scenarios (1 day)
- `POST /api/runs/{id}/replay`.
- `/scenarios` library browser + `/scenarios/{id}` detail.
- Per-call deep-dive page with audio + transcript + JSON viewer.
- Charts (ApexCharts radial gauge for overall score).
- Tailwind switched to standalone CLI build (commit the compiled CSS).

### Phase D — Cloud-ready (0.5 day)
- Dockerfile + compose; `.dockerignore`.
- Liveness probe; structured logs.
- Bind-guard logic in `create_app()`.
- Deploy README with the auth warning.

### Phase E — Tests (0.5 day)
- `pytest-asyncio` route tests via `httpx.AsyncClient(app=...)`.
- A mocked run_manager subprocess (don't actually launch Chromium in tests).
- Snapshot tests for HTMX fragments.

Total: ~4 working days.

## Verification

End-to-end checklist after Phase C:

```powershell
# 1. Launch dev server
uv run python -m scripts.dashboard
# → http://127.0.0.1:8000/dashboard

# 2. Pre-existing CLI-produced suites should appear under /runs immediately.

# 3. Start a fresh run from the dashboard
#    /new-run → site = webwaala.com, scenarios = pick 3, headless = true → Start
# Expected: redirected to /runs/{new_id}; log tail streams; progress bar updates;
# when the subprocess exits, the page auto-refreshes with full suite.json data.

# 4. Re-run that suite
#    /runs/{new_id} → "Re-run this suite"
# Expected: new run row created; "v2 of …" link visible on both old and new detail pages.

# 5. Drill into a call
#    /runs/{new_id}/calls/{scenario_id}
# Expected: full_call.wav plays inline; criterion table styled; transcript renders.

# 6. Browse scenarios
#    /scenarios → filter by intent="pricing-inquiry" → 3 scenarios shown
#    Click "Run only this" on one → new single-scenario run starts.

# 7. Settings page shows masked secrets; reports/dashboard.db exists.
```

Test runs from `tests/dashboard/`:

```powershell
uv run pytest tests/dashboard -q
```

Should: pass; not touch the real reports/ directory (use `tmp_path` fixtures).

## Out of scope (Phase 2+)

- Auth (basic auth env + multi-user with sessions/roles).
- Editing `.env` from the dashboard.
- Trends view (avg score over time, per-scenario regression chart).
- Dark mode toggle (palette designed for it; just no UI toggle in v1).
- Webhook on suite completion (Slack, email).
- Server-sent events / WebSockets in place of HTMX polling.
- Replay with config overrides ("re-run but change `--concurrency`").
- Inline scenario editor.
- Mobile/responsive polish below 768 px (v1 is desktop-first).
- Localisation.

## Open risks / tradeoffs

1. **Subprocess output buffering on Windows.** Python defaults to line-buffered stdout. We pass `stdout=open(log_path, "ab")` which buffers; verify with a real run that the log tails responsively. Fallback: `PYTHONUNBUFFERED=1` in the subprocess env.
2. **Concurrent runs on a single dev box.** Playwright + Daily.co are heavy; the default concurrency stays at 1 even in the dashboard. Show a warning if a second start is attempted while one is `running`.
3. **`full_call.wav` size on cloud.** A 30-call suite produces ~150 MB of stereo WAV. Document the storage growth. Phase 2: auto-compress to opus, keep stereo channel layout.
4. **Audio range serving** must include `Accept-Ranges: bytes` so HTML5 `<audio>` can seek; covered by FastAPI's `FileResponse` but explicit guard helps.
5. **The auth tension** above — if anyone misreads the README and binds publicly without the password, the dashboard is wide open and can spawn shell commands (via the run-manager subprocess shape). The bind-guard in `create_app()` is the safety net; review it carefully in code review.
6. **DB locks.** SQLite + aiosqlite is fine for single-user; if we ever go multi-worker uvicorn, we need WAL mode (`PRAGMA journal_mode=WAL`).
7. **Tailwind Play CDN is dev-only.** Production must use the compiled `tailwind.build.css`; ship a script in `deploy/` to rebuild it.
