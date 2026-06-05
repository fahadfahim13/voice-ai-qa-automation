# BizFinder Voice QA

Browser-driven QA harness for the BizFinder.ai voice AI widget. Drives the real
"Talk to us" button in a headed Chromium via Playwright, injects dynamic TTS
into the fake microphone per turn, captures both directions of audio, pulls the
QA Read API transcript + metrics, and scores each call against a 10-criterion
rubric using OpenRouter.

See [PLAN.md](./PLAN.md) for the full architecture and phased delivery.

## Quick start

```powershell
# 1. Create env from template, fill secrets
copy .env.example .env

# 2. Install deps (Python 3.11–3.13)
uv sync --extra dev

# 3. Install Chromium for Playwright
uv run playwright install chromium

# 4. Smoke-test the QA Read API
uv run python -m scripts.verify_setup
```

## Layout

| Path | What lives here |
|------|-----------------|
| `backend/qa_api/` | Typed client for the QA Read API |
| `backend/browser/` | Playwright driver + CDP fake-mic injection |
| `backend/caller/` | OpenRouter caller persona |
| `backend/tts/` | OpenAI / ElevenLabs / Piper adapters |
| `backend/stt/` | Whisper adapter |
| `backend/capture/` | In-page audio exfil |
| `backend/scenarios/` | Generator + library |
| `backend/judge/` | 10-criterion rubric |
| `backend/orchestrator/` | Per-call state machine |
| `backend/report/` | Streamlit + WeasyPrint |
| `scripts/` | One-shot CLIs (verify_setup, run_suite) |
| `tests/` | unit + integration (marked `live` / `browser`) |
| `recordings/` | Captured audio (gitignored) |
| `reports/` | Run artifacts (gitignored) |

## CLI cheat-sheet

```powershell
# 1. Smoke-test the QA Read API
uv run python -m scripts.verify_setup

# 2. Single bare-flow open: click Talk to us -> CALL, screenshot, hang up
uv run python -m scripts.bare_widget_open

# 3. Pre-rendered WAV mic injection (Step 3 PoC)
uv run python -m scripts.inject_mic_poc

# 4. Bot-audio capture PoC (writes bot.webm)
uv run python -m scripts.capture_bot_audio_poc

# 5. Multi-turn scripted call (artifacts under recordings/call_*)
uv run python -m scripts.run_call --turn "..." --turn "..."

# 6. Persona-driven call (needs OPENROUTER_API_KEY)
uv run python -m scripts.run_persona_call -p "Curious founder" -g "Check iOS support"

# 7. Build the scenario library (16 baseline; --expand adds LLM scenarios)
uv run python -m scripts.build_scenarios [--expand]

# 8. Full suite: persona -> call -> text judge -> audio judge -> HTML/PDF report
uv run python -m scripts.run_suite --max 5 --headless

# 9. Operator dashboard
uv run --extra report streamlit run backend/report/dashboard.py
```

## Dashboard

Operator dashboard (Streamlit, multipage). Architecture + how to extend it:
[docs/DASHBOARD.md](./docs/DASHBOARD.md).

```powershell
uv run --extra report streamlit run backend/report/dashboard.py
```

**Pages:** Overview (suite picker + headline metrics + in-UI smoke test),
Reports (runs grouped by version + re-run a pinned version), Scenarios (library),
Run suite (trigger a run + live status), Re-run.

**Auth gate.** The whole app sits behind a shared password read from
`DASHBOARD_PASSWORD`:
- **set** → a password prompt gates every page (Coolify injects it on deploy).
- **unset** → the app loads with a ⚠ "local use only" banner (local dev isn't blocked).

**Smoke test.** Verify the QA Read API from the Overview page (**🩺 Run smoke
test**) or the CLI — checks health, conversation list, and that a wrong secret is
rejected (**AUTH GATE OK**):

```powershell
uv run python -m scripts.qa_smoke_test   # exits non-zero on failure
```

## Status (Phase 1 — all 11 steps implemented)

| Step | What | Status |
|------|------|--------|
| 0 | Project skeleton + tooling | ✅ |
| 1 | QA Read API client + smoke test (live verified) | ✅ |
| 2 | Playwright bare-flow run (click Talk to us → CALL) | ✅ |
| 3 | Pre-rendered WAV mic injection — live verified user message reached bot | ✅ (pivot: see PLAN.md) |
| 4 | Bot audio capture via MediaRecorder (webm/opus) | ✅ |
| 5 | Scripted multi-turn end-to-end call | ✅ |
| 6 | OpenRouter caller persona | ✅ impl. (needs OPENROUTER_API_KEY to run live) |
| 7 | Scenario library (16 baseline scenarios across 8 axes) | ✅ |
| 8 | Text judge (10-criterion rubric) | ✅ impl. (needs OPENROUTER_API_KEY) |
| 9 | Audio judge over OpenRouter (Gemini 2.0 Flash via input_audio) | ✅ impl. (needs OPENROUTER_API_KEY) |
| 10 | Streamlit dashboard + WeasyPrint PDF | ✅ |

## What you need to set to run end-to-end

| Variable | Required for | Where |
|----------|--------------|-------|
| `QA_SHARED_SECRET` | QA Read API | already pre-filled in `.env` |
| `OPENROUTER_API_KEY` | Steps 6–9 (persona, judge) | **needs your key** |
| `OPENAI_API_KEY` | Higher-quality caller TTS + Whisper for local STT checks. Without it we fall back to `edge-tts` (free). | optional |

`qa-judge` siteId is still **PENDING** on BizFinder admin. Until provisioned,
the harness targets `fftechsaas.xyz-preview` (resolved automatically from
`QA_PREVIEW_URL`).

## Phase 1 → Phase 2 deferrals (see PLAN.md)

- Bot-side `bot/app.py` patch + SFTP audio path (lossless raw PCM)
- GPU-resident Qwen3-Omni-30B audio judge on A6000
- Dynamic intra-call caller persona (currently scenario script is pre-rendered)
