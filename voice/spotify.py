"""Minimal Spotify Web API playback helpers (uses companion's stored access token)."""
import json, urllib.request, urllib.error

BASE = "https://api.spotify.com/v1"


def _req(token, method, path, body=None):
    data = None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")}
    except Exception as e:
        return 0, {"error": str(e)}


def play_pause(token, play=True, device_id=None):
    path = "/me/player/play" if play else "/me/player/pause"
    if device_id:
        path += f"?device_id={device_id}"
    return _req(token, "PUT", path, {} if play else None)

def next_track(token, device_id=None):
    p = "/me/player/next" + (f"?device_id={device_id}" if device_id else "")
    return _req(token, "POST", p)

def previous_track(token, device_id=None):
    p = "/me/player/previous" + (f"?device_id={device_id}" if device_id else "")
    return _req(token, "POST", p)

def set_volume(token, percent, device_id=None):
    p = f"/me/player/volume?volume_percent={int(percent)}"
    if device_id:
        p += f"&device_id={device_id}"
    return _req(token, "PUT", p)

def get_device_id(token):
    code, body = _req(token, "GET", "/me/player/devices")
    devs = body.get("devices", []) if isinstance(body, dict) else []
    active = [d for d in devs if d.get("is_active")]
    pick = (active or devs or [{}])[0]
    return pick.get("id")
