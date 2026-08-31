# Hard Wax Weekly → Spotify sync

Scrapes [hardwax.com/this-week](https://hardwax.com/this-week/), matches each
release to a Spotify album, and adds all tracks from cleanly-matched releases to
a Spotify playlist. Releases without a confident album match are skipped —
tracks are never guessed.

## Run

```sh
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

# Spotify credentials (see .env.example) — export or put in a .env file
export SPOTIFY_CLIENT_ID=...
export SPOTIFY_CLIENT_SECRET=...
export SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
export SPOTIFY_REFRESH_TOKEN=...
export SPOTIFY_PLAYLIST_ID=...

# 0. Preflight: verify required hosts are reachable (fails fast if not)
.venv/bin/python preflight.py

# 1. Scrape this week's releases (arg = number of pages)
.venv/bin/python scrape.py 1 > /tmp/releases.json 2> /tmp/scrape.log

# 2. Match on Spotify and add tracks
.venv/bin/python add_releases.py /tmp/releases.json > /tmp/summary.json 2> /tmp/add.log
```

`/tmp/summary.json` reports matched releases (with per-release added-track
counts), unmatched releases, and the total tracks added.

## Required network egress

The sync makes outbound HTTPS to these hosts. In a policy-enforced / sandboxed
environment (e.g. Claude Code on the web) they must be allowed by the
environment's network policy, or every run fails with a `403 Forbidden` /
`ProxyError` at the egress gateway:

- `hardwax.com` — scrape this week's releases
- `accounts.spotify.com` — refresh the Spotify access token
- `api.spotify.com` — search albums and add tracks

Run `preflight.py` first; it probes each host and prints an actionable message
(and exits non-zero) when egress is blocked, instead of failing later with a
stack trace buried in the scrape/match logs.
