# Hard Wax Weekly → Spotify sync

Scrapes [hardwax.com/this-week](https://hardwax.com/this-week/), matches each release
to a Spotify album, and adds all tracks from matched releases to the **Hard Wax Weekly**
playlist. Releases without a clean Spotify album match are skipped — tracks are never guessed.

## Requires outbound internet access

This routine makes HTTPS requests to **hardwax.com** and the **Spotify API**
(`accounts.spotify.com`, `api.spotify.com`). When run as a Claude Code cloud routine,
the environment's **network policy must allow these hosts**.

A restrictive policy (no general internet access) makes the egress proxy return
`403 Forbidden` on CONNECT, and the routine cannot run — `scrape.py` and
`add_releases.py` detect this and exit with a clear `NETWORK POLICY DENIAL` message.
To fix, reconfigure the environment with a network policy that permits the hosts above.
See https://code.claude.com/docs/en/claude-code-on-the-web for policy options.

## One-time setup

1. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`.
3. `.venv/bin/python auth.py` — authorizes Spotify, creates the playlist, writes the
   refresh token and playlist ID to `.env`.

## Weekly run

```sh
.venv/bin/python scrape.py 1 > /tmp/releases.json 2> /tmp/scrape.log
.venv/bin/python add_releases.py /tmp/releases.json > /tmp/summary.json 2> /tmp/add.log
```

`summary.json` reports matched releases (with per-release `+N` track counts),
unmatched releases, and total tracks added.
