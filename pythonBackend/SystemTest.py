#!/usr/bin/env python3
from __future__ import annotations
"""
SystemTest.py

Integration runner for the HikeBuilder trip-chat endpoint (POST /api/trip/chat).

It replays multi-turn trip-planning conversations against a **running** server
and asserts the API contract on every turn — response shape, phase validity,
session stability, and the signal-token strip-before-return invariant. It does
NOT grade the LLM's content (which trail it picked, tag wording, etc.), because
that isn't deterministic and, on a free Groq tier, degrades or gets rate-limited
partway through a run.

FREE-TIER BEHAVIOUR (important)
-------------------------------
When the LLM is rate-limited or unavailable the backend returns 429 (quota/burst)
or 502 (Groq error). Those are NOT contract failures — the runner records them as
SKIP, stops hammering the LLM, and marks the remaining conversations skipped too.
So a run that dies halfway to a rate limit exits 0 (nothing FAILED), it just
covered less. Real failures (wrong shape, leaked signal token, 4xx/5xx that isn't
a known degradation, auth error) exit 1.

Conversations are general: the built-in set is a starting point, but you can
supply your own with --conversations conversations.json (a list of
{"name": str, "turns": [str, ...]} objects).

USAGE
-----
    pip install requests

    python SystemTest.py --base-url http://localhost:8000 --token <JWT>
    python SystemTest.py --test 4                 # run only conversation id 4
    python SystemTest.py --conversations mine.json
    python SystemTest.py --lat 35.7796 --lng -78.6382

AUTH
----
/api/trip/chat is gated by the AI quota guard (auth + per-account limits). Pass a
valid JWT via --token or HIKEBUILDER_AUTH_TOKEN. Without one every call 401s and
the run fails fast with a clear message.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from _testkit import (
    Client, Suite, TRIP_PHASES,
    degradation_reason, leaked_tokens,
)

try:
    import requests
except ImportError:
    sys.exit("Needs the 'requests' package: pip install requests")


# ── Defaults ───────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = os.environ.get("HIKEBUILDER_BASE_URL", "http://localhost:8000")
DEFAULT_TOKEN    = os.environ.get("HIKEBUILDER_AUTH_TOKEN", "")
DEFAULT_LAT      = 35.7796  # Raleigh, NC
DEFAULT_LNG      = -78.6382
CHAT_PATH        = "/api/trip/chat"


# ── Conversation definitions ───────────────────────────────────────────────

@dataclass
class Conversation:
    id: int
    name: str
    turns: list[str]


BUILTIN: list[Conversation] = [
    Conversation(1, "Waterfall hike in North Carolina",
                 ["Waterfall hike in North Carolina"]),
    Conversation(2, "Great views near Raleigh",
                 ["Great views near Raleigh"]),
    Conversation(3, "Summit hike, then location",
                 ["Summit hike", "In North Carolina"]),
    Conversation(4, "Easy ridge hike, 1-2 miles, then location",
                 ["Easy ridge hike, 1-2 miles", "In North Carolina"]),
    Conversation(5, "Easy lake hike in North Carolina",
                 ["Easy lake hike in North Carolina"]),
    Conversation(6, "Easy flat hike, nothing strenuous",
                 ["Easy flat hike, nothing strenuous"]),
    Conversation(7, "Challenging -> near me -> North Carolina",
                 ["Challenging hike, major elevation gain", "Near me", "In North Carolina"]),
    Conversation(8, "Short 2hr -> Charlotte -> NC -> Easy",
                 ["Short hike, 2 hours max", "Charlotte", "North Carolina", "Easy"]),
    Conversation(9, "Historic trails or ruins (multi-turn)",
                 ["Historic trails or ruins", "I haven't decided on difficulty yet",
                  "Just a day hike", "ok im waiting"]),
    Conversation(10, "Meadows and wildflowers",
                 ["Meadows and wildflowers in North Carolina"]),
    Conversation(11, "Summit hike, then NC abbreviation",
                 ["Summit hike", "NC"]),
]


def load_conversations(path: str) -> list[Conversation]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    convos = []
    for i, obj in enumerate(raw, 1):
        turns = obj["turns"] if isinstance(obj, dict) else obj
        name = obj.get("name", f"conversation {i}") if isinstance(obj, dict) else f"conversation {i}"
        convos.append(Conversation(i, name, list(turns)))
    return convos


# ── Per-turn contract assertions ───────────────────────────────────────────

REQUIRED_KEYS = ["session_id", "response", "phase", "plan", "advanced", "created", "hike_options"]


def assert_turn_contract(suite: Suite, label: str, data: dict, prev_session_id: str | None) -> str | None:
    """Runs every deterministic contract check on one successful chat turn.
    Returns the session_id to carry forward."""
    suite.expect_keys(data, REQUIRED_KEYS, f"{label}: response shape")

    sid = data.get("session_id")
    suite.check(f"{label}: session_id present", bool(sid),
                "response had no session_id")
    if prev_session_id is not None and sid is not None:
        suite.check(f"{label}: session_id stable across turns",
                    sid == prev_session_id, f"{prev_session_id} -> {sid}")

    phase = data.get("phase")
    suite.check(f"{label}: phase is a valid PHASES value",
                phase in TRIP_PHASES, f"got {phase!r}")

    text = data.get("response", "")
    suite.check(f"{label}: response is non-empty text",
                isinstance(text, str) and text.strip() != "", "empty response")

    # The core invariant: no internal signal token ever reaches the user.
    leaks = leaked_tokens(text if isinstance(text, str) else "")
    suite.check(f"{label}: no signal-token leak in response",
                not leaks, f"leaked {leaks}")

    opts = data.get("hike_options", [])
    if suite.check(f"{label}: hike_options is a list", isinstance(opts, list),
                   f"got {type(opts).__name__}") and opts:
        shape_ok = all(isinstance(o, dict) and "index" in o for o in opts)
        suite.check(f"{label}: hike_option cards carry a 1-based index", shape_ok,
                    "an option is missing its 'index' field")

    return sid or prev_session_id


# ── Conversation runner ────────────────────────────────────────────────────

def run_conversation(client: Client, suite: Suite, convo: Conversation,
                     lat: float, lng: float, delay: float,
                     transcript: list[str]) -> tuple[str, str]:
    """Returns (outcome, detail). outcome ∈ {ok, degraded, error}."""
    session_id: str | None = None
    label_base = f"Test {convo.id} ({convo.name})"
    transcript.append(f"=== {label_base} ===")

    for i, message in enumerate(convo.turns, 1):
        label = f"{label_base} turn {i}"
        payload = {"message": message, "session_id": session_id,
                   "user_lat": lat, "user_lng": lng}
        try:
            resp = client.post(CHAT_PATH, json=payload)
        except requests.RequestException as e:
            suite.fail(f"{label}: request failed", str(e))
            transcript.append(f'"{message}"\n[REQUEST FAILED: {e}]')
            return "error", str(e)

        # Free-tier degradation → SKIP the rest of this conversation.
        reason = degradation_reason(resp)
        if reason:
            suite.skip(f"{label}: LLM/dependency degraded, stopping conversation", reason)
            transcript.append(f'"{message}"\n[SKIPPED: {reason}]')
            return "degraded", reason

        if resp.status_code == 401:
            suite.fail(f"{label}: 401 Unauthorized", "chat needs a valid --token / HIKEBUILDER_AUTH_TOKEN")
            return "error", "unauthorized"

        if resp.status_code != 200:
            suite.fail(f"{label}: HTTP {resp.status_code}", (resp.text or "")[:300])
            transcript.append(f'"{message}"\n[HTTP {resp.status_code}]')
            return "error", f"http {resp.status_code}"

        ok, data = suite.expect_json(resp, f"{label}: JSON body")
        if not ok:
            return "error", "non-json"

        session_id = assert_turn_contract(suite, label, data, session_id)

        transcript.append(f'"{message}"\nTrail AI\n{data.get("response", "")}\n')
        if delay:
            time.sleep(delay)

    return "ok", ""


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Integration runner for /api/trip/chat with contract assertions.")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--token", default=DEFAULT_TOKEN, help="JWT (or set HIKEBUILDER_AUTH_TOKEN)")
    ap.add_argument("--conversations", help="Path to a JSON file of conversations to run instead of the built-ins")
    ap.add_argument("--lat", type=float, default=DEFAULT_LAT)
    ap.add_argument("--lng", type=float, default=DEFAULT_LNG)
    ap.add_argument("--test", type=int, default=None, help="Run only this conversation id")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="Seconds between turns (default 1.0, keeps you under the AI burst cap)")
    ap.add_argument("--out", default="hikebuilder_transcripts.txt", help="Where to save the transcript")
    args = ap.parse_args()

    if not args.token:
        print("WARNING: no --token given; /api/trip/chat will 401 and every conversation will fail.",
              file=sys.stderr)

    convos = load_conversations(args.conversations) if args.conversations else BUILTIN
    to_run = [c for c in convos if args.test is None or c.id == args.test]
    if not to_run:
        sys.exit(f"No conversation with id {args.test} (valid ids: {[c.id for c in convos]})")

    client = Client(args.base_url, token=args.token or None)
    suite = Suite("SystemTest (trip-chat contract)")
    transcript = [f"# HikeBuilder trip-chat run — {datetime.now(timezone.utc).isoformat()}", ""]

    print(f"Running {len(to_run)} conversation(s) against {args.base_url}{CHAT_PATH}\n")

    degraded_reason: str | None = None
    for convo in to_run:
        print(f"— Test {convo.id}: {convo.name}")
        if degraded_reason:
            # Once the LLM is rate-limited/unavailable, further calls just waste
            # quota — mark the rest skipped and move on.
            suite.skip(f"Test {convo.id} ({convo.name}): not run", degraded_reason)
            continue
        outcome, detail = run_conversation(client, suite, convo, args.lat, args.lng, args.delay, transcript)
        if outcome == "degraded":
            degraded_reason = detail
        elif outcome == "error" and detail == "unauthorized":
            break  # no point continuing without a working token

    suite.summary()

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(transcript))
        print(f"\nTranscript saved to {args.out}")
    except OSError as e:
        print(f"\n(could not save transcript: {e})", file=sys.stderr)

    sys.exit(suite.exit_code())


if __name__ == "__main__":
    main()
