# BizFinder Voice QA — Implementation Plan (Phase 1)

**Approach:** Browser-driven (Playwright) end-to-end caller bot against the real
widget, with OpenRouter powering scenario generation, the caller persona, and
the text judge. Audio judging is in-browser captured (no `bot/app.py` patch
required for Phase 1).

---

## ⚠ 2026-05-29 — Architectural Pivot: Pre-rendered WAV (not CDP+WebAudio)

**Discovered during Step 3 implementation:**

Daily.co's WebRTC setup creates two RTCPeerConnections. PC#0 (which holds the
audio sender transceiver) is closed almost immediately after call setup —
inspection shows it transitions to `signalingState=closed` within ~10s. PC#1
is live but its audio transceiver is `recvonly` (it only receives the bot's
audio). Daily's outbound publish path then depends on its own signaling to
renegotiate when the user starts speaking, and the SDP renegotiation has to go
through Daily's WebSocket signaling — not something we can fake from the page.

`navigator.mediaDevices.getUserMedia` override works (we successfully return
our `MediaStreamAudioDestinationNode.stream`), and we can `replaceTrack` on the
recvonly sender + set `transceiver.direction='sendrecv'`, but without a
renegotiation round-trip nothing actually goes out on the wire. The user-side
VU meter stays flat after injection, confirming Daily isn't transmitting.

**Pivot:** Use Chromium's `--use-file-for-fake-audio-capture=path/to/file.wav`
instead. Chrome treats the WAV file as a synthetic microphone device. Daily's
unmodified `getUserMedia({audio:true})` returns a normal audio track whose data
is sourced from the file. WebRTC's standard publish path works without any
shim.

**Trade-off:** the audio file is fixed at browser-launch time. We can't
react to the bot's reply mid-call with a freshly-generated utterance. Phase 1
absorbs this by pre-rendering the entire scenario (all user turns + inter-turn
pauses) into one WAV file per scenario before launching the browser. The
caller persona is still LLM-driven (OpenRouter generates the turn texts and
their pacing) — it just runs once per scenario, not turn-by-turn.

**What this affects in §4:**
- Step 3's "dynamic per-turn injection" → replaced by "pre-rendered scenario WAV"
- Step 6 ("dynamic caller persona over OpenRouter") becomes: generate the full
  scenario script before each call, render to WAV, launch Chrome against it.
  Bot interrupt-handling is still testable because the WAV includes deliberate
  early-talk segments; we just can't react to a bot utterance we didn't expect.

**What this enables (kept):** the in-page MediaRecorder capture of the bot's
remote audio track (Step 4) still works as planned and gives us a per-call WAV
of what the bot actually said.

## 1. Goal & Non-goals

**Goal.** A reproducible harness that:
1. Generates a scenario library (intents, edge cases, adversarial prompts).
2. Drives the BizFinder voice widget through a headed Chromium browser via Playwright.
3. Holds a multi-turn voice conversation by injecting dynamic TTS into the fake mic per turn.
4. Captures both directions of audio + the QA Read API transcript/metrics.
5. Scores each call against the 10-criterion rubric using OpenRouter.
6. Emits PDF + dashboard reports.

**Non-goals (Phase 1).**
- No GPU-resident audio judge (Qwen3-Omni). Deferred to Phase 2 once SSH'd
  audio capture + GPU slot are in place. Phase 1 uses an OpenRouter-hosted
  multimodal model (Gemini 2.0 Flash or GPT-4o-audio via OR) on the
  browser-captured WebRTC audio as a lower-fidelity stand-in.
- No `bot/app.py` patch. No SFTP to analytics VPS for audio. Phase 2 work.
- No production scheduling. Run locally on Windows dev box.

---

## 2. Architecture

```
                ┌──────────────────────────────────────────┐
                │  Scenario Library (JSON, generated once) │◀── OpenRouter
                └────────────────┬─────────────────────────┘   (DeepSeek/Claude)
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Run Orchestrator (Python)                     │
│                                                                    │
│  per scenario:                                                     │
│    1. Spawn Playwright (Chromium, --use-fake-ui-for-media-stream)  │
│    2. Navigate to https://bizfinder.ai/?preview=…fftechsaas.xyz    │
│       (or qa-judge tenant once provisioned)                        │
│    3. Click "Talk to us"                                           │
│    4. Wait for Daily.co room join + bot greeting                   │
│    5. Loop until end condition:                                    │
│         a. Capture last bot utterance (in-page MediaRecorder on    │
│            the remote audio track)                                 │
│         b. STT it (Whisper API)                                    │
│         c. Caller persona (OpenRouter) → next user utterance       │
│         d. Caller TTS (ElevenLabs/OpenAI) → PCM                    │
│         e. Inject PCM via CDP+Web Audio into fake mic              │
│    6. Hang up                                                      │
│    7. Pull QA Read API: GET /api/qa/conversations/<sessionId>      │
│    8. Persist artifacts (audio.wav, transcript.json, metrics.json) │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                ┌────────────────────────────────────────┐
                │  Judge (OpenRouter, text + audio)      │
                │  10-criterion rubric → scores + reason │
                └────────────────┬───────────────────────┘
                                 │
                                 ▼
                ┌────────────────────────────────────────┐
                │  Report: PDF (WeasyPrint) + Streamlit  │
                └────────────────────────────────────────┘
```

---

## 3. Components

| # | Component | Tech | What it does |
|---|-----------|------|--------------|
| 1 | `backend/scenarios/` | OpenRouter (DeepSeek V3 / Claude Haiku) + Pydantic | Generate + validate scenario JSON across 8 axes (intent, persona, accent, interrupt, noise, complexity, language, adversarial) |
| 2 | `backend/qa_api/` | `httpx` async, X-QA-Secret | Typed client for `/api/qa/health`, `/conversations`, `/conversations/<id>`. Rate-limited to 1 req/sec. Pydantic mirrors of `Conversation`/`Message`/`metrics[]` |
| 3 | `backend/browser/` | Playwright (Python, async) + CDP | Launch Chromium with mic/cam fake flags. Drive widget. Inject PCM via `AudioWorklet` into a `MediaStreamAudioDestinationNode` that overrides `getUserMedia` |
| 4 | `backend/caller/` | OpenRouter | Persona LLM. Reads scenario + bot transcript so far, produces next utterance |
| 5 | `backend/tts/` | ElevenLabs or OpenAI TTS API | Synthesize caller utterances. Pluggable interface; local Piper as offline fallback |
| 6 | `backend/stt/` | OpenAI Whisper API | Transcribe captured bot audio in-browser if QA API hasn't persisted the turn yet (race) |
| 7 | `backend/capture/` | In-page `MediaRecorder` over remote track + `page.evaluate` exfil | Save full-call WAV + per-turn WAV (split on VAD or on injection boundaries) |
| 8 | `backend/judge/` | OpenRouter (DeepSeek text + Gemini 2.0 Flash audio) | 10-criterion scoring. Returns `{criterion: {score, evidence, rationale}}` |
| 9 | `backend/report/` | WeasyPrint + Streamlit | PDF per run, dashboard for suites |
| 10 | `backend/orchestrator/` | LangGraph (lightweight; not full CrewAI yet) | State machine per call; retries; parallelism cap |

---

## 4. Phased Delivery

Each step has a verifiable completion criterion. Same pattern as the addendum's §7.

| # | Step | Done when |
|---|------|-----------|
| **0** | Project skeleton: `pyproject.toml`, `uv` env, `.env.example`, git init, ruff config, pre-commit | `uv run pytest` passes empty suite; `ruff check` clean |
| **1** | QA Read API client + smoke test | `verify_setup.py` hits all 3 endpoints, validates against Pydantic, auth-gate test passes |
| **2** | Bare Playwright run: open site, click Talk to us, accept mic prompt, screenshot the "in-call" state | Screenshot artifact saved; no errors in console |
| **3** | Fake-mic injection PoC: inject a 5-sec sine wave via CDP+Web Audio into the call, verify bot transcribes it as "beep"-like input | QA API shows a `user` message for the injected turn |
| **4** | Bot audio capture PoC: in-page `MediaRecorder` on remote track → exfil → WAV on disk that plays back the bot greeting | `greeting.wav` audible; SHA matches a re-fetch |
| **5** | One end-to-end scripted call: 3 hardcoded user turns, ElevenLabs TTS, capture both sides, pull QA transcript | `call_<sessionId>/{user_*.wav, bot_*.wav, transcript.json, metrics.json}` |
| **6** | Dynamic caller persona over OpenRouter | A call where each user turn is generated based on the bot's previous answer; conversation reaches its scenario goal or fail-state |
| **7** | Scenario generator + library (8 axes, ~50 scenarios for v1) | `scenarios/library/*.json` committed; Pydantic-valid |
| **8** | Text judge (10 criteria) over OpenRouter; 50-call run | `reports/run_<id>.json` with per-criterion scores; cost log shows ≤ $1 |
| **9** | Audio judge (Gemini 2.0 Flash via OpenRouter) on captured WAV | Pronunciation issues like "Rakesh" → "Ra-keesh" flagged in `criterion_audio_quality.evidence` |
| **10** | Streamlit dashboard + WeasyPrint PDF | Operator can run a suite + view report in ≤ 3 clicks |
| **11** | Human-labelled cross-validation (50 calls) | `docs/judge_validation_v1.md` shows ≥ 80% agreement |

---

## 5. Open Blockers (BizFinder side)

| Blocker | Owner | Blocks step | Workaround |
|---------|-------|-------------|------------|
| `qa-judge` siteId provisioned | BizFinder admin | 7 onwards (clean suite runs) | Use `fftechsaas.xyz` preview for steps 2–6 |
| Confirm QA flag mechanism (header vs Daily room metadata) | BizFinder dev | 5+ (gating audio capture on bot side, Phase 2) | N/A for Phase 1 (we capture in-browser) |
| OpenRouter API key (with budget) | You | Step 6+ | — |
| ElevenLabs or OpenAI TTS key | You | Step 5+ | Piper local fallback wired in step 5 |

---

## 6. Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| CDP+WebAudio fake-mic injection too flaky across Chromium versions | Med | Pin Chromium via Playwright; fallback to scripted-WAV mode for CI smoke |
| In-browser captured TTS audio is post-Opus-encoded — audio judge weaker on "Ra-keesh" class bugs | High | Document Phase 1 audio-judge as best-effort; Phase 2 picks up real PCM via SFTP path |
| Daily.co 15-min room expiry caps scenarios | Med | Cap scenarios at 12 min (per addendum §5); long-context = Phase 2 |
| Bot occupancy: `/health.available_slots === 0` blocks runs | Low | Poll `/health` before dial; back off |
| Test calls land in `fftechsaas.xyz` conversation history (pre-qa-judge provisioning) | Med | Run smallest possible volume on that tenant until `qa-judge` lands; flag any noise to Matt-equivalent at BizFinder |
| OpenRouter rate limits on heavy suites | Low | Concurrency cap 5; exponential backoff already in OR SDK |

---

## 7. Repo Layout

```
F:\Bizfinder\
├── PLAN.md                       # this file
├── Voice Judge-QA - Final Handover.pdf
├── voice_judge_qa_phase1_addendum_v2_rev.docx
├── pyproject.toml                # uv / hatchling
├── .env.example
├── .gitignore                    # excludes .env, recordings/, reports/
├── README.md
├── backend/
│   ├── __init__.py
│   ├── qa_api/                   # QA Read API client + Pydantic models
│   ├── browser/                  # Playwright driver + CDP injection
│   ├── caller/                   # Persona LLM
│   ├── tts/                      # ElevenLabs/OpenAI/Piper adapters
│   ├── stt/                      # Whisper adapter
│   ├── capture/                  # In-page MediaRecorder exfil
│   ├── scenarios/                # generator + library
│   │   └── library/*.json
│   ├── judge/                    # 10-criterion rubric + OR adapters
│   ├── orchestrator/             # LangGraph state machine
│   └── report/                   # WeasyPrint + Streamlit
├── tests/
│   ├── unit/
│   └── integration/              # hits live QA API, marked slow
├── scripts/
│   ├── verify_setup.py
│   └── qa-smoke-test.sh
└── recordings/                   # gitignored
```

---

## 8. Cost Projection (Phase 1)

| Item | Per call | At 100 calls |
|------|----------|--------------|
| OpenRouter — caller persona | ~$0.001 | $0.10 |
| OpenRouter — text judge | ~$0.002 | $0.20 |
| OpenRouter — audio judge (Gemini 2.0 Flash) | ~$0.005 | $0.50 |
| ElevenLabs TTS (~30s caller voice) | ~$0.015 | $1.50 |
| Whisper STT (~60s bot audio) | ~$0.006 | $0.60 |
| **Total** | **~$0.029** | **~$2.90** |

Higher than addendum's $0.005/call estimate because ElevenLabs (premium TTS)
+ Whisper API replace the addendum's local ChatterboxTTS + bot-internal STT.
Swap to local Piper (TTS) drops to ~$0.013/call.

---

## 9. What I'll do next (on your go-ahead)

1. Initialize the project skeleton (step 0).
2. Wire the QA Read API client + smoke test (step 1) — verifies your handover credentials work from this machine end-to-end.
3. Stand up the bare Playwright run (step 2) — proves the widget click flow.

Steps 0–2 are ~half a day and produce a green smoke baseline before any
LLM/TTS spend.
