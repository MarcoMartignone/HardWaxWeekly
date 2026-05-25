"""Dumb keyword-based curator for local end-to-end testing.

Reads releases JSON from stdin (or arg file), reads taste.md, emits picks JSON.

The real curation in production is done by the Claude routine reasoning about
each release's editorial notes against taste.md. This script is just a sanity
check so you can run the whole pipeline locally before wiring up the routine.

Usage:
    python scrape.py | python curate_simple.py | python add_tracks.py
"""
import json
import re
import sys
from pathlib import Path

TASTE_PATH = Path(__file__).parent / "taste.md"


def load_taste() -> tuple[set[str], set[str]]:
    """Return (love_terms, avoid_terms) extracted from taste.md."""
    if not TASTE_PATH.exists():
        return set(), set()
    text = TASTE_PATH.read_text()
    love_section = re.search(r"## Genres I love(.*?)(?=^##|\Z)", text, re.S | re.M)
    avoid_section = re.search(r"## Genres to avoid(.*?)(?=^##|\Z)", text, re.S | re.M)
    artists_section = re.search(r"## Favorite artists.*?\n(.*?)(?=^##|\Z)", text, re.S | re.M)

    def terms(section_match) -> set[str]:
        if not section_match:
            return set()
        raw = section_match.group(1)
        raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
        parts = re.split(r"[,\n]", raw)
        return {p.strip().lower() for p in parts if p.strip() and not p.strip().startswith("#")}

    love = terms(love_section) | terms(artists_section)
    avoid = terms(avoid_section)
    return love, avoid


def score(release: dict, love: set[str], avoid: set[str]) -> tuple[int, str]:
    haystack = " ".join([
        release.get("artist", ""),
        release.get("title", ""),
        release.get("label", ""),
        release.get("notes", ""),
    ]).lower()
    s = 0
    reasons = []
    if release.get("tip"):
        s += 2
        reasons.append("staff tip")
    for term in love:
        if term and term in haystack:
            s += 2
            reasons.append(f"+{term}")
    for term in avoid:
        if term and term in haystack:
            s -= 3
            reasons.append(f"-{term}")
    return s, ", ".join(reasons) or "no signal"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src and src != "-":
        with open(src) as f:
            releases = json.load(f)
    else:
        releases = json.load(sys.stdin)

    love, avoid = load_taste()
    print(f"# love terms: {sorted(love)}", file=sys.stderr)
    print(f"# avoid terms: {sorted(avoid)}", file=sys.stderr)

    scored = []
    for r in releases:
        s, reason = score(r, love, avoid)
        scored.append((s, reason, r))
    scored.sort(key=lambda x: x[0], reverse=True)

    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    picks = []
    for s, reason, r in scored[:top_n]:
        if s <= 0:
            continue
        tracks = r.get("tracks") or []
        chosen = tracks[0] if tracks else {"name": r.get("title", "")}
        picks.append({
            "artist": r["artist"],
            "track": chosen["name"],
            "release": r.get("title", ""),
            "score": s,
            "reason": reason,
        })

    json.dump(picks, sys.stdout, indent=2, ensure_ascii=False)
    print(f"\n# picked {len(picks)} of {len(releases)}", file=sys.stderr)


if __name__ == "__main__":
    main()
