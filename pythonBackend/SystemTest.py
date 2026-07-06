#!/usr/bin/env python3
from __future__ import annotations
"""
run_hike_tests.py

Automated runner for the 10 HikeBuilder trip-chat regression tests.

Drives POST /api/trip/chat directly over HTTP and replays each test's full
multi-turn conversation, so you don't have to retype them through the
frontend every time.

This version is intentionally dumb: it does NOT check anything (no
difficulty/tag/ID/data-note verification, no cross-test consistency
checks). It just runs each conversation start to finish and prints/saves
the transcript. Each test starts a brand new session (session_id=None),
so tests never bleed into each other.

USAGE
-----
    pip install requests --break-system-packages   # if not already installed

    python run_hike_tests.py --base-url http://localhost:8000 --token <JWT>
    python run_hike_tests.py --test 4               # just re-run one test
    python run_hike_tests.py --lat 35.7796 --lng -78.6382

AUTH
----
/api/trip/chat is gated by get_current_user_id (Auth.authentication). This
script sends whatever token you give it as "Authorization: Bearer <token>"
by default. If your auth dependency expects something else (a cookie, a
different header/scheme), use --auth-header / --auth-scheme.

If the app mounts the trip router under a different prefix than the plain
APIRouter(prefix="/api/trip") default, override with --path.
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("Needs the 'requests' package: pip install requests --break-system-packages")


# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = os.environ.get("HIKEBUILDER_BASE_URL", "http://localhost:8000")
DEFAULT_TOKEN = os.environ.get("HIKEBUILDER_AUTH_TOKEN", "")
DEFAULT_LAT = 35.7796  # Raleigh, NC
DEFAULT_LNG = -78.6382
DEFAULT_PATH = "/api/trip/chat"


# ── Test definitions ───────────────────────────────────────────────────────
#
# Turn wording is taken verbatim from the QA report where it gave exact
# quotes. Test 3 and Test 9 only had a prose description of the turn
# sequence, so those turns are a best-effort reconstruction — tweak the
# strings below if you want an exact replay of the original session.

@dataclass
class Turn:
    message: str


@dataclass
class TestCase:
    id: int
    name: str
    turns: list[Turn]


TESTS: list[TestCase] = [
    TestCase(1, "Waterfall hike in North Carolina",
             [Turn("Waterfall hike in North Carolina")]),
    TestCase(2, "Great views near Raleigh",
             [Turn("Great views near Raleigh")]),
    TestCase(3, "Summit hike, then location",
             [Turn("Summit hike"), Turn("In North Carolina")]),
    TestCase(4, "Easy ridge hike, 1-2 miles, then location",
             [Turn("Easy ridge hike, 1-2 miles"), Turn("In North Carolina")]),
    TestCase(5, "Easy lake hike in North Carolina",
             [Turn("Easy lake hike in North Carolina")]),
    TestCase(6, "Easy flat hike, nothing strenuous",
             [Turn("Easy flat hike, nothing strenuous")]),
    TestCase(7, "Challenging hike -> near me -> North Carolina",
             [
                 Turn("Challenging hike, major elevation gain"),
                 Turn("Near me"),
                 Turn("In North Carolina"),
             ]),
    TestCase(8, "Short hike 2hr max -> Charlotte -> North Carolina -> Easy",
             [
                 Turn("Short hike, 2 hours max"),
                 Turn("Charlotte"),
                 Turn("North Carolina"),
                 Turn("Easy"),
             ]),
    TestCase(9, "Historic trails or ruins (multi-turn path)",
             [
                 Turn("Historic trails or ruins"),
                 Turn("I haven't decided on difficulty yet"),
                 Turn("Just a day hike"),
                 Turn("ok im waiting"),
             ]),
    TestCase(10, "Meadows and wildflowers",
             [Turn("Meadows and wildflowers in North Carolina")]),
    TestCase(11, "Summit hike, then location (NC abbreviation)",
             [Turn("Summit hike"), Turn("NC")]),
]


# ── HTTP client ────────────────────────────────────────────────────────────

class HikeBuilderClient:
    def __init__(self, base_url, path=DEFAULT_PATH, token=None,
                 auth_header="Authorization", auth_scheme="Bearer",
                 timeout=30):
        self.url = base_url.rstrip("/") + path
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        if token:
            self.headers[auth_header] = f"{auth_scheme} {token}".strip() if auth_scheme else token

    def chat(self, message, session_id=None, user_lat=None, user_lng=None):
        payload = {
            "message": message,
            "session_id": session_id,
            "user_lat": user_lat,
            "user_lng": user_lng,
        }
        return requests.post(self.url, headers=self.headers, json=payload, timeout=self.timeout)


# ── Test execution ─────────────────────────────────────────────────────────

def run_test(client: HikeBuilderClient, test: TestCase, lat, lng, delay=0.0) -> list[str]:
    """Runs one test as a brand-new, independent conversation and returns
    the printable transcript lines. Does not check or grade anything."""

    session_id = None  # fresh conversation every test
    lines = [f"=== Test {test.id}: {test.name} ==="]

    for turn in test.turns:
        try:
            resp = client.chat(turn.message, session_id=session_id, user_lat=lat, user_lng=lng)
        except requests.RequestException as e:
            lines.append(f'"{turn.message}"')
            lines.append(f"[REQUEST FAILED: {e}]")
            break

        if resp.status_code != 200:
            lines.append(f'"{turn.message}"')
            lines.append(f"[HTTP {resp.status_code}: {resp.text[:500]}]")
            break

        data = resp.json()
        session_id = data.get("session_id", session_id)
        ai_response = data.get("response", "")

        lines.append(f'"{turn.message}"')
        lines.append("Trail AI")
        lines.append(ai_response)
        lines.append("")

        if delay:
            time.sleep(delay)

    lines.append("")
    return lines


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Run all 10 HikeBuilder trip-chat regression tests (output only, no checks).")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--path", default=DEFAULT_PATH, help="Chat endpoint path (default /api/trip/chat)")
    ap.add_argument("--token", default=DEFAULT_TOKEN, help="Auth token (or set HIKEBUILDER_AUTH_TOKEN)")
    ap.add_argument("--auth-header", default="Authorization")
    ap.add_argument("--auth-scheme", default="Bearer")
    ap.add_argument("--lat", type=float, default=DEFAULT_LAT)
    ap.add_argument("--lng", type=float, default=DEFAULT_LNG)
    ap.add_argument("--test", type=int, default=None, help="Run only this test ID (1-10)")
    ap.add_argument("--delay", type=float, default=0.0, help="Seconds to sleep between turns")
    ap.add_argument("--out", default="hikebuilder_transcripts.txt", help="Where to save the plain-text transcript")
    args = ap.parse_args()

    if not args.token:
        print(
            "WARNING: no auth token given (--token or HIKEBUILDER_AUTH_TOKEN). "
            "If /api/trip/chat requires auth, every request will 401.",
            file=sys.stderr,
        )

    client = HikeBuilderClient(
        base_url=args.base_url,
        path=args.path,
        token=args.token,
        auth_header=args.auth_header,
        auth_scheme=args.auth_scheme,
    )

    tests_to_run = [t for t in TESTS if args.test is None or t.id == args.test]
    if not tests_to_run:
        sys.exit(f"No test with id {args.test} (valid: 1-{len(TESTS)})")

    all_lines = [f"# HikeBuilder test run — {datetime.now(timezone.utc).isoformat()}", ""]

    for test in tests_to_run:
        test_lines = run_test(client, test, args.lat, args.lng, delay=args.delay)
        for line in test_lines:
            print(line)
        all_lines.extend(test_lines)

    with open(args.out, "w") as f:
        f.write("\n".join(all_lines))
    print(f"\nTranscript saved to {args.out}")


if __name__ == "__main__":
    main()