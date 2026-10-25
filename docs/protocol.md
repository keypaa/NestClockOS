# NestClockOS Companion ↔ Page WebSocket Protocol

Transport: JSON over `ws://localhost:8765`. The companion is source of truth; the page
receives a full `state` on connect and on every change.

## Page → companion (actions)

- `set_alarm` `{hour, minute, days?:[], label?, once?, date?}`
  - `days` empty/missing → one-shot alarm (`once: true`)
  - `date` is ISO YYYY-MM-DD for one-shots
- `toggle_alarm` `{id}`
- `cancel_alarm` `{id}`
- `start_timer` `{seconds, label?}`
- `cancel_timer` `{id}`
- `dismiss` — stops ringer + speech playback, clears pending actions UI-side
- `set_language` `{language: "fr"|"en"}`
- `voice_listen` — triggers a push-to-talk capture (one utterance)
- `confirm` / `deny` `{id}` — resolve a destructive voice action
- `spotify_login`, `spotify_token`

## Companion → page (events)

- `state` `{alarms[], timers[], language}`
- `alarm_fired` `{alarm}`
- `timer_fired` `{timer}`
- `voice_status` `{status}` — `listening`, `thinking`, `busy`, or `error`
- `voice_state` `{state, transcript?}` — `listening|thinking|speaking|idle`
- `voice_result` `{transcript, language, en_text, fr_text, category, confidence, overridden, route_ms, audio_s, reply_language?, action_ok?, action_msg?, pending_id?, pending_prompt?, error?}`
- `voice_reply` `{text, language}` — LLM fallback answer (only when `NESTCLOCK_USE_LLM=1`)
- `voice_confirmed` `{ok, message}`
- `weather` `{data: {temp_c, wind_kmh, code, condition_en, condition_fr, lat, lon}}`
- `spotify_status` `{connected}`
- `spotify_auth_url` `{url}`
- `spotify_error` `{message}`
- `spotify_token` `{access_token}`
- `error` `{message}`

## Companion-owned state
- `companion_state.json`: alarms, timers, language (default `fr`)
- Robot picks first non-destructive path; destructive voice actions are confirmed before execution
