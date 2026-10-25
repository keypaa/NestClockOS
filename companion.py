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
import json
import platform
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import numpy as np
import sounddevice as sd
import websockets
from wakepy import keep

import spotify_auth

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
    sd.play(pattern, SAMPLE_RATE)


# ---------------------------------------------------------------------------
# State — companion is the source of truth, persisted to disk
# ---------------------------------------------------------------------------

class Store:
    def __init__(self):
        self.alarms = []  # [{id, hour, minute, days: [0-6], label, enabled}]
        self.timers = []  # [{id, ends_at, duration, label}]
        self.load()

    def load(self):
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text())
            self.alarms = data.get("alarms", [])
            self.timers = data.get("timers", [])

    def save(self):
        STATE_PATH.write_text(json.dumps(
            {"alarms": self.alarms, "timers": self.timers}, indent=2
        ))

    def as_message(self):
        return {"type": "state", "alarms": self.alarms, "timers": self.timers}


store = Store()
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
    fired_alarm_this_minute = set()

    while True:
        now = time.localtime()
        now_key = (now.tm_hour, now.tm_min)

        for alarm in store.alarms:
            if not alarm["enabled"]:
                continue
            if alarm["hour"] == now.tm_hour and alarm["minute"] == now.tm_min:
                if now.tm_wday not in alarm["days"]:
                    continue
                key = (alarm["id"], now_key)
                if key in fired_alarm_this_minute:
                    continue
                fired_alarm_this_minute.add(key)
                play_alarm_pattern()
                await broadcast({"type": "alarm_fired", "alarm": alarm})

        remaining_timers = []
        for timer in store.timers:
            if time.time() >= timer["ends_at"]:
                play_alarm_pattern()
                await broadcast({"type": "timer_fired", "timer": timer})
            else:
                remaining_timers.append(timer)
        if len(remaining_timers) != len(store.timers):
            store.timers = remaining_timers
            store.save()
            await broadcast(store.as_message())

        # keep the fired-this-minute set from growing forever
        if len(fired_alarm_this_minute) > 200:
            fired_alarm_this_minute = {k for k in fired_alarm_this_minute if k[1] == now_key}

        await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# WebSocket handling
# ---------------------------------------------------------------------------

spotify = spotify_auth.SpotifyAuth(
    on_connected=lambda: asyncio.ensure_future(
        broadcast({"type": "spotify_status", "connected": True})
    )
)


async def handle_client(websocket):
    clients.add(websocket)
    try:
        await websocket.send(json.dumps(store.as_message()))
        await websocket.send(json.dumps({"type": "spotify_status", "connected": spotify.connected}))
        async for raw in websocket:
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "set_alarm":
                alarm = {
                    "id": str(uuid.uuid4()),
                    "hour": msg["hour"],
                    "minute": msg["minute"],
                    "days": msg.get("days", [0, 1, 2, 3, 4, 5, 6]),
                    "label": msg.get("label", ""),
                    "enabled": True,
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

            elif action == "dismiss":
                sd.stop()

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
    print(f"NestClockOS companion service on ws://localhost:{PORT}")

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
            stop_linux_fallback()


if __name__ == "__main__":
    asyncio.run(main())