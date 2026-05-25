"""One-time OAuth flow. Run once locally:

    python auth.py

Opens browser, captures the redirect, writes refresh token + playlist ID to .env.
Also creates the "Hard Wax Weekly" playlist on first run.
"""
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv

import spotify_client as sp

load_dotenv()

AUTH_URL = "https://accounts.spotify.com/authorize"
ENV_PATH = Path(__file__).parent / ".env"
PLAYLIST_NAME = "Hard Wax Weekly"
PLAYLIST_DESCRIPTION = "Curated weekly from hardwax.com/this-week — auto-updated."

_received_code: str | None = None
_received_state: str | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _received_code, _received_state
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        _received_code = qs.get("code", [None])[0]
        _received_state = qs.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = "Authorized. You can close this tab." if _received_code else "Auth failed."
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *args, **kwargs):
        pass


def upsert_env(updates: dict[str, str]) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()
    keys_seen = set()
    out: list[str] = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                keys_seen.add(key)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in keys_seen:
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def main():
    if not sp.CLIENT_ID or not sp.CLIENT_SECRET:
        print("ERROR: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET missing in .env.", file=sys.stderr)
        print("Copy .env.example to .env and fill them in first.", file=sys.stderr)
        sys.exit(1)

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": sp.CLIENT_ID,
        "response_type": "code",
        "redirect_uri": sp.REDIRECT_URI,
        "scope": sp.SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    server = HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    print("Opening browser for Spotify authorization...")
    print(f"If it doesn't open, visit:\n  {url}\n")
    webbrowser.open(url)

    while _received_code is None:
        pass
    server.shutdown()

    if _received_state != state:
        print("ERROR: state mismatch — possible CSRF, aborting.", file=sys.stderr)
        sys.exit(1)

    tokens = sp.exchange_code_for_tokens(_received_code)
    refresh = tokens.get("refresh_token")
    if not refresh:
        print(f"ERROR: no refresh_token in response: {tokens}", file=sys.stderr)
        sys.exit(1)

    upsert_env({"SPOTIFY_REFRESH_TOKEN": refresh})
    os.environ["SPOTIFY_REFRESH_TOKEN"] = refresh

    user = sp.me()
    print(f"Authorized as: {user['display_name']} ({user['id']})")

    existing_id = os.getenv("SPOTIFY_PLAYLIST_ID", "").strip()
    if existing_id:
        print(f"Playlist already configured: {existing_id}")
        return

    pl = sp.create_playlist(user["id"], PLAYLIST_NAME, PLAYLIST_DESCRIPTION, public=False)
    upsert_env({"SPOTIFY_PLAYLIST_ID": pl["id"]})
    print(f"Created playlist '{PLAYLIST_NAME}': {pl['external_urls']['spotify']}")
    print("\nAll set. Next: fill out taste.md, then run a sync.")


if __name__ == "__main__":
    main()
