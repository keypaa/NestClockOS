"""
NestClockOS — Phase 2: companion service.

Runs alongside the kiosk browser tab. Owns everything the browser can't
reliably do itself: keeping the display awake, playing audio, and holding
the source of truth for alarms/timers (so a browser reload never loses state).

Setup:
    pip install websockets wakepy sounddevice numpy

Run:
    python companion.py

The browser (index.html) connects to ws://localhost:8765 and:
  - receives a full "state" message on connect (current alarms + timers)
  - sends "set_alarm" / "cancel_alarm" / "start_timer" / "cancel_timer" / "dismiss"
  - receives "state" pushes whenever anything changes, and "alarm_fired" /
    "timer_fired" the instant something goes off
"""

import asyncio
import os
import json
import platform
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import numpy as np

import spotify_auth
from voice.router import RouterService
from voice.audio import MicCapture
from voice.stt import transcribe_parallel
from voice.llm import ask as ask_llm
from voice.tts import speak as speak_tts
from voice.reply import detect_reply_language
from voice.slots import parse_alarm_set, parse_timer_start, parse_music_subintent, parse_weather_query
import voice.spotify as vspotify
from voice.weather import fetch as fetch_weather
from voice.wakeword import run_loop as run_wake_loop
from voice.actions import try_execute, is_destructive, cancel
from stt_session import record_utterance, explain, make_client, SAMPLE_RATE

STATE_PATH = Path(__file__).parent / "companion_state.json"
PORT = 8765
SAMPLE_RATE = 44100


# ---------------------------------------------------------------------------
# Audio — synthesized beep, no asset files needed for this phase
# ---------------------------------------------------------------------------

def make_beep(freq=880.0, duration=0.35, volume=0.4):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    tone = np.sin(freq * 2 * np.pi * t)
    # short fade in/out to avoid clicks
    fade = int(SAMPLE_RATE * 0.02)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    return (tone * volume).astype(np.float32)


BEEP = make_beep()


def play_alarm_pattern():
    """Three beeps — distinct enough to notice, not so busy it's alarming."""
    pattern = np.concatenate([BEEP, np.zeros(int(SAMPLE_RATE * 0.15))] * 3)
    import sounddevice as sd
    sd.play(pattern, SAMPLE_RATE)


# ---------------------------------------------------------------------------
# Ringing — loops until dismissed or MAX_RING_SECONDS; owned by an asyncio task
# ---------------------------------------------------------------------------

MAX_RING_SECONDS = 600
TONE_MAP = {"default": 880.0, "soft": 660.0, "ping": 1046.5}
RAMP_SECONDS = 30
ALARM_VOLUME_START = 0.15
ALARM_VOLUME_END = 0.60
TIMER_VOLUME = 0.40


class AudioBackend:
    """Tiny interface so the ringer can be tested with a fake backend."""
    def play(self, samples, sample_rate=SAMPLE_RATE):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


class SoundDeviceBackend(AudioBackend):
    def play(self, samples, sample_rate=SAMPLE_RATE):
        import sounddevice as sd
        sd.play(samples, sample_rate)

    def stop(self):
        import sounddevice as sd
        sd.stop()


def make_beep_volume(volume, freq=880.0, duration=0.35):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    tone = np.sin(freq * 2 * np.pi * t)
    fade = int(SAMPLE_RATE * 0.02)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    return (tone * volume).astype(np.float32)


def make_burst(volume, pause=0.2, freq=880.0):
    beep = make_beep_volume(volume, freq=freq)
    gap = np.zeros(int(SAMPLE_RATE * pause), dtype=np.float32)
    return np.concatenate([beep, gap, beep, gap, beep, np.zeros(int(SAMPLE_RATE * 0.25))])


class Ringer:
    def __init__(self, backend=None, max_duration=MAX_RING_SECONDS):
        self.backend = backend or SoundDeviceBackend()
        self.max_duration = max_duration
        self._task = None
        self.active = False
        self._stop_event = None

    async def start(self, alarm=True, sound="default"):
        if self.active:
            # do not stack a second playback
            return
        self.active = True
        self._sound = sound
        self._stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run(alarm, sound))
        # attach done callback to reset state
        self._task.add_done_callback(self._done)

    async def _run(self, alarm, sound="default"):
        start = time.monotonic()
        freq = TONE_MAP.get(sound, 880.0)
        try:
            while not self._stop_event.is_set():
                elapsed = time.monotonic() - start
                if elapsed >= self.max_duration:
                    break
                if alarm:
                    frac = min(1.0, elapsed / RAMP_SECONDS)
                    volume = ALARM_VOLUME_START + (ALARM_VOLUME_END - ALARM_VOLUME_START) * frac
                else:
                    volume = TIMER_VOLUME
                samples = make_burst(volume, freq=freq)
                await asyncio.get_event_loop().run_in_executor(None, self.backend.play, samples, SAMPLE_RATE)
                burst_dur = len(samples) / SAMPLE_RATE
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=burst_dur)
                except asyncio.TimeoutError:
                    pass
        finally:
            await asyncio.get_event_loop().run_in_executor(None, self.backend.stop)

    def _done(self, _):

        self.active = False
        self._task = None
        self._stop_event = None

    def dismiss(self):
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self.backend.stop()

    async def wait(self):
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass


ringer = Ringer()


# ---------------------------------------------------------------------------
# State — companion is the source of truth, persisted to disk
# ---------------------------------------------------------------------------

class Store:
    def __init__(self):
        self.alarms = []  # [{id, hour, minute, days: [0-6], label, enabled}]
        self.timers = []  # [{id, ends_at, duration, label}]
        self.language = "fr"
        self.settings = {"brightness": 100, "dim_start": "22:00", "dim_end": "07:00",
                         "wake_word": False, "assistant_volume": 80, "ui_24h": True}
        self.load()

    def load(self):
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text())
            self.alarms = data.get("alarms", [])
            self.timers = data.get("timers", [])
            self.language = data.get("language", "fr")
            self.settings = {**self.settings, **data.get("settings", {})}

    def save(self):
        STATE_PATH.write_text(json.dumps(
            {"alarms": self.alarms, "timers": self.timers, "language": self.language,
             "settings": self.settings}, indent=2
        ))

    def as_message(self):
        return {"type": "state", "alarms": self.alarms, "timers": self.timers, "language": self.language, "settings": self.settings}


store = Store()
router_service = RouterService()
mic_capture = None
pending_actions = {}
voice_busy = False
spotify_device_id = None
mic_muted = False
last_volume = 60
weather_cache = None
mistral_client = None
try:
    mistral_client = make_client()
except Exception as e:
    print(f"Mistral: {e}")
clients = set()

_fallback_process = None


def linux_fallback_wake_lock():
    """
    Used only when wakepy can't activate (no GNOME D-Bus screensaver service
    found — common on minimal window manager setups). Two independent layers:

      1. systemd-inhibit — talks to systemd-logind directly, not any desktop
         environment's D-Bus service, so it works regardless of window
         manager as long as the system uses systemd. Blocks system-level
         suspend/idle.
      2. xset — X11-specific, disables the X server's own DPMS/screensaver
         timers directly. systemd-inhibit alone does not stop this, since
         screen blanking under X11 is a separate mechanism from system sleep.
         Silently skipped if not running under X11 (e.g. Wayland).
    """
    global _fallback_process

    if platform.system() != "Linux":
        print("Wake lock: no fallback available for this platform.")
        return

    if shutil.which("systemd-inhibit"):
        try:
            _fallback_process = subprocess.Popen([
                "systemd-inhibit",
                "--what=idle:sleep",
                "--who=NestClockOS",
                "--why=Kiosk display must stay awake",
                "--mode=block",
                "sleep", "infinity",
            ])
            print("Wake lock: systemd-inhibit active (blocks system suspend/idle).")
        except Exception as e:
            print(f"Wake lock: systemd-inhibit failed to start: {e}")
    else:
        print("Wake lock: systemd-inhibit not found on this system.")

    if shutil.which("xset"):
        result = subprocess.run(["xset", "s", "off"], capture_output=True)
        subprocess.run(["xset", "-dpms"], capture_output=True)
        if result.returncode == 0:
            print("Wake lock: xset screensaver/DPMS disabled (X11).")
        else:
            print("Wake lock: xset present but failed — likely not an X11 session (Wayland?).")
    else:
        print("Wake lock: xset not found — if this is Wayland, screen blanking may still "
              "occur depending on your compositor's own idle settings (sway/hyprland/etc. "
              "each need their own fix, not covered here yet).")


def stop_linux_fallback():
    if _fallback_process is not None:
        _fallback_process.terminate()


async def broadcast(message):
    if clients:
        payload = json.dumps(message)
        await asyncio.gather(*(c.send(payload) for c in clients), return_exceptions=True)


# ---------------------------------------------------------------------------
# Scheduler — checks once a second, fires alarms/timers, never double-fires
# ---------------------------------------------------------------------------

async def scheduler_loop():
    global weather_cache
    fired_this_minute = set()
    current_minute = None

    while True:
        now = time.localtime()
        now_key = (now.tm_hour, now.tm_min)
        if now_key != current_minute:
            fired_this_minute.clear()
            current_minute = now_key

        for alarm in list(store.alarms):
            if not alarm["enabled"]:
                continue
            if not (alarm["hour"] == now.tm_hour and alarm["minute"] == now.tm_min):
                continue
            once = bool(alarm.get("once"))
            date = alarm.get("date")
            if once and date:
                if date != time.strftime("%Y-%m-%d"):
                    continue
            elif not once:
                if now.tm_wday not in (alarm.get("days") or []):
                    continue
            # once without date fires on the next matching time (any day)
            if alarm["id"] in fired_this_minute:
                continue
            fired_this_minute.add(alarm["id"])
            await ringer.start(alarm=True, sound=alarm.get("sound", "default"))
            await broadcast({"type": "alarm_fired", "alarm": alarm})
            if alarm.get("spotify_playlist") and getattr(spotify, "connected", False):
                try:
                    token = await spotify.get_access_token()
                    device = vspotify.get_device_id(token) if token else None
                    await asyncio.get_event_loop().run_in_executor(None, vspotify.start_playback, token, alarm["spotify_playlist"], device)
                except Exception as e:
                    print("wake-to-spotify failed (beep continues):", e)
            if once:
                store.alarms = [a for a in store.alarms if a["id"] != alarm["id"]]
                store.save()
                await broadcast(store.as_message())

        now_ts = time.time()
        remaining_timers = []
        expired_fired = False
        for timer in list(store.timers):
            if timer.get("ends_at") is None:
                remaining_timers.append(timer)  # paused, keep
                continue  # paused
            if now_ts >= timer["ends_at"]:
                overdue = now_ts - timer["ends_at"]
                if overdue > 120:
                    print(f"Dropped expired timer {timer.get('id')} (overdue {overdue:.0f}s)")
                    expired_fired = True
                    continue
                await ringer.start(alarm=False)
                await broadcast({"type": "timer_fired", "timer": timer})
                expired_fired = True
            else:
                remaining_timers.append(timer)
        if len(remaining_timers) != len(store.timers):
            store.timers = remaining_timers
            store.save()
            await broadcast(store.as_message())

        # periodic weather broadcast (every 30 min from boot)
        ready = weather_cache is None or (time.time() - weather_cache.get("_ts", 0)) > 1800
        if ready:
            try:
                w = await asyncio.get_event_loop().run_in_executor(None, fetch_weather)
                w["_ts"] = time.time()
                weather_cache = w
                public = {k: v for k, v in w.items() if not k.startswith("_")}
                await broadcast({"type": "weather", "data": public})
            except Exception as e:
                print("weather poll error:", e)
                weather_cache = {"_ts": time.time()}

        await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# WebSocket handling
# ---------------------------------------------------------------------------

spotify = spotify_auth.SpotifyAuth(
    on_connected=lambda: asyncio.ensure_future(
        broadcast({"type": "spotify_status", "connected": True})
    )
)


def spotify_error_msg(code, body):
    """Map a Spotify playback HTTP result into a short human message."""
    msg = ""
    if isinstance(body, dict):
        err = body.get("error")
        msg = err.get("message", "") if isinstance(err, dict) else str(err or "")
    low = (msg or str(body or "")).lower()
    if code == 404 or "no active device" in low or "not found" in low:
        return "no spotify device active — open the music screen to connect"
    if code == 403 or "premium" in low:
        return "spotify premium required for playback control"
    if code == 401:
        return "spotify auth failed — reconnect on the music screen"
    return f"spotify error {code}: {str(msg)[:80]}"


async def handle_voice():
    try:
        """Push-to-talk capture: record, transcribe (P2), route, broadcast result."""
        global mistral_client
        if mistral_client is None:
            try:
                mistral_client = make_client()
            except Exception as e:
                await broadcast({"type": "voice_error", "message": str(e)})
                return
        def _capture():
            info = {}
            audio = mic_capture.capture_one(info=info) if mic_capture is not None else None
            if audio is None and mic_capture is None:
                # fallback to per-call capture
                audio = record_utterance(None, info=info)
            return audio, info
        global mic_muted, voice_busy, last_volume
        if mic_muted:
            print("voice: trigger ignored — mic is muted")
            await broadcast({"type": "voice_result", "transcript": "", "category": "fallback", "confidence": 0.0, "overridden": False, "error": "mic muted"})
            await broadcast({"type": "voice_state", "state": "idle"})
            return
        voice_busy = True
        await broadcast({"type": "voice_status", "status": "listening"})
        await broadcast({"type": "voice_state", "state": "listening"})
        # Duck background music before capturing speech (reduces mic self-echo).
        # Pause returns 200/204 only if something was playing; we resume after unless
        # the command itself asked for pause.
        duck_token = None
        duck_device = None
        music_ducked = False
        if os.environ.get("NESTCLOCK_DUCK_MUSIC", "1") == "1":
            try:
                _tok = await spotify.get_access_token()
                if _tok:
                    _dev = spotify_device_id or await asyncio.get_event_loop().run_in_executor(None, vspotify.get_device_id, _tok)
                    if _dev:
                        _code, _body = await asyncio.get_event_loop().run_in_executor(None, vspotify.play_pause, _tok, False, _dev)
                        if _code in (200, 204):
                            duck_token = _tok
                            duck_device = _dev
                            music_ducked = True
                            print("voice: ducked (paused) music before capture")
                        else:
                            print(f"voice: duck FAILED (code={_code}, device={_dev!r}, body={str(_body)[:120]})")
            except Exception as _e:
                print("voice: duck music failed:", _e)
        audio, info = await asyncio.get_event_loop().run_in_executor(None, _capture)
        if audio is None:
            print(f"voice: no command captured (peak={info.get('peak', 0):.3f}, "
                  f"threshold={info.get('threshold', 0):.3f}, {explain(info)})")
            await broadcast({"type": "voice_result", "transcript": "", "category": "fallback",
                             "confidence": 0.0, "overridden": False, "error": explain(info)})
            await broadcast({"type": "voice_state", "state": "idle"})
            return
        dur = len(audio) / 16000
        # P2 transcription (blocking, in executor)
        def _transcribe():
            return transcribe_parallel(mistral_client, audio)
        await broadcast({"type": "voice_state", "state": "thinking"})
        results = await asyncio.get_event_loop().run_in_executor(None, _transcribe)
        en = results.get("en", {}).get("text", "")
        fr = results.get("fr", {}).get("text", "")
        # Latin guard
        from voice.text import non_latin
        en_ok = (not non_latin(en)) and bool(en.strip())
        fr_ok = (not non_latin(fr)) and bool(fr.strip())
        # route both surviving transcripts
        best = None
        for lang, text in (("en", en), ("fr", fr)):
            if lang == "en" and not en_ok:
                continue
            if lang == "fr" and not fr_ok:
                continue
            r = await asyncio.get_event_loop().run_in_executor(None, router_service.route, text)
            r["lang"] = lang
            r["text"] = text
            if best is None or r["category_confidence"] > best["category_confidence"]:
                best = r
        if best is None:
            # fall back to whichever survived
            for lang, text in (("en", en), ("fr", fr)):
                if text.strip():
                    best = {"category": "fallback", "category_confidence": 0.0,
                            "overridden": False, "text": text, "lang": lang, "ms": 0.0}
                    break
        if best is None:
            await broadcast({"type": "voice_result", "transcript": "", "category": "fallback",
                             "confidence": 0.0, "overridden": False, "error": "no speech"})
            return
        action_ok, action_msg = False, None
        # Duck/pause music before capture (reduces mic self-echo). Restore unless the
        # command itself asked for pause.
        music_ducked = False
        duck_token = None
        duck_device = None
        requested_music_subintent = None
        # destructive actions require confirmation
        # optional LLM fallback for fallback routing
        if best["category"] == "fallback" and os.environ.get("NESTCLOCK_USE_LLM") == "1":
            await broadcast({"type": "voice_state", "state": "thinking"})
            reply = await asyncio.get_event_loop().run_in_executor(None, ask_llm, mistral_client, best["text"], detect_reply_language(best["text"], store.language))
            await broadcast({"type": "voice_reply", "text": reply, "language": detect_reply_language(best["text"], store.language)})
        if os.environ.get("NESTCLOCK_TTS") == "1" and reply:
            await broadcast({"type": "voice_state", "state": "speaking"})
            await asyncio.get_event_loop().run_in_executor(None, speak_tts, mistral_client, reply)

        if is_destructive(best["category"], best["text"]):
            import uuid as _u
            pid = str(_u.uuid4())
            pending_actions[pid] = (time.time(), best["category"], best["text"])
            cutoff = time.time() - 120
            for k in [k for k, v in pending_actions.items() if (isinstance(v, tuple) and len(v) == 3 and v[0] < cutoff)]:
                pending_actions.pop(k, None)
            await broadcast({"type": "voice_result",
                            "transcript": best["text"],
                            "language": best.get("lang", ""),
                            "en_text": en, "fr_text": fr,
                            "category": best["category"],
                            "confidence": best["category_confidence"],
                            "overridden": best["overridden"],
                            "route_ms": best.get("ms", 0.0),
                            "audio_s": round(dur, 2),
                            "reply_language": detect_reply_language(best["text"], default=store.language),
                            "action_ok": False,
                            "action_msg": "confirm?",
                            "pending_id": pid,
                            "pending_prompt": f"Confirm: {best['text']} ?"})
            return
        if best["category_confidence"] >= 0.5 or best["category"] == "fallback":
            slots = None
            if best["category"] == "alarm":
                slots = parse_alarm_set(best["text"])
            elif best["category"] == "timer":
                secs = parse_timer_start(best["text"])
                slots = {"seconds": secs} if secs else None
            elif best["category"] == "music":
                sub = parse_music_subintent(best["text"])
                slots = {"subintent": sub}
                requested_music_subintent = sub
                if sub == "pause":
                    # Do not auto-resume captured-ducked music when pausing was the point
                    music_ducked = False
                # Duck background music before recording speech so the microphone
                # doesn't capture the music itself (self-echo).
                try:
                    token = await spotify.get_access_token()
                    if not token:
                        action_ok, action_msg = False, "spotify not connected — open the music screen to connect"
                    else:
                        device = spotify_device_id or await asyncio.get_event_loop().run_in_executor(None, vspotify.get_device_id, token)
                        sub = slots["subintent"]
                        print(f"music: token ok, device={device!r} sub={sub} sdk_device_id={spotify_device_id!r}")
                        if sub in ("vol_up", "vol_down"):
                            target = min(100, last_volume + 10) if sub == "vol_up" else max(0, last_volume - 10)
                            code, body = await asyncio.get_event_loop().run_in_executor(
                                None, vspotify.set_volume, token, target, device)
                            if code in (200, 204):
                                last_volume = target
                        else:
                            fns = {
                                "play": lambda dev: vspotify.play_pause(token, True, dev),
                                "pause": lambda dev: vspotify.play_pause(token, False, dev),
                                "next": lambda dev: vspotify.next_track(token, dev),
                                "prev": lambda dev: vspotify.previous_track(token, dev),
                            }
                            code, body = await asyncio.get_event_loop().run_in_executor(None, (lambda: fns[sub](device)))
                            _stale_retry = (code == 404) and isinstance(body, dict) and "not found" in str(body.get("error", "")).lower()
                            if _stale_retry:
                                fresh = await asyncio.get_event_loop().run_in_executor(None, vspotify.get_device_id, token)
                                print(f"music: device stale ({device!r}); retrying via fresh GET: {fresh!r}")
                                if fresh and fresh != device:
                                    device = fresh
                                    code, body = await asyncio.get_event_loop().run_in_executor(None, (lambda: fns[sub](device)))
                                    if code in (200, 201, 204):
                                        print("music: retry succeeded on", fresh)
                            action_ok = code in (200, 201, 204)
                            action_msg = f"music {sub}" if action_ok else spotify_error_msg(code, body)
                except Exception as e:
                    action_ok, action_msg = False, f"spotify error: {e}"
                slots = None
            elif best["category"] == "weather":
                slots = parse_weather_query(best["text"])
                try:
                    w = await asyncio.get_event_loop().run_in_executor(None, fetch_weather)
                    public = {k: v for k, v in w.items() if not k.startswith("_")}
                    await broadcast({"type": "weather", "data": public})
                    action_ok = True
                    action_msg = "weather: " + w["condition_" + ("fr" if store.language == "fr" else "en")] + f" {w['temp_c']}C"
                    slots = None
                except Exception as e:
                    action_ok = False
                    action_msg = f"weather unavailable: {e}"
            elif best["category"] == "fallback":
                slots = {}
            if slots is not None:
                action_ok, action_msg = try_execute(store, best["category"], best["text"], slots)
            if action_ok:
                await broadcast(store.as_message())
        print(f"voice result: cat={best['category']} conf={best['category_confidence']:.2f} "
              f"audio={dur:.1f}s ok={action_ok} msg={action_msg!r} text={best['text']!r}")
        await broadcast({"type": "voice_result",
                        "transcript": best["text"],
                        "language": best.get("lang", ""),
                        "en_text": en, "fr_text": fr,
                        "category": best["category"],
                        "confidence": best["category_confidence"],
                        "overridden": best["overridden"],
                        "route_ms": best.get("ms", 0.0),
                        "audio_s": round(dur, 2),
                        "reply_language": detect_reply_language(best["text"]),
                        "action_ok": action_ok,
                        "action_msg": action_msg})
        await broadcast({"type": "voice_state", "state": "idle"})

    except Exception as e:
        voice_busy = False
        await broadcast({"type": "voice_state", "state": "error"})
        await broadcast({"type": "voice_result", "transcript": "", "category": "fallback", "confidence": 0.0, "overridden": False, "error": str(e)})
        print("voice error:", e)
    finally:
        if music_ducked and duck_token and duck_device:
            try:
                await asyncio.get_event_loop().run_in_executor(None, vspotify.play_pause, duck_token, True, duck_device)
                print("voice: resumed music after capture")
            except Exception as _e:
                print("voice: resume music failed:", _e)
        voice_busy = False

async def handle_client(websocket):
    clients.add(websocket)
    try:
        await websocket.send(json.dumps(store.as_message()))
        if weather_cache is not None and "_ts" in weather_cache:
            await websocket.send(json.dumps({"type": "weather", "data": {k: v for k, v in weather_cache.items() if not k.startswith("_")}}))
        await websocket.send(json.dumps({"type": "spotify_status", "connected": spotify.connected}))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    continue
            except (json.JSONDecodeError, ValueError):
                await websocket.send(json.dumps({"type": "error", "message": "invalid JSON"}))
                continue
            action = msg.get("action")
            if not isinstance(action, str):
                continue

            if action == "set_alarm":
                days = msg.get("days", [0, 1, 2, 3, 4, 5, 6])
                once = bool(msg.get("once", False)) or (len(days) == 0)
                alarm = {
                    "id": str(uuid.uuid4()),
                    "hour": msg["hour"],
                    "minute": msg["minute"],
                    "days": days,
                    "label": msg.get("label", ""),
                    "enabled": True,
                    "once": once,
                    "date": msg.get("date"),
                    "sound": msg.get("sound", "default"),
                    "spotify_playlist": msg.get("spotify_playlist"),
                }
                store.alarms.append(alarm)
                store.save()
                await broadcast(store.as_message())

            elif action == "toggle_alarm":
                for a in store.alarms:
                    if a["id"] == msg["id"]:
                        a["enabled"] = not a["enabled"]
                store.save()
                await broadcast(store.as_message())

            elif action == "cancel_alarm":
                store.alarms = [a for a in store.alarms if a["id"] != msg["id"]]
                store.save()
                await broadcast(store.as_message())

            elif action == "start_timer":
                timer = {
                    "id": str(uuid.uuid4()),
                    "duration": msg["seconds"],
                    "ends_at": time.time() + msg["seconds"],
                    "label": msg.get("label", ""),
                }
                store.timers.append(timer)
                store.save()
                await broadcast(store.as_message())

            elif action == "cancel_timer":
                store.timers = [t for t in store.timers if t["id"] != msg["id"]]
                store.save()
                await broadcast(store.as_message())

            elif action == "snooze":
                mins = int(msg.get("minutes", 9))
                store.alarms.append({
                    "id": str(uuid.uuid4()),
                    "hour": (time.localtime(time.time() + mins*60).tm_hour),
                    "minute": (time.localtime(time.time() + mins*60).tm_min),
                    "days": [],
                    "label": msg.get("label", "snooze"),
                    "enabled": True,
                    "once": True,
                    "date": time.strftime("%Y-%m-%d", time.localtime(time.time() + mins*60)),
                })
                store.save()
                await broadcast(store.as_message())

            elif action == "pause_timer":
                for t in store.timers:
                    if t["id"] == msg["id"] and "paused_remaining" not in t:
                        t["paused_remaining"] = max(0, t["ends_at"] - time.time())
                        t["ends_at"] = None
                store.save()
                await broadcast(store.as_message())

            elif action == "resume_timer":
                for t in store.timers:
                    if t["id"] == msg["id"] and t.get("ends_at") is None and "paused_remaining" in t:
                        t["ends_at"] = time.time() + t.pop("paused_remaining")
                store.save()
                await broadcast(store.as_message())

            elif action == "dismiss":
                ringer.dismiss()
                try:
                    import sounddevice as sd
                    sd.stop()
                except Exception:
                    pass

            elif action == "mic_mute":
                global mic_muted
                mic_muted = bool(msg.get("muted", False))
                await broadcast({"type": "mic_status", "muted": mic_muted})

            elif action == "voice_listen":
                global voice_busy
                if voice_busy:
                    await websocket.send(json.dumps({"type": "voice_status", "status": "busy"}))
                    continue
                voice_busy = True

                async def _run_voice():
                    global voice_busy
                    try:
                        await handle_voice()
                    finally:
                        voice_busy = False

                asyncio.ensure_future(_run_voice())

            elif action == "confirm":
                info = pending_actions.pop(msg.get("id"), None)
                if info is not None:
                    _, cat, text = info
                    ok, m = cancel(store, cat, text)
                    if ok:
                        await broadcast(store.as_message())
                    await broadcast({"type": "voice_confirmed", "ok": ok, "message": m})

            elif action == "deny":
                pending_actions.pop(msg.get("id"), None)

            elif action == "set_language":
                lang = msg.get("language", "fr")
                if lang in ("fr", "en"):
                    store.language = lang
                    store.save()
                    await broadcast(store.as_message())

            elif action == "set_settings":
                incoming = msg.get("settings", {})
                if isinstance(incoming, dict):
                    store.settings.update(incoming)
                    store.save()
                    await broadcast(store.as_message())

            elif action == "spotify_device":
                # page's Web Playback SDK reported its device id (set on 'ready')
                dev_id = msg.get("device_id")
                print(f"spotify: page reported Web Playback SDK device_id={dev_id!r}")
                spotify_device_id = dev_id

            elif action == "spotify_control":
                cmd = msg.get("cmd")
                token = spotify.get_access_token() if hasattr(spotify, "get_access_token") else None
                token = token if token else (await spotify.get_access_token())
                device = vspotify.get_device_id(token) if token else None
                if cmd == "play":
                    code, body = vspotify.play_pause(token, True, device)
                elif cmd == "pause":
                    code, body = vspotify.play_pause(token, False, device)
                elif cmd == "next":
                    code, body = vspotify.next_track(token, device)
                elif cmd == "prev":
                    code, body = vspotify.previous_track(token, device)
                elif cmd == "volume":
                    code, body = vspotify.set_volume(token, msg.get("value", 50), device)
                else:
                    code, body = 400, {"error": "unknown command"}
                await broadcast({"type": "spotify_control_result", "cmd": cmd, "code": code, "body": body})

            elif action == "spotify_login":
                try:
                    url = await spotify.begin_login()
                    await websocket.send(json.dumps({"type": "spotify_auth_url", "url": url}))
                except OSError as e:
                    await websocket.send(json.dumps({
                        "type": "spotify_error",
                        "message": f"Cannot open login listener on port {spotify_auth.REDIRECT_PORT}: {e}",
                    }))

            elif action == "spotify_token":
                token = await spotify.get_access_token()  # None when not connected
                await websocket.send(json.dumps({"type": "spotify_token", "access_token": token}))

    finally:
        clients.discard(websocket)


async def main():
    import websockets
    from wakepy import keep
    print(f"NestClockOS companion service on ws://localhost:{PORT}")

    global mic_capture
    print("Loading router (CPU)...")
    await asyncio.get_event_loop().run_in_executor(None, router_service.load)
    mc = MicCapture()
    try:
        await asyncio.get_event_loop().run_in_executor(None, mc.open)
        mic_capture = mc
        print("Mic stream open.")
        if os.environ.get("NESTCLOCK_WAKE_WORD") == "1":

            async def _wake():
                import asyncio
                loop = asyncio.get_event_loop()

                def _trigger():
                    global voice_busy
                    if voice_busy:
                        return
                    voice_busy = True
                    loop.call_soon_threadsafe(lambda: asyncio.ensure_future(handle_voice()))

                await loop.run_in_executor(None, run_wake_loop, mc, _trigger)
            asyncio.ensure_future(_wake())
    except Exception as e:
        print(f"Mic stream failed, using per-call capture: {e}")
        mic_capture = None

    with keep.presenting(on_fail="pass") as mode:  # we print our own explanation below
        if mode.active:
            print("Wake lock: active via wakepy.")
        else:
            print("Wake lock: wakepy could not activate (no GNOME D-Bus screensaver "
                  "service found — expected on minimal window manager setups).")
            linux_fallback_wake_lock()

        try:
            async with websockets.serve(handle_client, "localhost", PORT):
                await scheduler_loop()
        finally:
            if mic_capture is not None:
                mic_capture.close()
            stop_linux_fallback()


if __name__ == "__main__":
    asyncio.run(main())