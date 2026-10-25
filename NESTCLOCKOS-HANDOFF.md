# NestClockOS — COMPLETE HANDOFF

For Claude Code (or any coding agent) working inside the local project folder, with NO access to the
design conversation that produced this project. This replaces the earlier short handoff.
Everything here was either built and verified in that conversation, decided with the owner (Keylhan),
or is a clearly marked proposal. Tags used throughout:

- **[VERIFIED]** observed working on the owner's machine, or checked against current docs/tests.
- **[DECIDED]** a choice the owner made or explicitly accepted. Do not silently reverse these.
- **[PROPOSED]** my recommendation, not yet agreed. Challenge it if the evidence says so.
- **[UNVERIFIED]** from memory or a secondary source. Check current docs before relying on it.

## How to read this (suggested order)
1. Part A (what and why) and Part B (architecture) — 10 minutes, mandatory.
2. Part G (do / don't / not worth doing) — mandatory before touching code.
3. Part E (the roadmap, in detail) for the task you are about to do, plus Part H (how to test it).
4. The rest as reference: C (decisions), D (external service facts), F (Phase 5+), I (environment), J (open questions).

## Table of contents
A. Product vision, goals, non-goals, principles
B. System architecture, protocol, persistence, file-by-file state of the code
C. Decision log with rationale
D. External services: verified facts, limits, traps (Spotify, Mistral/Voxtral, Laya, Hugging Face)
E. Roadmap in detail (finish 4a, 4b, 4c, 4d, 4e)
F. Phase 5 and beyond
G. Do / Don't / Not worth doing
H. Testing strategy and acceptance criteria
I. Environment, run commands, operational gotchas
J. Open questions to ask the owner (do not guess these)
Appendix 1. Router (Laya) history and numbers
Appendix 2. Speech-to-text observations (real data)
Appendix 3. Design system (Figma) tokens and screens
Appendix 4. File inventory: what each file is, and whether to read, modify, or delete it

## FIRST HOUR CHECKLIST (do these before any feature work)
1. Read `CLAUDE.md`, then Parts A, B, G of this file, then the docs listed in E0.1.
2. `git status` / initialise git, add the `.gitignore` from B4, commit a baseline (secrets and recordings excluded).
3. Verify local file versions: `python stt_session.py -h` must list six commands (`devices, meter, talk, script, compare, replay`); `grep -n "prepare_save_dir" stt_session.py` must match, else re-apply the three fixes in B5.4.
4. Run the existing checks: `python test_override.py`; syntax-check the page script with `node --check` on the extracted `<script>`.
5. Confirm the router checkpoint: download the private Hugging Face copy once to a local folder (the owner provides the token; never in chat), load it using the pattern in `phase0_5/eval_finetuned.py`, re-run the held-out evaluation and record the direction split next to run 3's numbers (Appendix 1).
6. Read `llm_speed_test.py` and `llm_timings.csv` (their purpose is not documented here).
7. Then start E0.4 (alarms must ring until dismissed), E0.5 (one-shot alarms), then E1.

---------------------------------------------------------------------------------------------------
# A. PRODUCT VISION

## A1. What this is
A custom **bilingual (French / English) smart clock** that replaces a Lenovo Smart Clock (the old
Google-Assistant bedside display: small, dated, screen burn-in, few features). It is also a
**learning project** for the owner (AI/ML engineering student): small local models, cloud APIs, OS-level
work, web apps, integrations and tooling. Quality of engineering and of the learning matter as much as
the gadget.

Target feature set (the owner's own list, in priority order):
1. A glanceable, polished clock/date display, French and English shown together, designed to be
   readable across a room and pleasant at night. Needs an anti-burn-in strategy.
2. **Alarms and timers that are reliable** (they must fire even if the browser is closed or the
   network is down).
3. **Spotify**: the clock appears as a Spotify Connect device, shows what is playing, and has
   play/pause/next/previous/volume.
4. **A voice assistant in French and English**: a custom, changeable wake word; fast local handling of the
   common commands (alarm, timer, music, weather); a cloud LLM only for open-ended questions;
   spoken replies; on-screen listening/thinking/speaking states.
5. Weather on the home screen and a detailed weather screen.
6. A Settings screen (brightness/auto-dim, language, wake word, volume, connections).

## A2. Non-goals (decided)
- Rooting/flashing the Lenovo clock. **[DECIDED]** Dead end, too limited.
- Single-board computers (Raspberry Pi etc.). **[DECIDED]** Prices are absurd in the owner's market (a Pi 5 8GB was ~250 EUR, 16GB ~360 EUR).
- A native Android app. **[DECIDED]** The UI is a web page in a kiosk browser; the logic is a Python service.
- Running speech-to-text or an LLM on the device CPU. **[DECIDED]** Too slow to feel reactive. Cloud (Mistral) does STT/LLM/TTS. Only the tiny Laya router runs locally.
- Google Assistant / any Google voice stack.
- Multi-user accounts, a cloud backend of our own, a mobile companion app.
- Smart-home control (lights, etc.). Possible far-future backlog only.

## A3. Principles (apply to every decision)
1. **Reliability beats features.** An alarm that fails to ring is a product failure. Alarms/timers/audio live in the Python companion, not in the page.
2. **Local-first for the fast, common path; cloud for the heavy, rare path.** Common commands should not need an LLM round trip.
3. **Safe by default.** Anything that deletes or cancels state needs confirmation. Wrongly acting on chatter is worse than asking again.
4. **Honest UI.** Never show fake or placeholder data (weather, now-playing, alarms). Empty states are shown honestly.
5. **Bilingual by default**, as a permanent display convention (not a locale switch). See Appendix 3.
6. **Simple tools.** Plain HTML/CSS/JS with no build step. Python, standard library where possible. No framework unless a concrete need appears.
7. **Prove the plumbing before building UI around it**, and **measure before tuning**. Every phase so far started with a throwaway test harness (batch scorer, smoke test, mic meter), and that discipline paid off repeatedly.
8. **Numbers, not vibes.** Define acceptance criteria before a run, report actual numbers against them, then stop for a human decision.
9. **Isolate anything platform-specific** (wake lock, audio device selection, kiosk launch, brightness). The final hardware/OS is not chosen yet.

---------------------------------------------------------------------------------------------------
# B. SYSTEM ARCHITECTURE

## B1. Big picture (current + target)

```
 microphone ──► [capture: ring buffer + endpointing] ──► Voxtral STT (Mistral cloud)
   (4a done as push-to-talk;                                   │ transcript
    4d = wake word + ring buffer)                              ▼
                                              [language handling]  (open question, see E2.4)
                                                               │
                                                               ▼
                         Laya router (fine-tuned multilingual, LOCAL, CPU) + deterministic override
                                   │ category ∈ {alarm, timer, music, weather, fallback} + confidence
                    ┌──────────────┼───────────────────────────────┬─────────────────────────┐
                    ▼              ▼                               ▼                         ▼
              alarm/timer      music (Spotify Web API       weather (4c)             fallback / low confidence
              deterministic    via companion tokens)        Open-Meteo-style API     ──► Mistral LLM (4c)
              slot parser +    play/pause/next/vol          + display                     │
              companion store                                                              ▼
                    └──────────────┴───────────────┬───────────────────────────────  spoken reply
                                                   ▼                                 (Voxtral TTS, 4c)
                                  WebSocket events ──► kiosk page (listening/thinking/speaking, 4e)

 kiosk page (index.html, Chromium --kiosk)  ◄──── ws://localhost:8765 ────►  companion.py (Python, asyncio)
   UI, Wake Lock API (screen),                                                alarms/timers + scheduler, audio out,
   Spotify Web Playback SDK (the                                              wake lock (system), Spotify auth/tokens,
   Connect device lives in the page)                                          [voice pipeline goes here]
```

Two facts shape everything:
- The **companion owns the microphone, audio output, alarms/timers state and Spotify tokens.** The page is a display + input client that can be reloaded or closed without losing state. **[DECIDED]**
- The **Spotify playback device lives in the browser page** (Web Playback SDK), because that is Spotify's supported route. The companion controls it from outside through the Web API using the page's `device_id`. **[DECIDED]** (see Part D for why not librespot)

## B2. Processes, ports, URLs
| thing | where | notes |
|---|---|---|
| Static page server | `python -m http.server 8000` | open **http://127.0.0.1:8000** (NOT localhost: Spotify login returns to this origin) |
| Companion | `python companion.py` | WebSocket **ws://localhost:8765**, binds localhost only (no auth) |
| Spotify login callback | `127.0.0.1:8888/callback` | listener exists ONLY during a login attempt, then closes |
| Kiosk browser | `chromium --kiosk --ozone-platform-hint=auto http://127.0.0.1:8000` | the Wayland flag matters, see D4 |

## B3. WebSocket protocol (companion.py ⇄ index.html), current and complete
Browser → companion (JSON, `action` field):
| action | fields | effect |
|---|---|---|
| `set_alarm` | `hour` 0-23, `minute`, `days` [0..6] (0=Monday, Python `tm_wday`), `label` | creates an enabled recurring alarm (days default: all 7) |
| `cancel_alarm` | `id` | deletes it |
| `toggle_alarm` | `id` | flips `enabled` |
| `start_timer` | `seconds`, `label` | creates a timer (many allowed) |
| `cancel_timer` | `id` | deletes it |
| `dismiss` | – | stops audio (`sd.stop()`) |
| `spotify_login` | – | companion starts the callback listener, replies `spotify_auth_url` |
| `spotify_token` | – | replies `spotify_token` (fresh access token, refreshing if needed; `null` if not connected) |

Companion → browser (`type` field): `state` {alarms[], timers[]} (sent on connect and after every change);
`alarm_fired` {alarm}; `timer_fired` {timer}; `spotify_status` {connected}; `spotify_auth_url` {url};
`spotify_token` {access_token|null}; `spotify_error` {message}.

Objects: alarm `{id, hour, minute, days[], label, enabled}`; timer `{id, duration, ends_at(epoch s), label}`.

**Known protocol gaps to fill in Phase 4 (not yet implemented):**
- The page never tells the companion its Spotify `device_id` (needed for Web API control). Add `spotify_device {device_id}` sent from the SDK `ready` event (and cleared on `not_ready`).
- No `voice_*` messages exist yet (see E5 for the proposed set).
- No `once` (one-shot) alarm concept and no snooze (see E2.5 and F).

## B4. Persistence and secrets
| file | content | notes |
|---|---|---|
| `companion_state.json` | alarms + timers | written on every change; next to `companion.py`; no concurrent-write protection (single writer is fine) |
| `spotify_tokens.json` | access/refresh token, expiry, granted scope | mode 0600; **never commit**; treat the refresh token as a password |
| env `MISTRAL_API_KEY` | Mistral API key | env var only; never print or commit |
| Hugging Face token | only to download the private router checkpoint | after the first download, cache the model locally so the device does not need a token at runtime |

Recommended `.gitignore`: `spotify_tokens.json companion_state.json __pycache__/ rec*/ *.wav .env voice_log.jsonl`

## B5. Current code, file by file (state at handoff)

### B5.1 `index.html` — the kiosk UI (single file, no build, ~47 KB)
Screens (each a `.screen` div; `showScreen(id)` switches): `clockScreen`, `alarmsScreen`, `setAlarmScreen`,
`timerScreen`, `musicScreen`; plus a full-screen overlay `#firedOverlay` for fired alarms/timers (tap to dismiss,
sends `dismiss`). Navigation is **tap-based**: tap the alarm status line → alarms; tap the timer line → timer;
tap the music line → Now Playing; back buttons return. A small **24H/12H pill** (top-right, clock screen only)
persists the choice in `localStorage('use24h')`, default 24h.
Behaviours **[VERIFIED]**: fullscreen on first tap (needs a user gesture), Screen Wake Lock API with re-acquire on
`visibilitychange`, auto-reconnecting WebSocket (every 3 s, shows "COMPANION OFFLINE · SERVICE HORS LIGNE"),
live next-alarm and timer status lines, alarms list with enable toggle/delete, set-alarm stepper
(hour math is done in 24-hour space: a real bug at the 12 AM/PM boundary was found and fixed), timer
setup/countdown (Start/Cancel only; no Pause), Spotify Now Playing (art, title, artists, progress, prev/play/next,
volume slider) driven by the Web Playback SDK's `player_state_changed`.
Key JS: `connectCompanion()`, `renderAlarmStatus()`, `renderAlarmsList()`, `openSetAlarm()/syncSetAlarmUI()`,
`renderTimerStatus()/renderTimerScreen()/updateTimerCountdown()`, `loadSpotifySDK()/initSpotifyPlayer()/renderMusic()`,
`requestWakeLock()`, `render()` (1 Hz clock loop that also ticks timers and progress bars).
Known limits **[DECIDED/accepted]**: no swipe navigation and no odometer time picker (the Figma shows both; tap + stepper
chosen to keep scope small); only the first timer is shown/cancelled by the UI although the engine supports many;
`ws://localhost:8765` is hard-coded, so loading the page from another device (e.g. a tablet over the LAN) shows
"companion offline" — irrelevant when page and companion run on the same machine.

### B5.2 `companion.py` — the service (~270 lines)
- `Store` (alarms, timers) persisted to `companion_state.json`; `broadcast()` to all clients.
- `scheduler_loop()` runs every second: fires an alarm when `hour/minute` match and `tm_wday` is in `days` (guarded so it fires once per minute), fires timers when `ends_at` passes, removes fired timers.
- **Audio**: synthesized beeps via `sounddevice` (880 Hz, 3 beeps, plays ONCE, ~1.5 s). **This is a real functional gap**: an alarm clock must ring repeatedly (with a gentle ramp) until dismissed or a max duration. See E0 and F.
- **Wake lock**: tries `wakepy keep.presenting(on_fail="pass")`; on this Linux setup wakepy cannot work (it only knows GNOME/freedesktop D-Bus screensaver services), so a fallback runs `systemd-inhibit --what=idle:sleep --mode=block sleep infinity` (prevents system suspend) and, if `xset` exists (X11 only), disables DPMS. **Screen blanking on Omarchy/Hyprland is prevented by the BROWSER's Wake Lock API, not by the companion** (Wayland idle-inhibit needs a visible surface). **[VERIFIED]**: kiosk stayed awake 10 minutes against a 3-minute idle timeout.
- Spotify: instantiates `spotify_auth.SpotifyAuth`; handles `spotify_login` / `spotify_token`; broadcasts `spotify_status` on connect/login.
- Known behaviours to be aware of: timers whose `ends_at` passed while the companion was down fire immediately on restart; only recurring alarms exist (no one-shot); no snooze; no pause for timers; one 3-beep pattern per firing.

### B5.3 `spotify_auth.py` — Spotify login and tokens (stdlib only)
Authorization Code + PKCE (S256, 86-char verifier). `SpotifyAuth.begin_login()` opens a one-shot HTTP listener on `127.0.0.1:8888/callback` (closes on success or after 300 s), validates `state`, HTML-escapes any echoed text, exchanges the code, stores tokens (mode 0600) with the granted `scope`.
`connected` is true only if a refresh token exists AND every currently requested scope was granted (so changing `SCOPES` forces one clean re-login).
`get_access_token()` refreshes ~60 s before expiry **under an asyncio lock with a re-check** (a real race was found: two simultaneous token requests could wipe the login if Spotify refresh tokens are single-use; unconfirmed whether they are, the fix is harmless either way). On `invalid_grant` the tokens are wiped ONLY if the failing refresh token is still the current one; on network errors tokens are kept.
Scopes requested: `streaming user-read-email user-read-private user-read-playback-state user-modify-playback-state user-read-currently-playing` (the two email/private scopes are a precaution from older SDK guides; may be removable).
Client ID `ee662b5b41094040bb1a169fdd6cd0d0` (public identifier, env override `SPOTIFY_CLIENT_ID`). Redirect URI **must** stay `http://127.0.0.1:8888/callback`.
Also exports `api_get(path, token)` (blocking GET helper). CLI: `python spotify_auth.py login | devices`.

### B5.4 `stt_session.py` — Phase 4a tool (push-to-talk STT check)
Commands: `devices`, `meter`, `talk`, `script`, `replay`, `compare`. See E1 for use. Internals worth knowing:
`Endpointer` (pure logic): calibrates room noise for 0.4 s (**25th percentile**, ignoring saturated frames ≥ 0.5 RMS = device start-up garbage), trigger = max(3 × floor, 0.012), speech starts after 3 loud frames, ends after 0.8 s below 0.6 × trigger, min speech 0.25 s, max 10 s, start timeout 6 s, pre-roll 0.3 s and tail 0.25 s.
`record_utterance()` opens the device at a rate/channel layout it accepts (16 kHz mono, else native rate), does endpointing at that rate and resamples to 16 kHz at the end (scipy if present, else numpy interpolation). `explain()` says WHY nothing was heard (saturated input / quiet mic / inflated noise estimate from speaking too early / too brief).
`transcribe_audio()` calls Voxtral (see D2). `script` reads prompted phrases from a CSV and scores word error rate; `--save-audio DIR` keeps every recording + `manifest.csv`; `replay DIR --lang auto|en|fr|label` re-transcribes the SAME audio under another language setting; `compare A.csv B.csv ...` lines up result files on shared phrases and flags disagreements and non-Latin (e.g. Russian) outputs. Both `script` and `replay` also write `<out>_for_router.csv` (transcript as `phrase`, original `expected_category`, `language`) so the router test can score "speech → transcript → router".

**Version warning:** the owner's local `stt_session.py` is probably the version BEFORE three small fixes made at the very end of the design chat. Check with `grep -n "prepare_save_dir\|overwrite-audio\|Files: " stt_session.py`. If missing, re-apply:
1. `explain()`: add a branch before the generic message — if `floor > 0.004 or threshold > 0.8*peak`, say the noise estimate was inflated (noisy room, or speaking before the half-second pause); make the generic text "too briefly or too softly".
2. `compare`: print `Files: name (N phrases), ...` first; if no phrases are shared say a 0-phrase file is probably empty/leftover; exit with a clear message if a file is missing.
3. Save folders: `--save-audio DIR` must refuse to reuse a folder that already has `manifest.csv` unless `--overwrite-audio` (which deletes only the old session's listed files and manifest); `_save_recording` upserts one manifest row per file; `replay` keeps one row per file (a stale duplicate row for `001.wav` in `rec1/` made the first phrase appear twice).

### B5.5 Router tooling (Phase 0 / 0.5; read `phase0/phase0_log.md` and `phase0_5/`)
- `phase0_pipeline_test.py`: `batch <csv> [--model X] [--split S] [--quiet] [--no-override]` scores the router on text; `record` does mic → Voxtral → router. Contains `ROUTING_QUESTIONS` and `classify()` including the **deterministic override** (a regex that forces `fallback` at confidence 1.0 for the "parle plus fort / speak up / I can't hear you" family). The local version is the agent-extended one; trust the local file over any copy elsewhere.
- `test_override.py`: pins the override (10 must-fire + 15 must-not-fire phrases, including every bare-comparative volume command the model handles). Keep it green.
- `phase0_5/`: the whole fine-tuning effort (spec with 4 addenda, data generators, verifier reports, `prep_items.py`, `train_single_t4.py`, `eval_finetuned.py`, `COLAB_RUNBOOK.md`, `CHECKPOINT_SHIP.md`, `post_training_results.md`, `french_syntax_residual.md`). See Appendix 1 for the story and numbers.
- `phase1/phase1_design_notes.md`: the destructive-action confirmation rule (read it; summarized in G and E2.6).
- `llm_speed_test.py`, `llm_timings.csv` (root): created after the design chat, **contents not known to the author of this handoff**. Probably a latency test of cloud LLMs for the 4c fallback. Read before extending; do not assume.

---------------------------------------------------------------------------------------------------
# C. DECISION LOG (what was chosen, why, and what it implies)

| # | decision | why | consequence / what to keep doing |
|---|---|---|---|
| 1 | Web page in a kiosk browser + Python companion | most reusable skills, runs unchanged on laptop/tablet/mini-PC, no SBC/Android dependency | UI stays plain HTML/JS; anything needing OS/hardware goes in the companion |
| 2 | Python + WebSocket (not HTTP polling) | alarms/timers must push instantly; bidirectional; same language as the ML tooling | keep the JSON protocol in B3 as the single contract; version it if it changes |
| 3 | Companion is the source of truth (alarms, timers, tokens, mic, audio) | page can reload/close without losing state; voice must work when the page is closed | never move state into the page |
| 4 | Plain HTML/CSS/JS, no framework, single file | the UI is small; no build step; easy to test in a simulated DOM | resist adding React/Vite/etc. unless the file becomes unmanageable (then split into a few plain files, still no bundler) |
| 5 | Design = the Figma export (near-black, JetBrains Mono, amber status chrome, white hero clock, EN/FR together) | owner preferred it over earlier attempts; "modern, polished, NO glassmorphism, rounded corners fine" | see Appendix 3; do not reintroduce blur/translucency |
| 6 | Tap navigation, stepper time pickers | swipe gestures and odometer pickers add real complexity and were not needed to prove features | revisit only in a polish pass |
| 7 | 24-hour clock by default, 12h toggle | owner is French | keep both paths working |
| 8 | Cloud for STT/TTS/LLM = Mistral (Voxtral STT + TTS, chat models) | French provider, fast, one vendor for all three; owner targets that ecosystem long term | API key in env only |
| 9 | Local router = Laya multilingual, fine-tuned (RLCD) | untuned it was 56% on French; fine-tuned ~93-97% on held-out text | see Appendix 1 for the criteria and residuals |
| 10 | Fine-tune via RL only (RLCD), no SFT stage | that is how Laya is built (calibrated decisions); the official recipe already includes a soft-CE term | no further fine-tuning rounds under the old spec; any new round needs a NEW frozen spec with new evidence |
| 11 | Direction-based safety criterion (fallback→action = dangerous, zero tolerance; action→fallback = fails safe, tolerated) | the router sees only coarse categories, so a confidence threshold cannot make errors vanish; but errors split cleanly by direction | gate execution by direction + deterministic override + confirmation for destructive actions |
| 12 | Destructive actions need confirmation regardless of router confidence | router cannot distinguish "set" from "cancel" alarm (same category) | implement downstream in the slot parser/executor (E2.6) |
| 13 | Spotify via the official Web Playback SDK in the browser (not librespot) | official/supported; librespot is unofficial, ToS-gray, and had an open outage report on 2026-09-29 | needs Premium, Widevine in the browser, loopback redirect URI |
| 14 | Companion owns Spotify login + tokens | so voice (Phase 4) can call the Web API without the page | page asks companion for tokens via WS |
| 15 | Screen blank prevention by the browser Wake Lock API; suspend prevention by the companion | Wayland idle-inhibit needs a visible surface; `systemd-inhibit` alone does not stop Omarchy's idle service | keep BOTH layers; launch Chromium with `--ozone-platform-hint=auto` |
| 16 | No auto-restart/OS supervision until hardware/OS is chosen | cannot be configured sensibly yet | do it in Phase 5/6 (systemd units), not before |
| 17 | Timer UI: Start/Cancel only (no Pause) | engine has no paused state; not worth the complexity for v1 | revisit in F |
| 18 | Honest empty states instead of fake data | principle A3.4 | weather/now-playing slots stay empty until real data exists |
| 19 | The router is NOT asked to do sub-actions (set vs cancel vs query vs snooze) | categories were fixed during fine-tuning; changing them needs retraining | sub-intents come from a deterministic slot parser (E2.3) |
| 20 | Language handling for STT: do NOT force one language globally | measured: forcing French wrecks English phrases (see Appendix 2) | auto + guard, or dual-candidate arbitration; decide with data (E2.4) |
| 21 | Laya runs locally; a hosted OpenAI-compatible gateway (Impossibl) and TypeSafe's proprietary Jev model were considered | Laya is open, tiny and fast on CPU; a gateway only makes sense if Laya were served remotely | not needed; Mistral is the only cloud provider in the design |

---------------------------------------------------------------------------------------------------
# D. EXTERNAL SERVICES — VERIFIED FACTS, LIMITS, TRAPS
Dates matter: these were checked in late Sept / early Oct 2026. Services change; re-check anything marked [UNVERIFIED] or anything that starts failing.

## D1. Spotify
- **Premium is required**: the listener's account (Family plan is fine; a community thread reports the SDK failing on Lite/Mini plans, **[UNVERIFIED]** so do not rely on those) AND, since the February 2026 Developer-Mode changes, the **owner of the developer app** must have active Premium. New dev-mode apps are capped at a handful of users (irrelevant for a personal device). `GET /me` no longer returns `product`, `country`, `email`, so Premium cannot be auto-detected: show a clear error instead. **[VERIFIED against Spotify's migration guide]**
- **Redirect URIs must be loopback IP literals**: `http://127.0.0.1:PORT/...`. `localhost` is rejected. Registered: `http://127.0.0.1:8888/callback`. **[VERIFIED]**
- **Web Playback SDK** (script `https://sdk.scdn.co/spotify-player.js`): needs Widevine/EME in the browser (stock open-source Chromium often lacks it; this owner's Chromium has it — checked with `navigator.requestMediaKeySystemAccess('com.widevine.alpha', ...)`), Premium, and a secure context (localhost/127.0.0.1 OK; plain-HTTP LAN origins are **[UNVERIFIED]** and probably not OK). API used: `new Spotify.Player({name:'NestClockOS', getOAuthToken, volume})`, events `ready` {device_id}, `not_ready`, `player_state_changed`, `initialization_error`, `authentication_error`, `account_error`, `playback_error`; methods `connect`, `togglePlay`, `nextTrack`, `previousTrack`, `setVolume`, `getVolume`, `seek`, `activateElement`, `getCurrentState`. `getOAuthToken` is called by the SDK whenever it needs a token and may be called concurrently (this is what exposed the refresh race).
- **Web API player endpoints needed in 4b** (companion → Spotify, `Authorization: Bearer <token>`): `GET /v1/me/player/devices` (**[VERIFIED]** 200, returns the owner's phone as an active device), and **[UNVERIFIED until exercised]**: `GET /v1/me/player`, `PUT /v1/me/player/play`, `PUT /v1/me/player/pause`, `POST /v1/me/player/next`, `POST /v1/me/player/previous`, `PUT /v1/me/player/volume?volume_percent=N`, `PUT /v1/me/player` (transfer playback, body `{"device_ids":[id],"play":bool}`). Each takes an optional `device_id`. Re-read the current reference and the Feb 2026 migration guide before coding; the guide, as read, did not list player endpoints among removals. Expect: 404 "no active device" → transfer playback first; 403 → not Premium; 429 → back off (Retry-After).
- **Starting music by voice** has a design gap: the Web API can resume the last context, or play a given URI/context. "Mets de la musique" with nothing to resume needs a policy (see J). Searching Spotify is possible but dev-mode quotas/limits apply (search results capped at 10 as of the guide).
- **Autoplay policy**: browsers need one user gesture before audio. The first tap (fullscreen) activates the player (`activateElement`). After an unattended reboot nobody taps: Chromium's `--autoplay-policy=no-user-gesture-required` is the standard switch **[UNVERIFIED on this build]**; test it in the real kiosk launch.
- **Why not librespot/spotifyd**: unofficial reverse-engineered client, ToS-gray (its own README says so), and an open issue (#1771) reported Connect failing since 2026-09-29. **[DECIDED]** official SDK only.
- **Token lifetime**: access tokens ~1 hour. The refresh path was tested with mocks and in real use for a day-plus gap, but the owner once had to reconnect after a gap longer than a day (cause never confirmed; the race fix is the best hypothesis). **A >24-hour soak test with the page open is required before calling Spotify reliable.**

## D2. Mistral — Voxtral STT (and TTS), chat models
- **STT call** **[VERIFIED]**: `client.audio.transcriptions.complete(model="voxtral-mini-latest", file={"content": <open binary file>, "file_name": "x.wav"}, language=None|"fr"|"en")`; response `.text`. Import `from mistralai.client import Mistral` (current docs) with fallback `from mistralai import Mistral` (older SDKs). Docs said `voxtral-mini-latest` currently points to `voxtral-mini-2602` (an alias; pin a dated model id if behaviour must stay stable).
- **The response carries no detected language** (`getattr(resp, "language", None)` was always empty). So Voxtral's language ID cannot feed a router's `lang_guess`; we decide language ourselves.
- **Measured latency**: 200-600 ms for 1-4 s clips (p50 ≈ 270-280 ms, p90 ≈ 320-460 ms). Cloud STT is viable inside a voice loop.
- **Failure modes seen** (Appendix 2): automatic language detection occasionally emits **Russian/Cyrillic on very short clips** (3 of ~67); forcing the wrong language is harmful (English forced to French produced French nonsense and even Dutch); forcing French on code-switched phrases actually normalises them well; digits vs number words vary ("2" vs "two"); times arrive as `8.30`, `8h`, `8 a.m.`; "minuteur" is often heard as "compteur" or "timer"; first words get clipped when the speaker starts talking before the capture is ready.
- **Other documented options, not tried**: a streaming/real-time transcription model (`voxtral-mini-transcribe-realtime-2602` per the docs) and context biasing (`context_bias`; documented as optimised for English, experimental elsewhere). Worth a measured experiment on the saved recordings (replay harness) before adopting; do not adopt on faith.
- **TTS** **[UNVERIFIED]**: docs mention `voxtral-mini-tts-2603` and `client.audio.speech.complete(...)` with streamed events (`speech.audio.delta` / `speech.audio.done`). Read the current TTS docs before writing any code: voices, French quality, latency to first audio, output format, pricing.
- Pricing/rate limits were not checked. Do not put STT calls in a loop on silence; send audio only after a trigger.
- The owner already has an API key; it lives in the `MISTRAL_API_KEY` environment variable.

## D3. Laya (router) and Hugging Face
- Checkpoints: `convaiinnovations/laya` (English), `laya-multilingual` (mmBERT-base backbone, ~322M parameters, 100+ languages), `laya-typed-decisions` (ModernBERT-large, **English-only architecture**, fine-tuned on invoice/support workflows; tested and rejected for this task). Reported licence Apache-2.0 **[UNVERIFIED: re-read the model card if you redistribute]**.
- The model answers typed questions in one forward pass: `choice` (pick one of N options), `score`, `noul` (yes/no style). `Router.predict(state, questions, model=...)`. The built-in `Router` picks the english or multilingual checkpoint with a script/diacritic heuristic that **misroutes plain-ASCII French** to the English checkpoint; irrelevant now because the product uses ONE fine-tuned multilingual checkpoint for everything (bypass the Router's language routing).
- Training method: RLCD (Reinforcement Learning for Calibrated Decisions): the policy outputs a distribution, Gaussian noise is added to logits for exploration, reward = strictly proper scoring rules (log + spherical), REINFORCE with a group-mean baseline; the official recipe also includes a soft cross-entropy term. After training, per-question temperatures are fitted (calibration). Untuned base checkpoints are badly calibrated (the "invalid temperatures ... treat confidence as uncalibrated" warning is expected on them).
- Install on a CPU-only machine without pulling multi-GB CUDA wheels: `pip install torch --index-url https://download.pytorch.org/whl/cpu`, then `pip install laya --no-deps`, then `pip install transformers safetensors huggingface_hub`.
- Size/latency: each checkpoint is ~650-850 MB on disk. The model card claims ~tens of ms per decision on CPU **[UNVERIFIED on the owner's laptop: measure inside the companion]**.
- **The fine-tuned checkpoint**: the original run-3 weights were lost (Colab session wiped before download). The owner has since **reproduced run 3 from the documented recipe and pushed it to a private Hugging Face repo** under the account `keypa` (the planned id was `keypa/laya-multilingual-nestclock`; confirm the exact id in `phase0_5/CHECKPOINT_SHIP.md` / `post_training_results.md`). The reproduction is NOT byte-identical to the original run 3 (RL exploration noise), so re-read `post_training_results.md` for the numbers it reached and re-check the direction-based criterion (Appendix 1) before trusting it. Download it once, keep a local copy in the project (outside git), and load from the local path at runtime so the device never needs a Hugging Face token.
- The `is_complete` head (noul) was NOT trained (the dataset has no labels for it). Never use its output.

## D4. The owner's environment (affects what works)
- Dev laptop: ThinkPad E14 Gen 2, AMD Ryzen 5 4500U (6 cores), ~21 GB RAM, Radeon Vega integrated graphics, no discrete GPU, 14" 1080p, plus an external monitor. **Omarchy 4.0.4 (Arch Linux), Hyprland 0.56.2 (Wayland), foot terminal, PipeWire.** Python is uv-managed CPython 3.13.
- Idle handling: classic `hypridle` is NOT running; Omarchy's own idle service honours Wayland idle-inhibit (a visible window using the Wake Lock API) but **not** `systemd-inhibit` for screen blanking. **[VERIFIED]**
- Chromium must run on its native Wayland backend (`--ozone-platform-hint=auto`) for the Wake Lock API to inhibit idle.
- `xset` is not installed (X11 only; irrelevant on Wayland). `wakepy` only knows GNOME/freedesktop D-Bus screensaver services, so it always reports "could not activate" here; harmless, kept as the first attempt for portability.
- Audio: PipeWire exposes `default` and `pipewire` ALSA devices (128 channels, resampled), the raw analog codec ALC257 (`hw:1,0`), HDMI outputs, and JACK-named duplicates. Raw `hw:` devices often refuse 16 kHz mono. **Device indices shift when devices are plugged/unplugged**; pass a device NAME (e.g. `--device pipewire`) or re-run `python stt_session.py devices` before every session. On a first stream open the device can emit a burst of full-scale garbage (handled: ignored when measuring noise).
- Chromium prints harmless startup errors (GCM `DEPRECATED_ENDPOINT`, on-device model "Unable to get gpu adapter"): ignore them.
- Other devices: Samsung Tab S10 Lite (Android, school tablet, **touch-testing only, not the final device**), Samsung S24 Ultra phone (tap-to-fullscreen verified).
- Budget reality: hardware is expensive in the owner's market; do not propose purchases without alternatives and prices checked.

---------------------------------------------------------------------------------------------------
# E. ROADMAP IN DETAIL

Order of work (do not skip ahead; each step has an exit criterion):
E0 housekeeping and alarm correctness → E1 finish Phase 4a (data + language policy) → E2 Phase 4b (voice → action, push-to-talk) → E3 Phase 4c (LLM fallback, spoken replies, weather) → E4 Phase 4d (wake word) → E5 Phase 4e (voice UI states) → F Phase 5+ (polish, hardening, hardware).
Use the generator → verifier → numbers → stop pattern from Phase 0.5 for any data or training work, and a frozen written spec with numeric acceptance criteria for anything bigger than a day of work.

## E0. Housekeeping and alarm correctness (small, do first)
1. Read, in this order: `phase0/phase0_log.md`, `phase0_5/phase0_5_finetune_spec.md` (all 4 addenda), `phase0_5/post_training_results.md`, `phase0_5/CHECKPOINT_SHIP.md`, `phase0_5/french_syntax_residual.md`, `phase1/phase1_design_notes.md`, `llm_speed_test.py` + `llm_timings.csv`, then this file's Appendix 2.
2. Initialise git if not already; add the `.gitignore` from B4; commit a baseline. Delete leftovers: `stt_rec1.csv`, `stt_rec1_for_router.csv` (empty leftovers of an aborted run), `__pycache__/`.
3. Verify `stt_session.py` has the three late fixes (B5.4) and re-apply if missing.
4. **Make alarms ring properly** [PROPOSED, high value, small]: when an alarm fires, loop the sound until dismissed or a maximum duration (default 10 min), with a gentle volume ramp (e.g. 0.15 → 0.6 over ~30 s) and a short pause between bursts; same for timers but without the ramp. Implement as an asyncio task owned by the scheduler (cancelled by `dismiss`). Keep the audio backend behind a tiny interface so tests can use a fake. Test: ringing continues after the first pattern, stops on dismiss, stops at max duration, survives a client disconnect, and a second alarm firing while one rings does not stack sounds.
5. **One-shot alarms**: add `once: true` (and an optional absolute `date`) to the alarm model so "wake me at 7 tomorrow" is not a permanent daily alarm; after firing, a one-shot is deleted (or disabled; decide, then make the UI show it consistently). Update `renderAlarmsList` to display "once / une fois" and the date. Needed by E2.
6. **Timers that expired while the companion was down**: decide and document behaviour (currently they fire immediately at startup). [PROPOSED]: fire if overdue by < 2 minutes, otherwise drop silently and log.
7. Start the `voice/` package skeleton and move the pure logic out of `stt_session.py` (Endpointer, resampling, WER/normalisation) into it so the dev CLI and the companion share one implementation (DRY). Keep `stt_session.py` working.

## E1. Finish Phase 4a: data and the language policy
Goal: know, with numbers on the owner's real voice, how good speech → transcript → router is, and pick a language policy.
1. Run the pending replay: `python stt_session.py replay rec1 --lang en --out r_en.csv`, then `python stt_session.py compare stt_rec1_test.csv r_label.csv r_fr.csv r_en.csv`. Listen to `rec1/016.wav` ("Lance un minuteur de 5 minutes", garbled in every run) and `rec1/020.wav` (code-switched alarm phrase): is the audio clipped/mumbled, or is the model wrong? (`aplay file.wav` or `mpv`.)
2. **Record a larger, more realistic evaluation set** (≥ 120 utterances, ideally 200): prompts from `phase0_5/synthetic_dataset_raw.csv --split held_out_eval` (500 phrases, includes "hey nest, ..." prefixes and realistic fillers) and the hand-written `phase0/test_phrases_large.csv`; mix ≈ 50% French / 35% English / 15% mixed, all five categories equally; vary conditions: quiet room, music playing at moderate volume, ~1-2 m from the mic, different times of day; keep each session in its own `rec*/` folder (one session per folder; the script now refuses to reuse a folder). These recordings are **permanent test fixtures** (they feed the dry-run regression in H, and can serve as a held-out evaluation set for any future router work).
3. **Language policy experiment** (replay is free, same audio): compare `auto`, `label` (oracle), `fr`, `en`. Then simulate two candidate runtime policies offline, using the fine-tuned router on the transcripts:
   - (P1) `auto`, and if the transcript contains non-Latin characters (`non_latin()` in `stt_session.py`) retry once.
   - (P2) transcribe twice in parallel (`en` and `fr`; no extra latency since the calls are concurrent), run the router on both transcripts, keep the one with the higher category confidence, with a sanity guard (Latin script, non-empty).
   Keep the one that wins on routing accuracy and on the "fallback→action" count, not on word error rate.
4. Exit criteria for 4a **[PROPOSED]**: recorder-side misses (empty transcripts when the pause is respected) < 3%; non-Latin outputs < 2% after the guard; a documented language policy with numbers behind it; router accuracy on real transcripts measured and recorded in a results file.

## E2. Phase 4b — voice → action (push-to-talk first)
Scope: a tap on a mic button (or a keyboard key in dev) starts one capture; the pipeline transcribes, routes, parses, executes, and reports state. No wake word yet.

### E2.1 Structure [PROPOSED]
A `voice/` package imported by `companion.py` (keep `companion.py` readable):
`voice/audio.py` (device opening, resampling, ring buffer), `voice/endpoint.py` (Endpointer), `voice/stt.py` (Voxtral wrapper + language policy + retries/timeouts), `voice/router.py` (Laya load, `classify()`, override, thresholds), `voice/slots.py` (deterministic parsers), `voice/actions.py` (execute against the Store and Spotify), `voice/pipeline.py` (glue, timing, logging), `voice/dryrun.py` (offline WAV → parsed action).
Every network call has a timeout and a clear failure path (offline Wi-Fi must not freeze the clock; alarms and timers must keep working with no network).

### E2.2 Microphone ownership and trigger [DECIDED: companion owns the mic]
Reasons: Python has direct device control, it works when the page is closed, the later wake word runs here, and it avoids browser microphone-permission prompts and Chromium audio quirks. The UI gets a mic button; it sends `voice_listen`; the companion captures one utterance and reports state events (E5). Capture must not block the asyncio loop (run blocking audio/HTTP/model work in executors; alarms must fire on time during a voice interaction).
Design the capture as an **always-open input stream with a ring buffer** from the start (even for push-to-talk): measure room noise from the audio *before* the trigger. This removes the push-to-talk handicap seen in 4a ("speak after a half-second pause", clipped first words, inflated noise floor) and is exactly what the wake word needs.

### E2.3 Router integration
- Load the fine-tuned checkpoint from the LOCAL copy at startup (CPU), warm it up with one dummy call, expose `route(text) -> {category, confidence, override_fired, ms}`. Copy the exact loading and question-building code from `phase0_5/eval_finetuned.py` and `phase0_pipeline_test.py` (`ROUTING_QUESTIONS`, `classify()`); **do not alter the category set or the criteria wording** (the model was fine-tuned on that exact text; changing it silently degrades accuracy and calibration).
- Keep the deterministic override and its test (`test_override.py`) green; if new known-dangerous phrasings are found from real transcripts, extend the override, never the thresholds.
- **Execution gate [PROPOSED]**: execute locally only if confidence ≥ 0.5 AND the action is non-destructive AND the slot parser succeeded; otherwise hand the transcript to the LLM/clarification path. Tune the number on real transcripts (E1 set) with the direction-based lens (Appendix 1). Understand the limit: raw confidence cannot remove all dangerous errors (some are confident), so safety comes from three layers: the override, the confirmation rule (E2.6), and the fact that the dangerous direction's worst case here is a spurious music action, not a destructive one.
- Run the model in a thread executor; measure p50/p90 latency and idle/peak RAM inside the companion; record them in the results file.

### E2.4 Language handling (open, decide with E1 data)
Hard facts: Voxtral reports no language; auto-detect fails on ~4% of short clips; forcing one language hurts the other; forcing French helps code-switched phrases. Candidate policies are P1 and P2 in E1.3. Also needed: the **reply language** (E3): detect it from the transcript with a tiny local heuristic (stop-word counts or a small library) and default to French when ambiguous; the UI always shows both languages anyway. A Settings language toggle (Figma) should only change UI/reply defaults, not force STT.

### E2.5 Slot parsing — deterministic, bilingual, tested table-first
The router gives only a category. A deterministic parser derives the **sub-intent** and the **slots**. Do this with small, explicit, well-tested functions; do not call an LLM for these (it was explicitly decided that the LLM gets only the fuzzy leftovers and only one relevant tool).
Sub-intents per category (keyword families, EN + FR, accent-insensitive, tolerant to STT variants):
- **alarm**: *set* (réveille-moi, mets/programme une alarme, wake me, set an alarm), *cancel/delete* (annule, supprime, éteins, cancel, delete, turn off — DESTRUCTIVE), *query* (est-ce que mon alarme est active, is my alarm set, quelles alarmes), *snooze* (repousse, snooze), *toggle*, *change* (change l'alarme à 9h → modify).
- **timer**: *start* (lance/mets un minuteur, start a timer, countdown, compte à rebours), *cancel* (annule le minuteur — DESTRUCTIVE), *query* (où en est le minuteur, il reste combien, how much time is left), *add time* (ajoute 2 minutes), *restart/pause* (restart exists in the data; pause is unsupported by the engine today).
- **music**: *play/resume* (mets de la musique, reprends la lecture, continue la lecture, resume), *pause/stop* (coupe, arrête, pause, stop), *next/previous*, *volume up/down* (monte/baisse le son, augmente/diminue le volume, un peu plus/moins fort, turn up/down), *volume set* (mets le volume à 50), *play something specific* (artist/playlist: needs Spotify search; defer).
- **weather**: today/tomorrow/weekend/now, temperature, rain, umbrella, wind (location defaults to the configured city).
- **fallback**: not parsed; goes to the LLM or to a small set of **local deterministic skills** that are cheaper and faster than an LLM: current time ("quelle heure est-il", "what time is it"), current date. [PROPOSED]
Entities to extract and the STT output shapes already observed (accept ALL): times `7h`, `7h30`, `7 h 30`, `7:30`, `7.30`, `8.30`, `8 a.m.`, `8am`, `huit heures`, `sept heures et demie`, `huit heures moins le quart`, `midi`, `minuit`, `eight thirty`, "half past"; durations `5 minutes`, `cinq minutes`, `2-5 minutes`(garbled), `une heure et demie`, `20 seconds`, `half an hour`; days `demain`, `tomorrow`, weekday names FR/EN, `tous les jours`, `en semaine`, `le week-end`, `every weekday`, `weekends`; labels (free text, optional); volume amounts (`un peu`, `a bit`, percentages).
Rules [PROPOSED]: "wake me at 7" with no day → one-shot for the **next occurrence**; "every ..." / "tous les ..." → recurring; a time with no am/pm in English → next upcoming occurrence; STT variants like "compteur"/"timer" count as "minuteur" when the router says `timer`; unparseable or ambiguous → ask a short clarification, never guess a destructive target. Add French number words fully (including 70-99 forms).
Test table-first: a CSV of (utterance, category, expected sub-intent, expected slots) in both languages, including every STT-damaged variant from Appendix 2; run it in CI-style. Grow it from real transcripts.

### E2.6 Safety and confirmation (from phase1_design_notes.md)
Any DESTRUCTIVE sub-intent (cancel/delete/turn off an alarm or timer) requires confirmation regardless of router confidence: companion sends `confirm_request {id, action, text_en, text_fr}`; the UI shows two big buttons (tap yes/no) and a voice yes/no is accepted for ~8 s via a short capture that bypasses the router (simple local keyword check: oui/yes/ouais/ok vs non/no/annule); timeout = cancel; never auto-confirm; log both the request and the outcome. If the target is ambiguous (several alarms), ask which one. If only one candidate exists, still confirm.

### E2.7 Companion changes needed (collected)
`once` alarms and the ringing loop (E0); snooze; `spotify_device` message and a small Spotify Web API client (play/pause/next/previous/volume/transfer with device id, error handling, token refresh already exists); `voice_listen` + `voice_state`/`voice_result`/`confirm_request`/`confirm_response` messages; a mic button in `index.html`; interaction logging.

### E2.8 Observability [PROPOSED, do it early]
Append one JSON line per interaction to `voice_log.jsonl` (git-ignored): timestamp, audio seconds, STT ms, language policy used, transcript, router category/confidence/override flag, parsed sub-intent/slots, action executed or deferred, total ms, error. Retention is local and user-controlled; saving raw audio is **off by default** and only enabled by an explicit debug flag. This log is the raw material for every later tuning decision.

### E2.9 Acceptance for 4b [PROPOSED numbers, adjust when measured]
On the E1 real-voice set, with the real pipeline in dry-run mode (no side effects): routing accuracy ≥ 85% overall and ≥ 85% for each of French and English; **zero** fallback→action errors on a dedicated list of dangerous/ambiguous phrases (including the "parle plus fort" family); slot-parser exact match ≥ 90% on its own table and ≥ 80% on real transcripts; local-action end-to-end latency (end of speech → action done) p90 < 1.2 s; no event-loop stalls (alarm fires within 1 s of target while a voice interaction runs). If a number is missed, report it with the failing cases and stop for a decision; do not tune blindly.

## E3. Phase 4c — LLM fallback, spoken replies, weather
- **LLM** (Mistral chat): used only when the router says `fallback`, confidence is below the gate, or the slot parser cannot decide. Choose the model by measurement: `llm_speed_test.py`/`llm_timings.csv` exist (read them), compare time-to-first-token and answer quality in FR/EN. Keep replies to one or two spoken sentences, no markdown, answer in the user's language, include current date/time/timezone in the prompt. Do **not** expose the full toolbox: tool calling with a heavy schema made Mistral models unreliable in the owner's experience; if tools are used, expose only the single relevant one. Stream the answer and feed the TTS in sentence-sized chunks to cut latency.
- **TTS**: Voxtral TTS **[UNVERIFIED — read the current docs first]**. Play through the same audio backend as alarms; barge-in: a wake word, tap, or `dismiss` must stop speech immediately; duck or pause Spotify while speaking and restore it afterwards (companion has the Web API and device id).
- **Confirmation style** [PROPOSED]: local actions confirm visually plus a short earcon (instant and free); speak only when information is returned (answers, queries). Make it a setting.
- **Weather**: needs a data source. Candidate: Open-Meteo (free, no key) **[UNVERIFIED — check the docs, terms, rate limits and the weather-code table]**. Location is a configured city (the Figma uses Paris) to avoid location APIs. Bilingual condition strings. Feeds the home-screen weather strip and the weather screen (Figma). Never show fake weather; if the fetch fails, show nothing or an honest "unavailable".
- Acceptance [PROPOSED]: LLM fallback to first spoken audio p90 < 3 s; offline mode degrades gracefully (local actions still work; voice replies say the network is unavailable); no audio or text is sent to the cloud for anything the local path handled.

## E4. Phase 4d — custom wake word
- Requirements: custom phrase that can be **changed periodically** (the owner wants this); runs continuously on CPU with low load; low false-accept rate even with music or TV; works in French-accented English and French; fully local; the Figma settings mock shows the phrase "Hey NestClock" and the synthetic training data uses a "hey nest" prefix, but the real choice is the owner's (J).
- **Research first**: current open-source options and their licences (openWakeWord is the best-known open candidate and may allow custom-trained models from synthetic speech, but its pretrained-model licence and tooling must be checked **[UNVERIFIED]**; commercial engines may need access keys/licences). Pick by licence, custom-training workflow, CPU cost, and measured false accepts, not by reputation.
- Design: the always-open ring-buffer capture from E2.2 feeds the detector in ~80 ms frames. On trigger: pause or duck Spotify (Web API), take the pre-roll from the ring buffer, run the same endpointing + STT + pipeline, then restore music. Debounce and a cool-down after each trigger.
- **Self-echo** is the known hard part: the speaker (music/TTS) is heard by the microphone. Mitigations in order of effort: duck/pause music on trigger and keep TTS short; place the mic away from the speaker; PipeWire has an echo-cancel module **[UNVERIFIED on this system]**; the most reliable fix is hardware with built-in echo cancellation (a USB speakerphone/conference puck) — decide when choosing hardware (F). Do not start a long AEC research project before the wake word works in a quiet room.
- Measure, don't assume: false accepts per hour in a quiet room, with speech nearby, with music, with the TV; false rejects at 0.5 m / 2 m / 4 m; French and accented-English pronunciations. [PROPOSED bars]: ≤ 1 false accept/hour quiet, ≤ 3/hour with TV; ≥ 90% detection at 2 m.

## E5. Phase 4e — on-screen voice states (from the Figma "Voice Assistant" screens)
- Companion → page events [PROPOSED]: `voice_state {state: idle|listening|thinking|speaking|error, transcript?, reply_en?, reply_fr?, level?}`, `voice_result {category, action, ok}`, `confirm_request`. Page → companion: `voice_listen`, `confirm_response`, `dismiss` (also cancels speech).
- UI: a full-screen overlay (like `#firedOverlay`; a fired alarm always takes priority): listening = concentric rings + mic with "Listening… / À L'ÉCOUTE"; thinking = a minimal, clearly different state; speaking = reply text stacked EN then FR and the line "USER: …" with the transcript. The Figma's "AMBIENT NOISE: 34DB" line is only acceptable if it shows the **real measured** level.
- Return to the previous screen after the interaction; respect `prefers-reduced-motion`; keep the bilingual convention (Appendix 3).

---------------------------------------------------------------------------------------------------
# F. PHASE 5 AND BEYOND

## F1. Phase 5 — product polish and hardening (mostly software; can start before hardware is chosen)
The original roadmap's Phase 5 was "polish + the burn-in fix + pick/mount hardware". Here is everything it includes now.

1. **Anti-burn-in (the owner's main complaint about the old clock).** Slow imperceptible pixel-shift of the whole clock block (a few px every few minutes); a night dimming schedule (the Figma shows "AUTO-DIM 12%"; start/end times configurable, [PROPOSED] default 22:00-07:00; optional sunrise/sunset later); dim or auto-hide static chrome (the 24H pill, hints) after idle; no large static bright areas on the home screen; at night prefer the dim clock only. **Brightness control is platform-specific**: a CSS dimming overlay works everywhere but does not lower backlight power or help an OLED as much; real backlight control is OS/hardware-specific (Linux backlight tools, Android API). Implement `set_brightness(percent)` as a small isolated module in the companion with a CSS fallback in the page. Whether the new panel is OLED or LCD is unknown (J): ask before over-investing.
2. **Settings screen** (Figma "NestClock Settings"). Implement only settings that do something real: UI/reply language default, 24h/12h, brightness + auto-dim schedule, wake word on/off + sensitivity, assistant volume, Spotify connection status with connect/disconnect, weather city. **Do not reproduce the Figma's fake fields** (Wi-Fi network name, firmware version, MAC address, "system reboot") unless real data/function exists; Wi-Fi is an OS concern. Persist everything in ONE `settings.json` owned by the companion and push it to the page over WebSocket (single source of truth).
3. **Weather**: home-screen strip and the detailed weather screen (current conditions, humidity, wind, 5-day forecast, an alert card only if the data source really provides alerts). Built on the E3 data source.
4. **Alarm features** (small, high value): ringing loop and ramp (E0), **snooze** (tap and voice, configurable length, default 9 min), selectable sounds, **wake to Spotify** (at alarm time start a chosen playlist via the Web API, and **always keep the beep as a fallback** if Spotify/network fails: reliability beats features), alarm-missed log. Timers: **pause/resume** (needs a paused state in the engine: store remaining seconds, freeze, resume), multiple-timer list UI, named timers by voice.
5. **Reliability and operations** (needs the hardware/OS decision for the final form, but the pieces can be written now): systemd units (companion, static file server, kiosk launcher) with `Restart=always`; a browser watchdog (relaunch the kiosk if it dies); `EnvironmentFile` for `MISTRAL_API_KEY` (mode 0600); journald logging with sane levels; boot ordering; NTP and time-zone (`Europe/Paris`) and **DST tests for alarms**; power-loss recovery; offline-operation test (alarms and timers must work with the network unplugged); 7-day soak test (memory growth, token refresh, WebSocket reconnects, audio device still present after suspend/resume); a `doctor` command that checks mic, audio out, companion reachable, Spotify connected, Mistral key present and reachable, router model loads, disk space.
6. **Security and privacy hygiene**: companion binds localhost only (keep it that way unless LAN display becomes a goal, then add auth and TLS first); token file permissions; no secrets in logs; reconsider the `user-read-email` / `user-read-private` scopes; **a visible on-screen indicator whenever the microphone is capturing**; a software mic-mute toggle; audio never stored unless an explicit debug flag is set; check Mistral's data-retention terms **[UNVERIFIED]**.
7. **Packaging**: a short README (setup in order), pinned `requirements.txt`, the CPU-only torch trick documented, a `scripts/fetch_router.py` using `huggingface_hub.snapshot_download` to place the fine-tuned model in a local folder, a versioned protocol section in this handoff (update it whenever messages change).
8. **Tests as a product feature**: one command that runs everything in H (pytest for Python, a jsdom runner for the page, the dry-run regression on the WAV fixtures).

## F2. Hardware and deployment (decide AFTER the wake word and echo experiments)
Why last: microphone/speaker quality and echo cancellation drive the choice more than the screen does.
- Requirements: touchscreen roughly 10-15" in landscape (tablet-like, bigger than the old Lenovo); runs Linux (the code assumes systemd, PipeWire/ALSA, Chromium with Widevine) with ≥ 4 GB RAM (Chromium ≈ 1 GB, router model ≈ 1 GB, Python); fanless/quiet; power on automatically; a decent far-field microphone and a speaker that is not microscopic.
- **Echo is the real constraint**: a USB speakerphone/conference puck with built-in echo cancellation solves self-echo in hardware (this is a general technique; specific products were not evaluated here, **[UNVERIFIED]**). It also gives a proper microphone and speaker in one cheap box, so the screen device can be simpler.
- Candidate form factors (none evaluated; prices must be checked at purchase time, the owner's market is expensive): refurbished mini PC or thin client + a touch monitor; a refurbished 2-in-1 Windows tablet/laptop running Linux; Chromebook-class hardware. SBCs were rejected on price.
- **Android tablet as a dumb display is a trap**: the page needs the companion over the LAN (companion must bind beyond localhost, with authentication), the Spotify Web Playback SDK needs a secure context (HTTPS) on non-localhost origins **[UNVERIFIED]**, and the Python companion cannot sensibly run on Android. Not recommended unless the owner accepts TLS + auth work.
- Platform-specific code to port and keep isolated: wake lock/idle inhibit, brightness, audio device selection, kiosk autostart and flags (Wayland vs X11), Widevine availability (Chrome vs Chromium).
- Acceptance [PROPOSED]: boots to the clock with no keyboard; an alarm fires after a cold reboot and after a power cut; kiosk recovers from a browser crash within 10 s; survives a 7-day soak.

## F3. Beyond (backlog; only on the owner's request, roughly by value/cost)
- Voice-driven music search ("mets du Vivaldi"): Spotify search within dev-mode limits.
- Router round 2: only with a NEW frozen spec and real evidence (e.g. ≥ N misroutes in the voice log). Candidates: STT-damaged variants ("compteur"), music-domain hard negatives to undo the French statement-order weather collision (see `french_syntax_residual.md`), is_complete labels if ever needed. Use the generate → verify → numbers → stop process and the direction-based criterion.
- On-device STT for offline voice: excluded by CPU cost; revisit only with better hardware.
- Calendar glance, notifications, smart-home triggers, multiple wake words, a LAN remote display (needs auth + TLS), automatic updates (git pull + restart), a light theme (not requested).

---------------------------------------------------------------------------------------------------
# G. DO / DON'T / NOT WORTH DOING

## G1. DO
1. Read the Phase 0.5 spec addenda and results before touching routing: they contain hard-won criteria and reasons.
2. **Verify external API and model details in the current docs before coding** and say plainly what you could not verify (the owner's explicit rule; use calibrated wording: "the docs say", "I tested", "I could not confirm").
3. Write parser tests table-first; keep `test_override.py` green; keep a dry-run regression on the recorded WAV fixtures.
4. Time every pipeline stage and log it (E2.8); decide with numbers.
5. Keep platform-specific code behind small functions in its own module.
6. Keep the companion as the source of truth; keep the page dumb and reloadable.
7. Keep the UI bilingual and honest, following Appendix 3. After any `index.html` edit: extract the `<script>`, run `node --check`, and run the jsdom behavioural test (fake WebSocket, fake `Spotify.Player`).
8. Use fakes for audio, time and network in tests; never wait real minutes for an alarm test when a fake clock works.
9. Handle failure paths: no network, Mistral error/timeout, Spotify 404/403/429, mic missing or device renamed, router model missing. Show a visible, bilingual, non-technical message; never hang; never lose alarms.
10. Prove a bug exists before fixing it (reproduce against the old code), then show the same test passing after.
11. Report actual numbers against the acceptance criteria; at a fork, stop and ask.
12. Keep each recording session in its own `rec*/` folder; they are fixtures.
13. Keep responses to the owner short and decision-oriented; he works under tight usage limits and prefers one clear recommendation with reasons.
14. When product behaviour is not specified (Part J), ask instead of guessing.

## G2. DON'T
1. **Don't change `ROUTING_QUESTIONS`** (category set or criteria wording) and don't add categories: the fine-tuned model depends on the exact text. New sub-intents belong in the deterministic parser.
2. **Don't use or trust `is_complete`**; it was never trained.
3. **Don't chase zero dangerous errors with confidence thresholds**; it cannot work (some are confident). Use direction + override + confirmation. Don't reopen the Tier/criterion decisions.
4. **Don't run more fine-tuning rounds** without a new frozen spec and new evidence (three rounds only relocated errors).
5. **Don't force one STT language globally**; don't judge STT by word error rate alone (digits-vs-words and "le"→"the" inflate it harmlessly).
6. Don't use `localhost` in the Spotify redirect; don't use librespot/spotifyd; don't keep Spotify tokens in browser storage; never commit or print secrets (tokens, API keys, HF token).
7. Don't show fake data (Figma's Wi-Fi/firmware/MAC, invented weather, invented now-playing).
8. Don't add frameworks, bundlers, glassmorphism/blur/translucent panels, or swipe navigation unless asked.
9. Don't block the asyncio event loop (model inference, HTTP, audio) and don't move alarm/timer logic into the page.
10. **Don't auto-execute destructive voice actions and never auto-confirm.**
11. Don't stream microphone audio to the cloud continuously; don't retain audio by default.
12. Don't rely on `wakepy` for Linux or `xset` on Wayland; don't assume X11.
13. Don't rewrite whole files when a targeted edit works; keep diffs reviewable.
14. Don't hard-code audio device indices; use names.
15. Don't change the meaning of `days` (0 = Monday … 6 = Sunday) or the existing WebSocket message names without updating Part B3 here.
16. Don't use `time.sleep` in async code, and don't spawn unbounded subagents (the owner's tooling has hard caps for good reason: runaway agent spawning is a documented way to burn money).

## G3. NOT WORTH DOING (now)
- The Figma's odometer scroll picker and swipe gestures (functionally equivalent tap UI exists).
- More router fine-tuning; optimising router latency (it is tens of ms; the cloud STT call dominates at ~300 ms).
- A long acoustic-echo-cancellation research project before the wake word works in a quiet room.
- On-device STT/LLM; LAN/tablet display support; Wi-Fi settings UI.
- OS supervision/autostart before the hardware and OS are chosen (a dev-time script is fine).
- Timer pause before it is requested; pixel-perfect polish before the voice pipeline works.
- Perfectly repairing weird code-switched transcripts with rules before measuring how often they matter.

---------------------------------------------------------------------------------------------------
# H. TESTING STRATEGY AND ACCEPTANCE CRITERIA

## H1. Layers (all proven in this project; reuse the patterns)
1. **Pure-logic unit tests**: slot-parser tables (EN/FR, with STT-damaged variants), Endpointer on synthetic signals (noise + speech bursts + clicks + saturation), WER/normalisation, `explain()`, resampling fidelity (a 440 Hz tone stays 440 Hz), override pinning.
2. **Fake-hardware integration tests**: a fake `sounddevice` module that feeds scripted audio blocks through the real recording code (including devices that accept only 48 kHz stereo); fake token endpoint for `spotify_auth` (PKCE challenge = S256(verifier), state mismatch rejected, HTML escaping, file mode 0600, refresh keeps the old refresh token, `invalid_grant` wipes only if unchanged, concurrent refresh = one call); fake WebSocket client against `handle_client`.
3. **UI behaviour tests in jsdom** (npm `jsdom` in a scratch folder): load the real `index.html` with a fake `WebSocket` and a fake `Spotify.Player`, push messages, click, assert DOM and what was sent. This caught real wiring bugs. Remember `input()`/other defaults bound at import time are not patched by monkeypatching builtins.
4. **Router evaluation**: `phase0_pipeline_test.py batch` on `held_out_eval`, then on real transcripts; always report the **direction split** (fallback→action vs action→fallback) and per-language numbers.
5. **Dry-run regression on WAV fixtures**: WAV → STT → router → parsed action, no side effects; compare with the manifest's expected category; store metrics in a dated results file and compare with the last one. (Calls the real Voxtral API, so it costs money and needs the key: keep a cached-transcript mode for offline CI.)
6. **Latency benchmarks**: per stage, p50/p90 over ≥ 30 runs, logged in a results file.
7. **Manual checklists on the real kiosk**: alarm after reboot, wake lock over a long idle period, Spotify after 24 h and after a Wi-Fi drop, microphone indicator, brightness schedule.

## H2. Habits that paid off
- Reproduce a bug against the OLD code first, then show the new code fixes it (the Spotify refresh race, the 12-hour stepper boundary bug, the saturated start-up frames).
- Add a test for every bug found; the test names should say what failed.
- Make a failing diagnostic self-explanatory (the "heard nothing" message now says whether the mic was saturated, too quiet, or the noise estimate was polluted).
- Treat your own test assertions as suspects when code looks right (twice an assertion was wrong, not the code): print the actual output before changing code.
- Keep the old and new versions comparable (same phrases, same seed) so a change in numbers means something.

## H3. Acceptance criteria summary [PROPOSED numbers; adjust once measured, then freeze them BEFORE the next run]
| area | criterion |
|---|---|
| alarms | fires within 1 s of the target; keeps ringing until dismissed (max 10 min); survives companion restart, reboot, DST change; works fully offline |
| STT | recorder-side misses < 3%; non-Latin outputs < 2% after the guard; p90 latency < 800 ms |
| router on real transcripts | ≥ 85% overall, ≥ 85% each for French and English; **0** fallback→action errors on the dangerous-phrase list |
| slot parser | ≥ 90% exact on the table, ≥ 80% on real transcripts |
| local voice action | end of speech → action done p90 < 1.2 s; alarms unaffected while a voice interaction runs |
| LLM fallback | first spoken audio p90 < 3 s |
| wake word | ≤ 1 false accept/hour quiet, ≤ 3/hour with TV; ≥ 90% detection at 2 m |
| Spotify | works after 24 h and 7 days without manual reconnect; transport controls < 500 ms perceived |
| ops | boot to clock unattended; kiosk recovers from a crash in < 10 s; 7-day soak with no memory growth beyond a stated bound |

---------------------------------------------------------------------------------------------------
# I. ENVIRONMENT, RUN COMMANDS, OPERATIONAL GOTCHAS

## I1. Python environment (uv-managed CPython 3.13)
```
pip install websockets numpy sounddevice wakepy mistralai          # companion + STT tools
pip install scipy                                                    # optional: better resampling
pip install torch --index-url https://download.pytorch.org/whl/cpu  # CPU-only torch (no CUDA wheels)
pip install laya --no-deps && pip install transformers safetensors huggingface_hub
export MISTRAL_API_KEY=...        # never paste or commit it
```
For UI tests: a scratch folder with `npm install jsdom` (Node is installed; do not commit `node_modules`).

## I2. Run commands
| what | command |
|---|---|
| static page | `python -m http.server 8000` then open `http://127.0.0.1:8000` |
| companion | `python companion.py` |
| kiosk | `chromium --kiosk --ozone-platform-hint=auto http://127.0.0.1:8000` (consider adding `--autoplay-policy=no-user-gesture-required` and test it) |
| Spotify login test | `python spotify_auth.py login` (then `devices`) |
| timer/alarm smoke test | `python test_companion.py` (needs the companion running) |
| mic level / right device | `python stt_session.py meter [--device NAME_OR_N]` |
| list audio devices | `python stt_session.py devices` |
| free-form STT | `python stt_session.py talk --device ...` |
| prompted STT session | `python stt_session.py script --n 40 --device ... --csv phase0/test_phrases_large.csv --save-audio rec2 --out stt_rec2.csv` |
| replay same audio | `python stt_session.py replay rec2 --lang auto\|en\|fr\|label --out r_x.csv` |
| compare result files | `python stt_session.py compare stt_rec2.csv r_label.csv r_fr.csv` |
| router on text | `python phase0_pipeline_test.py batch phase0_5/synthetic_dataset_raw.csv --split held_out_eval` |
| override test | `python test_override.py` |

## I3. Debug cheat-sheet
- Is the system-suspend inhibitor held? `systemd-inhibit --list` should show `NestClockOS` with mode `block` while the companion runs (this does NOT stop screen blanking).
- Does the page hold the screen wake lock? Browser console shows "Screen wake lock active" (and re-acquires after visibility changes).
- Audio input trouble: `python stt_session.py meter`; the PipeWire tools `wpctl status` / `wpctl get-volume @DEFAULT_AUDIO_SOURCE@` may help (WirePlumber; **[UNVERIFIED on this system]**); `pavucontrol` shows the active input port if installed.
- Router/override: `python phase0_pipeline_test.py batch ... --no-override` shows raw scores.

## I4. Gotchas collected the hard way
1. **Open the page at `http://127.0.0.1:8000`, not `localhost`.** `localStorage` is per-origin (the 24h preference resets when the origin changes) and the Spotify login returns to 127.0.0.1.
2. Changing the requested Spotify `SCOPES` forces exactly one re-login (by design). A day-plus gap once required a reconnect (cause unconfirmed; race fixed).
3. If port 8888 is busy (Jupyter uses it) login fails: pick another port AND update the redirect URI in the Spotify dashboard.
4. Only one companion can run (port 8765).
5. Audio device indices shift when devices appear/disappear; the first opening of an input stream may deliver full-scale garbage for ~0.3 s (handled in the Endpointer).
6. In Python, a default argument like `input_fn=input` binds at import time: monkeypatching `builtins.input` later does nothing (a test once hung forever for this reason). Inject dependencies explicitly.
7. Speaking right after Enter in push-to-talk inflates the noise floor and clips the first word; the ring-buffer capture in E2.2 removes this.
8. Timers that expired while the companion was down fire at startup (E0.6).
9. `wakepy` always reports "could not activate" on this machine (expected); `xset` does not exist on Wayland.
10. Checksums of downloaded files can differ from the author's (line endings, editor re-saves); use functional checks (`python stt_session.py -h` lists six commands; `grep` for the fix names).
11. A private Hugging Face repo needs a token to download once; never ask the owner to paste it in chat. Cache the model locally afterwards.
12. The Chromium startup errors listed in D4 are harmless.
13. The author's sandbox files (outside the owner's folder) can vanish between sessions; irrelevant for Claude Code, but it explains why every deliverable was re-delivered as a file.

## I5. Working with this owner
- Keylhan is a French-native engineering student (speaks English with a French accent), based in Paris, tinkering at an advanced level (RL training infrastructure, agents, Linux). He likes understanding the *why*; give a one-line reason with each recommendation. He often says "you decide": decide, state the reasoning and the alternative you rejected.
- He tests on his own machine and pastes terminal output or screenshots. Ask for the smallest useful output (a summary table, the last lines), never for secrets.
- He is on limited usage plans: keep chat replies short; do heavy work in the repo, not in prose.
- His tooling: Claude Code with the Superpowers skills and his own plugin **Zenno** (a Shield security layer, Agent Team orchestration with hard caps on depth/concurrency/total subagents, and "Ponytail" YAGNI/KISS/DRY discipline). Respect those caps; prefer one fresh subagent per well-defined task over long-lived contexts; for data/training work use a generator subagent and an independent verifier that is allowed to reject.
- He values calibrated honesty: say what is verified, what is a guess, what you could not check. Admitting a mistake plainly and fixing it is welcome; sycophancy is not.
- Preferences visible in decisions: no glassmorphism, rounded corners are fine, "UI/UX matters a lot", bilingual by default, 24-hour clock.

---------------------------------------------------------------------------------------------------
# J. OPEN QUESTIONS — ASK THE OWNER, DO NOT GUESS

1. **Final hardware**: budget, screen size, panel type (OLED vs LCD decides how seriously to treat burn-in), OS (Linux assumed), whether to add a USB speakerphone with echo cancellation, where it will sit (bedside, kitchen) and how far from the user.
2. **Wake word**: the phrase(s) ("Hey NestClock" appears in the Figma; "hey nest" appears in the data), and whether changing it periodically should be manual or automated.
3. **"Mets de la musique" with nothing to resume**: play Liked Songs? a default playlist? just say "pick something on your phone"?
4. **Reply language** when the user mixes languages (default French? follow the last utterance?).
5. **Spoken confirmations**: always, never, or only when information is returned?
6. **Weather**: city (Paris?), units, and what to show if the API fails.
7. **Alarms**: sound choice vs a Spotify wake-up playlist, snooze length, maximum ring time, behaviour when Spotify fails (keep the beep fallback).
8. **Auto-dim**: schedule, minimum brightness, any ambient-light sensor expectation.
9. **Privacy**: keep recordings for evaluation? how long? is the local voice log acceptable?
10. **LLM**: preferred Mistral model(s), monthly cost ceiling, reply style.
11. **Further router fine-tuning**: only if evidence appears; ask before proposing a new round.
12. **Time zone / DST**: assume Europe/Paris unless told otherwise.

---------------------------------------------------------------------------------------------------
# APPENDIX 1 — THE ROUTER (LAYA): HISTORY, NUMBERS, CRITERIA

## 1.1 What the router does
Input: a transcript. Output: one of `alarm | timer | music | weather | fallback` plus a calibrated confidence. It is only a **category** (no sub-action, no slots). `fallback` means "not a device command" (chat, questions, noise, unclear speech) and is what hands off to the LLM. Questions asked of the model are defined in `phase0_pipeline_test.py` (`ROUTING_QUESTIONS`): a `choice` question with 5 options and verbatim criteria texts, plus an `is_complete` question that was never trained.

## 1.2 Phase 0 — validating the idea on text (hand-written 125 phrases: 54 en / 54 fr / 17 mixed)
Chronology and what each step taught:
1. 30 phrases, 6 categories (alarm/timer/music/weather/general_chat/other): 73.3%. `general_chat` vs `other` are indistinguishable catch-alls → **collapsed into `fallback`**.
2. 5 categories: 83.3%. Volume phrases ("Turn up the volume", "Baisse le son") missed at very low confidence.
3. Rewording the `music` criterion to mention volume: **no change at all** (28/30 rows identical). Lesson: a bare phrase with no domain word is a sparse-signal problem, not a wording problem.
4. Forcing the `laya-typed-decisions` checkpoint: same 83.3%, different misses, compressed confidences. Not transferable. Rejected.
5-7. Confidence-gating analysis: one confident French miss ("Où en est le minuteur", 0.71) forced the "safe" threshold to 0.8, leaving only ~34% of traffic local. On the 125-phrase set overall accuracy was 75.2% (en 90.7%, fr 57.4%, mixed 82.4%). A single global threshold is not a viable design.
8-10. 20 of 54 French-labelled phrases were **misrouted to the English checkpoint** by Laya's built-in language heuristic; every one was plain-ASCII French with no accents. Accuracy by (label → checkpoint actually used): en→english 90.7%, fr→multilingual 61.8%, fr→english 50.0%, mixed→english 84.6%, mixed→multilingual 75.0%. Two stacked problems: misrouting, and a ~62% ceiling of the multilingual checkpoint on this task (consistent with Laya's own published MASSIVE-intent gap: 0.783 English vs 0.451 other languages).
Decisions: reject a global threshold; reject "send all French to the cloud" (French is the owner's majority language, that would defeat the local router); **fine-tune `laya-multilingual`** (not `typed-decisions`, whose backbone is English-only).

## 1.3 Phase 0.5 — fine-tuning (all artifacts in `phase0_5/`)
- **Method**: RLCD only (no SFT stage) — Laya's native training; the official recipe includes a soft cross-entropy guidance term inside the RL loss, which was kept. Single T4 (Colab), fp16. Hyperparameters in `train_single_t4.py`: 4 epochs, effective batch 64 (8×2×4), group size 4, LR 2.5e-5 / 1e-4, exploration σ 0.4 → 0.1, w_sph 0.75, a seed-fixed 200-item calibration holdout (stratified by language+category from run 2 on), per-question-type temperature fit afterwards. Run 1 trained in ~169 s on a T4.
- **Data** (`synthetic_dataset_raw.csv`, 2500 rows, `split` = train/held_out_eval): LLM-generated by one subagent, **independently verified** by a second that could reject (it did once: FAIL → fix → PASS); 500 per category; per split fr 45% / en 35% / mixed 20%; deliberately over-weighted clusters: French idioms (e.g. "où en est X"), volume commands, the fallback boundary, plain-ASCII French; zero exact/near duplicates, zero train/eval leakage. Later additions: run-2 augmentation of anchor-free phrasing (`synthetic_augment_*`), run-3 hard negatives teaching "describing music ≠ commanding it" (`synthetic_hardneg_*`, 40 rows) plus 10 relabels and 9 song-ID relabels → **final train set 2190 rows**.
- **Baselines on `held_out_eval` (n=500: fr 225 / en 175 / mixed 100)** — forced multilingual: en 81.1%, fr 56.0%, mixed 78.0%, overall 69.2%; dedicated english checkpoint on English: 84.0%; default Router overall 68.6% (en 84.0, fr 55.1, mixed 72.0).
- **Acceptance framework** (frozen before the runs, then revised twice with documented reasons): Tier 1 (ONE model for both languages): FR ≥ 85% and EN ≥ 82% (revised from 88% when the reference checkpoint measured 84.0% on this set, not 90.7% from the older hand-written set); ECE ≤ 0.15; the two failure clusters (French idioms, volume) each ≥ 80%; **gating criterion revised to be direction-based** (below).
- **Direction-based safety criterion** [DECIDED]: `fallback → action` (executes on something that should have been deferred) = dangerous, zero tolerance; `action → fallback` = fails safe (costs a cloud call, executes nothing) = a small documented residual is acceptable. Reason: the router sees only the coarse category, so destructive sub-actions are invisible to it, and confidence cannot remove confident errors.
- **Runs** (each: one run, report numbers, stop for a human decision):
| run | FR | EN | mixed | ECE | wrong at ≥0.5 | notes |
|---|---|---|---|---|---|---|
| 1 | 94.2% | 96.6% | 100% | 0.033 | 17 | blind spot: anchor words (bare "plus fort", "continue la lecture", "chrono"); uncalibrated holdout mix; eval label disputes |
| 2 | 98.7% | 97.7% | – | 0.037 | 7 (6 after one eval relabel) | targeted anchor-free data; clusters solved (idioms 25/25, volume 37/38); a regression ("humming that melody" → music) |
| 3 | 92.9% | 96.6% | – | 0.046 | 24 = **1 dangerous + 23 safe** | hard negatives fixed humming but over-generalised "declarative shape → fallback", swallowing French weather questions written in statement word order ("il pleut à Lyon") |
Decision after run 3 [DECIDED]: **ship run 3 + a deterministic override, no run 4.** Three rounds had only relocated errors.
- **The override** (in `classify()` of `phase0_pipeline_test.py`, pinned by `test_override.py`): a regex on the router output forces `fallback` at confidence 1.0 for the "speak up / parle plus fort / I can't hear you" family (the one remaining dangerous confusion: asking a person or the assistant to speak louder was read as "volume up", confidence 0.94). `--no-override` shows raw scores. If real transcripts reveal other dangerous phrasings, extend the override.
- **Accepted residuals** (all fail safe unless noted): ~23/500 French weather questions in statement word order → fallback (an extra cloud call); "continue la lecture"; "chrono"/"compteur" synonyms for minuteur; bare comparatives; the eval/train labelling of discourse-dependent phrases ("pick up where we left off") and song-ID questions ("who is this artist" → fallback) was settled in favour of `fallback`.
- **Checkpoint**: see D3 (lost once, reproduced from the documented recipe, pushed to a private HF repo). Read `phase0_5/CHECKPOINT_SHIP.md` for the loading cell and `post_training_results.md` for the exact numbers the reproduction reached; re-run `eval_finetuned.py` on the reproduced weights and record the direction split before building on it.

---------------------------------------------------------------------------------------------------
# APPENDIX 2 — SPEECH-TO-TEXT OBSERVATIONS (real voice, laptop mic, Voxtral `voxtral-mini-latest`)

## 2.1 Sessions and files
| session | file | settings | notes |
|---|---|---|---|
| run 1 | `stt_results.csv` | PipeWire `default` (device 6), language auto, 30 phrases recorded before the owner stopped | phrase 1 is INVALID (start-up glitch bug, since fixed) |
| run 2 | `stt_rec1_test.csv`, audio in `rec1/` | device 4 (indices had shifted), auto, 40 phrases (same phrases and order as run 1 because the default seed is the same) | 3 recorder misses (empty transcripts) |
| replays of run 2's audio | `r_label.csv`, `r_fr.csv` | `--lang label` and `--lang fr` | 38 rows each = 37 recordings + 1 duplicate row of phrase 1 (stale manifest entry, now prevented) |
| pending | `r_en.csv` | `--lang en` | to run (E1.1) |
Each `*_for_router.csv` holds the transcripts in the router-test schema.

## 2.2 Numbers (some are the script's own summaries; "my tally" = computed from pasted output)
- Latency (cloud call only): p50 ≈ 270-280 ms, p90 ≈ 320-460 ms; clips of 1-4 s.
- Run 1: ~20 of 29 valid attempts exact; 2 Russian outputs; 2 real mishears.
- Run 2 (script summary): ALL 25.7% mean WER, 50% exact, 3 empty; fr 26.3% (2 empty), en 23.0% (1 empty), mixed 29.9%.
- Same 37 recordings (my tally, duplicates removed): **auto 19.7% → language-told ("label") 17.1% → everything forced to French 22.6%**.
  English only: auto 17.1% → label 9.9% → forced French 32.5%. French only: unchanged by labelling (~18%). Mixed only: auto 29.9% → forced French 14.6%.
- Recorder-side misses in run 2: phrase 8 (soft voice, floor 0.0002, loudest 0.0419), phrases 27 and 34 (**room-noise estimate inflated to 0.0124 and 0.0095** versus ~0.0002 on good takes = the owner started speaking before the half-second pause).

## 2.3 Notable transcripts (what was said → what was heard)
- Language-ID failures (auto): "Raconte-moi une blague" → "Рассказывай мне одну блague."; "Snooze the alarm" → "Снузи, Рам."; "Lower the volume a bit" → "Лабораторный." (3 of ~67 clips; all short; two were English with a French accent, one was French). With the language told: "Lower the volume of it." (still imperfect but Latin and in the right language).
- Forced French on English is destructive: "Is it sunny outside" → "Est-ce que c'est une autre side ?"; "Set an alarm for 8:30" → "Zet een alarm voor 8.30." (Dutch); "Lower the volume a bit" → "Là où est le volume?".
- Forced French helps code-switching: "mets une alarme for 8am demain" → auto "Main alarm for 8 a.m. Demain." (bad) vs forced "Mets une alarme pour 8h demain." (good); "cancel le timer please" → "cancel le timer, please."
- Vocabulary drift: "minuteur" → "compteur" (×3) or "timer"; "Mets de la musique" → "Mais de la musique."; "Passe" → "Passez"; "relativité" → "réactivité" once; "Y a-t-il du vent" → "Est-il du vent".
- Number/time formatting: "8:30" → "8.30"; "2 minutes" → "deux minutes"/"two minutes"; "8am" → "8 a.m."; "ce weekend" → "ce week-end"; the slot parser must accept all of these.
- Persistent failures on the same core command across sessions and across language settings: "Lance un minuteur de 5 minutes" → "Non, 5 minutes et 5 minutes." (run 1), "Dans 5 minutes, il y a 2-5 minutes." (run 2 and both replays). Listen to `rec1/016.wav` before blaming the model: the push-to-talk recorder may have clipped the start.
- A dropped first word ("Will it snow tomorrow" → "it snow tomorrow.") appears identically in the live run and in the replays (same audio): a capture problem, not a transcription problem.

## 2.4 What this means (lessons, in order of importance)
1. Cloud STT is fast enough (~0.3 s) and mostly right on short commands; the category-bearing words usually survive even when the transcript is imperfect, so routing is likely more robust than word-error rate suggests (to be measured on real transcripts, E1/E2).
2. Language handling is the biggest controllable lever: don't force; guard against non-Latin output; consider dual-language candidates arbitrated by the router.
3. The capture design (ring buffer, noise estimate before the trigger) removes a whole class of self-inflicted errors (clipped first words, polluted noise floor).
4. Code-switched phrases are the weakest; the owner does use them ("mets une alarme for 8am demain"), so keep them in every evaluation.

---------------------------------------------------------------------------------------------------
# APPENDIX 3 — DESIGN SYSTEM (from the owner's Figma export, `Figma_design.pdf`)

## 3.1 Principles
Near-black, flat, monospace "firmware" look; the hero (clock) is neutral white, **amber is reserved for status/system chrome and interactive/active elements**; everything user-visible is bilingual. **No glassmorphism, no blur, no translucent panels** (explicit owner preference); rounded corners are welcome; subtle amber glow only on album art. Motion is functional only (colon blink, pulse on a fired alarm), and respects `prefers-reduced-motion`.

## 3.2 Tokens (as implemented in `index.html`)
`--bg #0a0a0a`, `--hero #f2f1ec`, `--amber #eea23e`, `--amber-dim #8a6a3a`, `--muted #6e6e6e`, `--card #111214`, `--border #23252b`. Font **JetBrains Mono** (400/500/700, Google Fonts) for everything. Hero clock: bold 700, `clamp(4.2rem, 16vw, 11rem)`, tabular numerals; seconds are not shown (the blinking colon shows it is alive).
Status lines: uppercase, letter-spacing .12em, amber. Dates: English line in hero colour, French line muted below (both always shown). Cards (sub-screens only): radius 20 px, `--card` background, 1 px `--border`. Buttons: `.btn-amber` (amber fill, dark text `#1a1305`, radius 14, uppercase, bold) and `.btn-outline`. Toggle switch, day chips with the English initial over the French initial (M/L, T/M, W/M, T/J, F/V, S/S, S/D), steppers with ∧/∨ chevrons.

## 3.3 Bilingual convention
Short labels: `ENGLISH · FRANÇAIS` joined with a middle dot (the Figma uses " / " in many places; the code uses " · "; stay consistent with the code). Longer text: English line then French line stacked. Never switch language by browser locale for display; both languages are always visible. Dates use `Intl.DateTimeFormat` with 'en-US' and 'fr-FR' explicitly.

## 3.4 Screens in the Figma and their status
| Figma screen | status |
|---|---|
| Home / clock (next alarm line, big clock + AM tag, EN + FR date, weather strip "-2°C PARIS · BRUMEUX / MISTY", "AUTO-DIM 12%", now-playing ticker) | clock, dates, alarm/timer/music status lines built; **weather strip and auto-dim line not built** (no real data yet) |
| Alarms list | built (list, toggle, delete, "+ NEW ALARM") |
| Set Alarm (odometer picker, repeat chips, label) | built with a stepper instead of the odometer |
| Timer Active (countdown, "OF/DE 20:00", Pause/Reset, swipe hint) | built without Pause; no swipe |
| Now Playing (art, title, amber artist, progress, prev/play/next, volume, Spotify badge) | built (no Spotify badge) |
| Weather Forecast (current, humidity/wind, 5-day, frost advisory card) | **not built** (4c/5) |
| Voice Assistant — listening (rings, "Listening… / À L'ÉCOUTE", ambient noise line) | **not built** (4e) |
| Voice Assistant — speaking (reply EN + FR, "USER: …" line) | **not built** (4e) |
| Settings (display, voice, language, connections, firmware/MAC, reboot) | **not built** (5; skip the fake fields) |
Also: a mini clock + Wi-Fi icon sits top-right on every sub-screen in the Figma; the code shows the clock only (no fake Wi-Fi status).

---------------------------------------------------------------------------------------------------
# APPENDIX 4 — FILE INVENTORY (what each file is and what to do with it)

## Project root
| file | what | action |
|---|---|---|
| `index.html` | the kiosk UI | modify (keep single file, no build) |
| `companion.py` | the service | modify |
| `spotify_auth.py` | Spotify PKCE login/tokens | modify carefully; keep its tests' behaviour |
| `stt_session.py` | Phase 4a CLI | verify version (B5.4); move shared logic into `voice/` later, keep the CLI |
| `phase0_pipeline_test.py` | router scorer + `classify()` + override | extend (e.g. `--model-dir` for the fine-tuned checkpoint); keep behaviour |
| `test_override.py` | pins the override | keep green |
| `test_companion.py` | timer smoke test over WebSocket | keep; extend |
| `llm_speed_test.py`, `llm_timings.csv` | unknown to the handoff author (probably LLM latency test for 4c) | read first |
| `Figma_design.pdf` | design reference | read-only |
| `companion_state.json` | runtime state | git-ignore |
| `spotify_tokens.json` | **secret**, mode 0600 | git-ignore, never print |
| `stt_results.csv` | run 1 results (phrase 1 invalid) | keep as evidence (consider moving to `results/`) |
| `stt_rec1_test.csv`, `stt_rec1_test_for_router.csv` | run 2 results | keep |
| `r_label.csv`, `r_fr.csv`, `*_for_router.csv` | replays of run 2 audio | keep |
| `stt_rec1.csv`, `stt_rec1_for_router.csv` | empty leftovers of an aborted run | delete |
| `rec1/` | run 2 audio + `manifest.csv` (has a stale duplicate row for 001.wav) | keep as fixtures; dedupe the manifest |
| `__pycache__/` | cache | delete/ignore |

## `phase0/`
`phase0_log.md` (the full Phase 0 story: read), `test_phrases.csv` (30 phrases, superseded), `test_phrases_large.csv` (125 hand-written phrases; used as STT prompts).

## `phase0_5/` (the fine-tuning project; the spec is frozen — add addenda, do not rewrite)
`phase0_5_finetune_spec.md` (spec + 4 addenda: READ), `baseline_results.md`, `post_training_results.md` (arc of runs + reproduction numbers: READ), `CHECKPOINT_SHIP.md` (provenance, loading, HF upload cell: READ), `COLAB_RUNBOOK.md` (how training/eval is run on Colab), `french_syntax_residual.md` (the accepted French residual and the scoped future fix), `prep_items.py`, `train_single_t4.py`, `eval_finetuned.py` (loading + scoring pattern to copy), `dump_errors.py`, `synthetic_gen_script.py` + `synthetic_dataset_raw.csv` + `synthetic_verification_report.md`, `synthetic_augment_*`, `synthetic_hardneg_*`, `run1_train_repro.csv` (reproduction of run 1 for diagnosis).

## `phase1/`
`phase1_design_notes.md` — the confirmation rule for destructive actions (the router cannot see sub-actions).

---------------------------------------------------------------------------------------------------
END OF HANDOFF. If this file and the code disagree, trust the code, then fix this file in the same commit.



