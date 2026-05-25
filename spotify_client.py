"""Thin Spotify Web API client. Reads creds from .env."""
import base64
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

SCOPES = "playlist-modify-private playlist-modify-public playlist-read-private user-top-read user-library-read"

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

_access_token: Optional[str] = None
_access_token_expires_at: float = 0.0


def _basic_auth_header() -> dict:
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    return {"Authorization": "Basic " + base64.b64encode(creds).decode()}


def exchange_code_for_tokens(code: str) -> dict:
    r = requests.post(
        TOKEN_URL,
        headers=_basic_auth_header(),
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def refresh_access_token(refresh_token: str) -> dict:
    r = requests.post(
        TOKEN_URL,
        headers=_basic_auth_header(),
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_access_token() -> str:
    global _access_token, _access_token_expires_at
    if _access_token and time.time() < _access_token_expires_at - 60:
        return _access_token
    refresh = os.getenv("SPOTIFY_REFRESH_TOKEN", "")
    if not refresh:
        raise RuntimeError("SPOTIFY_REFRESH_TOKEN missing. Run: python auth.py")
    data = refresh_access_token(refresh)
    _access_token = data["access_token"]
    _access_token_expires_at = time.time() + int(data.get("expires_in", 3600))
    return _access_token


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


def me() -> dict:
    r = requests.get(f"{API}/me", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def search_track(artist: str, track: str, limit: int = 5) -> list[dict]:
    q = f'artist:"{artist}" track:"{track}"'
    r = requests.get(
        f"{API}/search",
        headers=_headers(),
        params={"q": q, "type": "track", "limit": limit},
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("tracks", {}).get("items", [])
    if items:
        return items
    r = requests.get(
        f"{API}/search",
        headers=_headers(),
        params={"q": f"{artist} {track}", "type": "track", "limit": limit},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("tracks", {}).get("items", [])


def search_album(artist: str, album: str, limit: int = 10) -> list[dict]:
    q = f'artist:"{artist}" album:"{album}"' if artist and artist.lower() != "various artists" else f'album:"{album}"'
    r = requests.get(
        f"{API}/search",
        headers=_headers(),
        params={"q": q, "type": "album", "limit": limit},
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("albums", {}).get("items", [])
    if items:
        return items
    fallback_q = f"{artist} {album}" if artist and artist.lower() != "various artists" else album
    r = requests.get(
        f"{API}/search",
        headers=_headers(),
        params={"q": fallback_q, "type": "album", "limit": limit},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("albums", {}).get("items", [])


def album_tracks(album_id: str) -> list[dict]:
    tracks: list[dict] = []
    url = f"{API}/albums/{album_id}/tracks"
    params = {"limit": 50}
    while url:
        r = requests.get(url, headers=_headers(), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        tracks.extend(data.get("items", []))
        url = data.get("next")
        params = None
    return tracks


def create_playlist(user_id: str, name: str, description: str = "", public: bool = False) -> dict:
    r = requests.post(
        f"{API}/users/{user_id}/playlists",
        headers=_headers(),
        json={"name": name, "description": description, "public": public},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def playlist_track_uris(playlist_id: str) -> set[str]:
    uris: set[str] = set()
    url = f"{API}/playlists/{playlist_id}/tracks"
    params = {"fields": "items(track(uri)),next", "limit": 100}
    while url:
        r = requests.get(url, headers=_headers(), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        for it in data.get("items", []):
            t = it.get("track") or {}
            uri = t.get("uri")
            if uri:
                uris.add(uri)
        url = data.get("next")
        params = None
    return uris


def add_to_playlist(playlist_id: str, uris: list[str]) -> None:
    for i in range(0, len(uris), 100):
        chunk = uris[i : i + 100]
        r = requests.post(
            f"{API}/playlists/{playlist_id}/tracks",
            headers=_headers(),
            json={"uris": chunk},
            timeout=30,
        )
        r.raise_for_status()


def remove_from_playlist(playlist_id: str, uris: list[str]) -> None:
    for i in range(0, len(uris), 100):
        chunk = uris[i : i + 100]
        r = requests.delete(
            f"{API}/playlists/{playlist_id}/tracks",
            headers=_headers(),
            json={"tracks": [{"uri": u} for u in chunk]},
            timeout=30,
        )
        r.raise_for_status()


def top_artists(limit: int = 20, time_range: str = "medium_term") -> list[dict]:
    r = requests.get(
        f"{API}/me/top/artists",
        headers=_headers(),
        params={"limit": limit, "time_range": time_range},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("items", [])
