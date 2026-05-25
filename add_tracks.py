"""Consume a JSON list of picks and add them to the configured playlist.

Picks JSON shape (stdin or arg-path):
    [
      {"artist": "Artist Name", "track": "Track Title", "reason": "..."},
      ...
    ]

Skips picks already in the playlist. Logs misses to stderr.
"""
import json
import os
import sys
from difflib import SequenceMatcher

from dotenv import load_dotenv

import spotify_client as sp

load_dotenv()

ARTIST_THRESHOLD = 0.7
TRACK_THRESHOLD = 0.7


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def best_match(artist: str, track: str) -> dict | None:
    """Require BOTH artist and track similarity above threshold.

    The previous averaging approach let perfect artist match cover for a
    totally different track name (e.g. Khotin/Resobeat → Khotin/Groove 32).
    """
    candidates = sp.search_track(artist, track, limit=5)
    if not candidates:
        return None
    best = None
    best_combined = -1.0
    for c in candidates:
        c_artist = ", ".join(a["name"] for a in c.get("artists", []))
        a_sim = similar(artist, c_artist)
        t_sim = similar(track, c["name"])
        if a_sim < ARTIST_THRESHOLD or t_sim < TRACK_THRESHOLD:
            continue
        combined = a_sim + t_sim
        if combined > best_combined:
            best_combined = combined
            best = c
    return best


def load_picks(source: str | None) -> list[dict]:
    if source and source != "-":
        with open(source) as f:
            return json.load(f)
    return json.load(sys.stdin)


def main():
    playlist_id = os.getenv("SPOTIFY_PLAYLIST_ID", "").strip()
    if not playlist_id:
        print("ERROR: SPOTIFY_PLAYLIST_ID missing. Run auth.py first.", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1] if len(sys.argv) > 1 else None
    picks = load_picks(source)
    print(f"# {len(picks)} picks to process", file=sys.stderr)

    existing = sp.playlist_track_uris(playlist_id)
    print(f"# playlist already has {len(existing)} tracks", file=sys.stderr)

    to_add: list[str] = []
    added: list[dict] = []
    missed: list[dict] = []

    for pick in picks:
        artist = pick.get("artist", "").strip()
        track = pick.get("track", "").strip()
        if not artist or not track:
            missed.append({**pick, "reason_miss": "empty artist/track"})
            continue
        match = best_match(artist, track)
        if not match:
            missed.append({**pick, "reason_miss": "no spotify match"})
            print(f"  miss: {artist} — {track}", file=sys.stderr)
            continue
        uri = match["uri"]
        if uri in existing or uri in to_add:
            print(f"  skip (already in playlist): {artist} — {track}", file=sys.stderr)
            continue
        to_add.append(uri)
        added.append({
            "artist": artist,
            "track": track,
            "matched_artist": ", ".join(a["name"] for a in match["artists"]),
            "matched_track": match["name"],
            "uri": uri,
            "url": match["external_urls"]["spotify"],
        })
        print(f"  add:  {artist} — {track}  →  {match['name']}", file=sys.stderr)

    if to_add:
        sp.add_to_playlist(playlist_id, to_add)

    summary = {"added": added, "missed": missed, "skipped_already_present": True}
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    print(f"\n# added {len(added)}, missed {len(missed)}", file=sys.stderr)


if __name__ == "__main__":
    main()
