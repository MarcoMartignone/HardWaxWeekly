"""Release-level matching: find each Hard Wax release on Spotify as an album,
then add all its tracks to the playlist.

Strict policy: if we can't find the actual release on Spotify, we skip it
entirely. No guessing on individual tracks.

Reads scrape JSON from stdin (or arg path).
"""
import json
import os
import sys
from difflib import SequenceMatcher

from dotenv import load_dotenv

import spotify_client as sp

load_dotenv()

ARTIST_THRESHOLD = 0.7
ALBUM_THRESHOLD = 0.6


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_release(artist: str, title: str) -> dict | None:
    """Find Spotify album that matches a Hard Wax release.

    Returns the album dict or None. For Various Artists releases, only the
    album title needs to match.
    """
    candidates = sp.search_album(artist, title, limit=10)
    if not candidates:
        return None

    is_va = artist.lower() in ("various artists", "various people", "va")
    best = None
    best_score = -1.0
    for c in candidates:
        c_artists = ", ".join(a["name"] for a in c.get("artists", []))
        c_name = c.get("name", "")
        a_sim = 1.0 if is_va else similar(artist, c_artists)
        t_sim = similar(title, c_name)
        if a_sim < ARTIST_THRESHOLD or t_sim < ALBUM_THRESHOLD:
            continue
        score = a_sim + t_sim
        if score > best_score:
            best_score = score
            best = c
    return best


def load_releases(source: str | None) -> list[dict]:
    if source and source != "-":
        with open(source) as f:
            return json.load(f)
    return json.load(sys.stdin)


def main():
    playlist_id = os.getenv("SPOTIFY_PLAYLIST_ID", "").strip()
    if not playlist_id:
        print("ERROR: SPOTIFY_PLAYLIST_ID missing.", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1] if len(sys.argv) > 1 else None
    releases = load_releases(source)
    print(f"# {len(releases)} releases to process", file=sys.stderr)

    existing = sp.playlist_track_uris(playlist_id)
    print(f"# playlist already has {len(existing)} tracks", file=sys.stderr)

    to_add: list[str] = []
    seen: set[str] = set()
    matched: list[dict] = []
    unmatched: list[dict] = []

    for r in releases:
        artist = r.get("artist", "").strip()
        title = r.get("title", "").strip()
        if not artist or not title:
            continue
        if r.get("format", "").lower() in ("slipmat", "book"):
            print(f"  skip (non-music): {artist} — {title}", file=sys.stderr)
            continue
        album = match_release(artist, title)
        if not album:
            unmatched.append({"artist": artist, "title": title})
            print(f"  miss: {artist} — {title}", file=sys.stderr)
            continue
        tracks = sp.album_tracks(album["id"])
        new_uris = []
        for t in tracks:
            uri = t["uri"]
            if uri in existing or uri in seen:
                continue
            seen.add(uri)
            new_uris.append(uri)
            to_add.append(uri)
        matched.append({
            "artist": artist,
            "title": title,
            "matched_artist": ", ".join(a["name"] for a in album["artists"]),
            "matched_album": album["name"],
            "album_url": album["external_urls"]["spotify"],
            "added_track_count": len(new_uris),
            "total_track_count": len(tracks),
        })
        print(f"  match: {artist} — {title}  →  {album['name']}  (+{len(new_uris)} tracks)", file=sys.stderr)

    if to_add:
        sp.add_to_playlist(playlist_id, to_add)

    summary = {"matched": matched, "unmatched": unmatched, "tracks_added": len(to_add)}
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    print(f"\n# matched releases: {len(matched)}, unmatched: {len(unmatched)}, tracks added: {len(to_add)}", file=sys.stderr)


if __name__ == "__main__":
    main()
