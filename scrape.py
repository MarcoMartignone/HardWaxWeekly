"""Scrape hardwax.com/this-week/ and emit JSON of releases to stdout."""
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://hardwax.com"
START = f"{BASE}/this-week/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def fetch(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    except requests.exceptions.ProxyError as e:
        # In sandboxed/proxied environments the egress policy may block
        # hardwax.com (403 on CONNECT). This is not a code bug and cannot be
        # retried around — surface it clearly instead of a raw traceback.
        print(
            "ERROR: could not reach hardwax.com — the network egress proxy "
            "denied the connection (likely a 403 policy block). Allow "
            "hardwax.com in this environment's network policy and re-run.\n"
            f"  detail: {e}",
            file=sys.stderr,
        )
        sys.exit(2)
    r.raise_for_status()
    return r.text


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    releases = []

    for li in soup.select("li.workinfo, li.product, li[id^='product']"):
        rel = extract_release(li)
        if rel:
            releases.append(rel)

    if not releases:
        for li in soup.find_all("li"):
            if li.find("a", href=re.compile(r"^/act/")):
                rel = extract_release(li)
                if rel:
                    releases.append(rel)

    return releases


def extract_release(li) -> dict | None:
    artist_a = li.find("a", href=re.compile(r"^/act/"))
    if not artist_a:
        return None

    artist = artist_a.get_text(strip=True).rstrip(":")

    title = ""
    for sib in artist_a.next_siblings:
        text = (sib.string or "").strip() if hasattr(sib, "string") else str(sib).strip()
        if text:
            title = text.lstrip(":").strip()
            break
    if not title:
        h = li.find(["h2", "h3", "h4"])
        if h:
            title = h.get_text(" ", strip=True).replace(f"{artist}:", "").strip()

    label_a = li.find("a", href=re.compile(r"^/label/"))
    label = label_a.get_text(strip=True) if label_a else ""

    fmt = ""
    fmt_match = re.search(r"\b(Do 12\"|Do LP|12\"|LP|EP|7\"|10\"|MP3|AIFF|Slipmat|Book)\b", li.get_text())
    if fmt_match:
        fmt = fmt_match.group(1)

    full_text = li.get_text(" ", strip=True)
    notes = extract_notes(li, artist, title, label)

    is_tip = "Tip!" in full_text or "tip!" in full_text.lower()

    tracks = []
    for a in li.find_all("a", href=re.compile(r"media\.hardwax\.com/audio/")):
        name = " ".join(a.stripped_strings)
        name = re.sub(r"\s+", " ", name).strip()
        pos_match = re.search(r"_([A-Z]\d+)\.mp3", a["href"])
        pos = pos_match.group(1) if pos_match else ""
        if name:
            tracks.append({"position": pos, "name": name, "preview": a["href"]})

    product_id = ""
    add_a = li.find("a", href=re.compile(r"#add/\d+"))
    if add_a:
        m = re.search(r"#add/(\d+)", add_a["href"])
        if m:
            product_id = m.group(1)

    return {
        "product_id": product_id,
        "artist": artist,
        "title": title,
        "label": label,
        "format": fmt,
        "tip": is_tip,
        "notes": notes,
        "tracks": tracks,
    }


def extract_notes(li, artist: str, title: str, label: str) -> str:
    text = li.get_text("\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    skip_patterns = [
        re.compile(r"^\d+[.,]\d+\s*€"),
        re.compile(r"^€\s*\d"),
        re.compile(r"^(Do\s+)?(12\"|LP|EP|7\"|10\"|MP3|AIFF|Slipmat|Book)\b", re.I),
        re.compile(r"^add\b", re.I),
        re.compile(r"^\[\d+\]$"),
        re.compile(r"^Tip!?$", re.I),
    ]
    notes_lines = []
    for l in lines:
        if l.lower().startswith(artist.lower()):
            continue
        if title and l.lower() == title.lower():
            continue
        if label and l.lower() == label.lower():
            continue
        if any(p.match(l) for p in skip_patterns):
            continue
        if l.startswith(("A", "B", "C", "D")) and len(l) > 2 and l[1].isdigit():
            continue
        if re.match(r"^[A-D]\d", l):
            continue
        notes_lines.append(l)
        if len(" ".join(notes_lines)) > 400:
            break
    return " ".join(notes_lines).strip()


def main():
    all_releases = []
    url = START
    page = 1
    max_pages = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    while url and page <= max_pages:
        print(f"# fetching page {page}: {url}", file=sys.stderr)
        html = fetch(url)
        releases = parse_page(html)
        print(f"# parsed {len(releases)} releases", file=sys.stderr)
        all_releases.extend(releases)

        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.find("a", string=re.compile(r"next", re.I))
        if next_link and next_link.get("href"):
            url = BASE + next_link["href"] if next_link["href"].startswith("/") else next_link["href"]
            page += 1
            time.sleep(1)
        else:
            url = None

    json.dump(all_releases, sys.stdout, indent=2, ensure_ascii=False)
    print(f"\n# total: {len(all_releases)} releases", file=sys.stderr)


if __name__ == "__main__":
    main()
