"""Execute a parsed voice intent against the companion Store.

Synchronous actions (alarm, timer, time/date fallback) operate on the local
Store immediately. Async actions (music, weather) are executed via their own
functions so the companion's handle_voice stays a thin orchestrator.
"""
import asyncio
import time
import uuid


def try_execute(store, category, text, slots):
    """Execute a synchronous voice action against the local Store.

    Returns (action_ok, action_msg). Music and weather use async executors
    instead (see execute_music_action / execute_weather_action).
    """
    if category == "alarm" and slots and slots.get("hour") is not None:
        a = {
            "id": str(uuid.uuid4()),
            "hour": slots["hour"],
            "minute": slots["minute"],
            "days": [0, 1, 2, 3, 4, 5, 6] if not slots.get("once") else [],
            "label": text,
            "enabled": True,
            "once": bool(slots.get("once")),
            "date": slots.get("date"),
        }
        store.alarms.append(a)
        store.save()
        return True, f"alarm set {a['hour']:02d}:{a['minute']:02d}"
    if category == "timer" and slots and slots.get("seconds"):
        t = {
            "id": str(uuid.uuid4()),
            "duration": slots["seconds"],
            "ends_at": time.time() + slots["seconds"],
            "label": text,
        }
        store.timers.append(t)
        store.save()
        return True, f"timer set {slots['seconds']}s"
    if category == "fallback":
        low = text.lower()
        if any(w in low for w in ("heure", "time", "quelle heure")):
            import datetime
            return True, "time: " + datetime.datetime.now().strftime("%H:%M")
        if any(w in low for w in ("date", "jour", "day")):
            import datetime
            return True, "date: " + datetime.date.today().isoformat()
    return False, None


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


async def execute_music_action(token_provider, device_id, slots, last_volume):
    """Execute a Spotify playback action asynchronously.

    Args:
        token_provider: a callable returning a valid access token (or None)
        device_id: the Spotify device id from the browser SDK, or None
        slots: {"subintent": "play"|"pause"|"next"|"prev"|"vol_up"|"vol_down"}
        last_volume: current volume level (0-100)

    Returns:
        (action_ok, action_msg, new_volume, music_resumed_manually)
        music_resumed_manually is True when "pause" was the command (so the
        caller does NOT auto-resume any ducked music).
    """
    import voice.spotify as vspotify
    sub = slots.get("subintent", "play")
    music_ducked_manually = sub == "pause"
    token = await token_provider() if asyncio.iscoroutinefunction(token_provider) else token_provider()
    if not token:
        return False, "spotify not connected — open the music screen to connect", last_volume, music_ducked_manually
    async_loop = asyncio.get_event_loop()
    device = device_id or await async_loop.run_in_executor(None, vspotify.get_device_id, token)
    print(f"music: token ok, device={device!r} sub={sub} sdk_device_id={device_id!r}")
    if sub in ("vol_up", "vol_down"):
        target = min(100, last_volume + 10) if sub == "vol_up" else max(0, last_volume - 10)
        code, body = await async_loop.run_in_executor(None, vspotify.set_volume, token, target, device)
        if code in (200, 204):
            last_volume = target
        ok = code in (200, 204)
        msg = f"music {sub}" if ok else spotify_error_msg(code, body)
        return ok, msg, last_volume, music_ducked_manually
    # play / pause / next / prev
    fns = {
        "play": lambda dev: vspotify.play_pause(token, True, dev),
        "pause": lambda dev: vspotify.play_pause(token, False, dev),
        "next": lambda dev: vspotify.next_track(token, dev),
        "prev": lambda dev: vspotify.previous_track(token, dev),
    }
    code, body = await async_loop.run_in_executor(None, (lambda: fns[sub](device)))
    # retry on stale device_id
    _stale_retry = (code == 404) and isinstance(body, dict) and "not found" in str(body.get("error", "")).lower()
    if _stale_retry:
        fresh = await async_loop.run_in_executor(None, vspotify.get_device_id, token)
        print(f"music: device stale ({device!r}); retrying via fresh GET: {fresh!r}")
        if fresh and fresh != device:
            device = fresh
            code, body = await async_loop.run_in_executor(None, (lambda: fns[sub](device)))
            if code in (200, 201, 204):
                print("music: retry succeeded on", fresh)
    ok = code in (200, 201, 204)
    msg = f"music {sub}" if ok else spotify_error_msg(code, body)
    return ok, msg, last_volume, music_ducked_manually


async def execute_weather_action(fetcher, store_language):
    """Fetch current weather and return (weather_data, action_ok, action_msg)."""
    w = await asyncio.get_event_loop().run_in_executor(None, fetcher)
    public = {k: v for k, v in w.items() if not k.startswith("_")}
    lang = "fr" if store_language == "fr" else "en"
    msg = "weather: " + w.get(f"condition_{lang}", "") + f" {w['temp_c']}C"
    return public, True, msg


def is_destructive(category, text):
    low = text.lower()
    if category in ("alarm", "timer"):
        return any(w in low for w in ("annule", "cancel", "delete", "supprime", "remove", "efface"))
    return False


def cancel(store, category, text):
    from .slots import parse_alarm_time
    if category == "alarm":
        time_val = parse_alarm_time(text)
        if time_val:
            h, m = time_val
            before = len(store.alarms)
            store.alarms = [a for a in store.alarms if not (a.get("hour") == h and a.get("minute") == m)]
            removed = before - len(store.alarms)
        else:
            if store.alarms:
                store.alarms.pop()
                removed = 1
            else:
                removed = 0
        if removed:
            store.save()
            return True, f"cancelled {removed} alarm(s)"
        return False, "no matching alarm"
    if category == "timer":
        if store.timers:
            store.timers.pop() if not ("tous" in text.lower() or "all" in text.lower()) else store.timers.clear()
            store.save()
            return True, "timer cancelled"
        return False, "no timer"
    return False, None
