"""
NestClockOS — Spotify auth (Authorization Code + PKCE), companion side.

The companion owns the login and the tokens, so later phases (voice control)
can call the Web API without going through the browser. Stdlib only.

Test it on its own, before any UI:
    python spotify_auth.py login     # approve in the browser, then lists Connect devices
    python spotify_auth.py devices   # reuse saved tokens, list Connect devices

Keep spotify_tokens.json out of git: the refresh token is a credential.
"""

import asyncio
import base64
import hashlib
import html
import http
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "ee662b5b41094040bb1a169fdd6cd0d0")
REDIRECT_HOST, REDIRECT_PORT = "127.0.0.1", 8888
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"  # must match the dashboard exactly
KIOSK_URL = os.environ.get("NESTCLOCK_URL", "http://127.0.0.1:8000/")
# user-read-email/private: listed by older SDK guides; kept so the browser player works. Drop later if unneeded.
SCOPES = ("streaming user-read-email user-read-private user-read-playback-state "
          "user-modify-playback-state user-read-currently-playing")
TOKEN_PATH = Path(__file__).parent / "spotify_tokens.json"
TOKEN_URL = "https://accounts.spotify.com/api/token"
LOGIN_TIMEOUT = 300  # seconds the callback listener stays open


def _post_form(data):
    """Blocking POST to the token endpoint. Raises RuntimeError on an HTTP error."""
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"token endpoint {e.code}: {e.read().decode(errors='replace')}") from None


def api_get(path, token):
    """Blocking GET on the Web API. Returns (status, parsed_json_or_text)."""
    req = urllib.request.Request(
        "https://api.spotify.com/v1" + path, headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


class SpotifyAuth:
    def __init__(self, on_connected=None):
        self.on_connected = on_connected  # plain callable, fired after a successful login
        self.tokens = self._load()
        self._pending = None
        self._refresh_lock = asyncio.Lock()  # one refresh at a time (refresh tokens may be single-use)

    # ---- storage ----

    def _load(self):
        try:
            return json.loads(TOKEN_PATH.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self):
        fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.tokens, f)
        os.chmod(TOKEN_PATH, 0o600)

    @property
    def connected(self):
        """Logged in AND granted every scope we currently ask for (old logins force a re-login)."""
        granted = set(self.tokens.get("scope", "").split())
        return bool(self.tokens.get("refresh_token")) and set(SCOPES.split()) <= granted

    # ---- tokens ----

    def _store(self, resp):
        self.tokens["access_token"] = resp["access_token"]
        self.tokens["expires_at"] = time.time() + resp["expires_in"]
        if resp.get("refresh_token"):  # a refresh response may omit it: keep the old one
            self.tokens["refresh_token"] = resp["refresh_token"]
        if resp.get("scope"):
            self.tokens["scope"] = resp["scope"]
        self._save()

    async def _refresh(self):
        used = self.tokens["refresh_token"]
        try:
            resp = await asyncio.to_thread(_post_form, {
                "grant_type": "refresh_token",
                "refresh_token": used,
                "client_id": CLIENT_ID,
            })
        except RuntimeError as e:
            print(f"Spotify: refresh failed ({e})")
            # revoked or expired for good: force a new login, unless a newer login replaced it meanwhile
            if "invalid_grant" in str(e) and self.tokens.get("refresh_token") == used:
                self.tokens = {}
                self._save()
            return
        except OSError as e:  # network blip: keep the tokens, try again next time
            print(f"Spotify: refresh failed, network problem ({e})")
            return
        self._store(resp)

    async def get_access_token(self):
        """A valid access token, refreshing if needed. None if not connected."""
        if not self.connected:
            return None
        if self._expiring():
            async with self._refresh_lock:
                if self.connected and self._expiring():  # another request may have refreshed while we waited
                    await self._refresh()
        if not self.connected or time.time() > self.tokens.get("expires_at", 0):
            return None
        return self.tokens["access_token"]

    def _expiring(self):
        return time.time() > self.tokens.get("expires_at", 0) - 60

    # ---- login ----

    async def begin_login(self):
        """Start the one-shot callback listener and return the Spotify authorize URL."""
        await self._stop_pending()
        verifier = secrets.token_urlsafe(64)  # 86 chars from [A-Za-z0-9-_], within 43-128
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        server = await asyncio.start_server(self._on_http, REDIRECT_HOST, REDIRECT_PORT)
        timer = asyncio.get_running_loop().call_later(
            LOGIN_TIMEOUT, lambda: asyncio.ensure_future(self._stop_pending()))
        self._pending = {"verifier": verifier, "state": state, "server": server, "timer": timer}
        return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        })

    async def _stop_pending(self):
        p, self._pending = self._pending, None
        if p:
            p["timer"].cancel()
            p["server"].close()

    async def _on_http(self, reader, writer):
        try:
            request_line = (await asyncio.wait_for(reader.readline(), 10)).decode(errors="replace")
            while (await asyncio.wait_for(reader.readline(), 10)).strip():
                pass  # skip the headers
            parts = request_line.split()
            url = urllib.parse.urlparse(parts[1] if len(parts) > 1 else "/")
            if url.path != "/callback":
                await self._respond(writer, 404, "Not found")
                return

            q = urllib.parse.parse_qs(url.query)
            pending = self._pending
            ok, msg = False, "Login failed."
            if not pending:
                msg = "No login in progress."
            elif not secrets.compare_digest(q.get("state", [""])[0], pending["state"]):
                msg = "State mismatch: login rejected."
            elif "error" in q:
                msg = f"Spotify said: {q['error'][0]}"
            elif "code" in q:
                try:
                    resp = await asyncio.to_thread(_post_form, {
                        "grant_type": "authorization_code",
                        "code": q["code"][0],
                        "redirect_uri": REDIRECT_URI,
                        "client_id": CLIENT_ID,
                        "code_verifier": pending["verifier"],
                    })
                    self._store(resp)
                    ok, msg = True, "Spotify connected. Returning to the clock..."
                except (RuntimeError, OSError) as e:
                    msg = f"Token exchange failed: {e}"

            await self._respond(writer, 200 if ok else 400, msg, redirect=ok)
            if ok:
                await self._stop_pending()
                if self.on_connected:
                    self.on_connected()
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()

    async def _respond(self, writer, status, msg, redirect=False):
        refresh = f'<meta http-equiv="refresh" content="2;url={KIOSK_URL}">' if redirect else ""
        body = (
            f"<!doctype html><meta charset=utf-8>{refresh}"
            "<body style='background:#0a0a0a;color:#f2f1ec;font-family:monospace;padding:3rem'>"
            f"{html.escape(msg)}</body>"
        ).encode()
        head = (
            f"HTTP/1.1 {status} {http.HTTPStatus(status).phrase}\r\n"
            f"Content-Type: text/html; charset=utf-8\r\nContent-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(head.encode() + body)
        await writer.drain()


# ---- CLI test harness ----

async def _print_devices(auth):
    token = await auth.get_access_token()
    if not token:
        print("Not connected. Run: python spotify_auth.py login")
        return
    status, body = await asyncio.to_thread(api_get, "/me/player/devices", token)
    print(f"GET /me/player/devices -> {status}")
    print(json.dumps(body, indent=2) if isinstance(body, (dict, list)) else body)


async def _cli(cmd):
    if cmd == "login":
        done = asyncio.Event()
        auth = SpotifyAuth(on_connected=done.set)
        url = await auth.begin_login()
        print("Approve access in your browser (opening it now):\n" + url)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        await asyncio.wait_for(done.wait(), LOGIN_TIMEOUT)
        print("Login OK, tokens saved to", TOKEN_PATH)
        await _print_devices(auth)
    elif cmd == "devices":
        await _print_devices(SpotifyAuth())
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(_cli(sys.argv[1] if len(sys.argv) > 1 else ""))