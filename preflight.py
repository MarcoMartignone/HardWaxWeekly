"""Preflight connectivity check for the weekly Hard Wax -> Spotify sync.

The sync needs outbound HTTPS to a few hosts. In sandboxed / policy-enforced
environments (e.g. Claude Code on the web) outbound egress may be denied by an
organization network policy, which surfaces as a "403 Forbidden" tunnel error
or a proxy ProxyError. When that happens the real scrape/match scripts fail
with a long stack trace that buries the actual problem.

Run this first. It probes each required host and, on failure, prints a short
actionable message and exits non-zero so the routine can stop early with a
clear reason instead of a traceback.

Usage:
    python preflight.py
"""
import sys

import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# Hosts the sync must reach, with a lightweight probe URL for each.
REQUIRED = [
    ("hardwax.com", "https://hardwax.com/this-week/", "scrape this week's releases"),
    ("accounts.spotify.com", "https://accounts.spotify.com/", "refresh the Spotify access token"),
    ("api.spotify.com", "https://api.spotify.com/v1/", "search albums and add tracks"),
]


def probe(url: str) -> tuple[bool, str]:
    """Return (reachable, detail). 'reachable' means the TCP/TLS tunnel opened
    and the host answered *something* — even a 401/404 counts, since that means
    egress is allowed. Only connection/proxy errors count as blocked."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        return True, f"HTTP {r.status_code}"
    except requests.exceptions.ProxyError as e:
        return False, f"egress proxy denied the connection ({_short(e)})"
    except requests.exceptions.ConnectionError as e:
        return False, f"could not connect ({_short(e)})"
    except requests.exceptions.RequestException as e:
        # Timeouts and the like: the host may be reachable but slow. Treat as a
        # soft warning rather than a hard block.
        return True, f"reachable but errored ({_short(e)})"


def _short(e: Exception) -> str:
    s = str(e)
    return (s[:140] + "...") if len(s) > 140 else s


def main() -> int:
    blocked = []
    for host, url, why in REQUIRED:
        ok, detail = probe(url)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {host}  ({why})  -> {detail}", file=sys.stderr)
        if not ok:
            blocked.append((host, detail))

    if blocked:
        print("", file=sys.stderr)
        print("PREFLIGHT FAILED: the network egress policy is blocking hosts the", file=sys.stderr)
        print("sync needs. This is an environment/policy issue, not a code bug —", file=sys.stderr)
        print("it cannot be routed around from inside the session.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Blocked host(s):", file=sys.stderr)
        for host, detail in blocked:
            print(f"  - {host}: {detail}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Fix: allow these hosts in the environment's network policy", file=sys.stderr)
        print("(Claude Code on the web -> environment settings), or run the", file=sys.stderr)
        print("routine in an environment with allowlisted/unrestricted egress:", file=sys.stderr)
        for host, _, _ in REQUIRED:
            print(f"  - {host}", file=sys.stderr)
        return 1

    print("PREFLIGHT OK: all required hosts reachable.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
