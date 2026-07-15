#!/usr/bin/env python3
from __future__ import annotations
"""
IntegrationTest.py

Integration tests for every part of the HikeBuilder API that does NOT call Groq,
so they can be run as often as you like — no AI quota is consumed. This is the
suite you'd wire into CI and run on every push.

What it covers (all deterministic, DB- or code-backed):
  • Health/liveness/readiness endpoints and security response headers.
  • Hike reads + search: the difficulty filter actually filters, bad difficulty
    → 400, missing/ malformed ids → 404/422.
  • Item reads + a full self-cleaning CRUD cycle (create → read → patch → delete
    → 404). The create routes need no auth, and it deletes what it made, so it's
    safe to run repeatedly.
  • Auth gates: protected routes 401 without a token; notably POST /api/trip/chat
    401s *before* it ever reaches Groq, so the trip-planner's gate is testable
    for free.
  • Request-body size cap (413).
  • Authenticated reads (list trips, self user, ownership 403/404) — run when you
    provide --token, or let --register mint a throwaway account and clean it up.

USAGE
-----
    pip install requests

    python IntegrationTest.py --base-url http://localhost:8000
    python IntegrationTest.py --token <JWT> --user-id <uuid>
    python IntegrationTest.py --register        # auto-provision + delete a temp user
    python IntegrationTest.py --skip-write       # skip the item CRUD cycle
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

from _testkit import Client, Suite

try:
    import requests
except ImportError:
    sys.exit("Needs the 'requests' package: pip install requests")


DEFAULT_BASE_URL = os.environ.get("HIKEBUILDER_BASE_URL", "http://localhost:8000")
RANDOM_UUID = "00000000-0000-4000-8000-000000000000"  # well-formed, ~never a real row


# ── Health & security headers ──────────────────────────────────────────────

def check_health(c: Client, s: Suite) -> None:
    print("\n[health & headers]")
    r = c.get("/health")
    if s.expect_status(r, 200, "GET /health → 200"):
        ok, data = s.expect_json(r, "GET /health returns JSON")
        if ok:
            s.check("GET /health status == ok", data.get("status") == "ok", f"got {data}")

    r = c.get("/")
    s.expect_status(r, 200, "GET / (root) → 200")

    # Trip-chat router health — reachable without touching Groq.
    r = c.get("/api/trip/health")
    if s.expect_status(r, 200, "GET /api/trip/health → 200"):
        ok, data = s.expect_json(r, "GET /api/trip/health returns JSON")
        if ok:
            s.check("trip health reports status ok", data.get("status") == "ok", f"got {data}")

    # Readiness pings real dependencies; 503 just means a dependency is down —
    # report it, don't fail the suite over infra state.
    r = c.get("/health/ready")
    s.expect_status(r, {200, 503}, "GET /health/ready → 200 or 503")
    ok, data = s.expect_json(r, "GET /health/ready returns JSON")
    if ok and isinstance(data, dict):
        checks = data.get("checks", {})
        s.check("readiness reports database + redis", {"database", "redis"} <= set(checks), f"got {checks}")
        for dep, state in checks.items():
            if state != "ok":
                s.skip(f"dependency '{dep}' is {state}", "not a code failure — bring the dependency up")

    # Security headers are set by middleware on every response.
    r = c.get("/health")
    s.check("X-Content-Type-Options: nosniff",
            r.headers.get("X-Content-Type-Options") == "nosniff", r.headers.get("X-Content-Type-Options"))
    s.check("X-Frame-Options: DENY",
            r.headers.get("X-Frame-Options") == "DENY", r.headers.get("X-Frame-Options"))
    s.check("Referrer-Policy: no-referrer",
            r.headers.get("Referrer-Policy") == "no-referrer", r.headers.get("Referrer-Policy"))


# ── Hikes (public reads + search filter) ───────────────────────────────────

HIKE_KEYS = ["id", "name", "difficulty", "length_km", "geometry", "region"]


def check_hikes(c: Client, s: Suite) -> None:
    print("\n[hikes]")
    sample_id = None

    r = c.get("/hikes/list")
    if s.expect_status(r, 200, "GET /hikes/list → 200"):
        ok, data = s.expect_json(r, "GET /hikes/list returns JSON")
        if ok:
            if s.check("hikes list is an array", isinstance(data, list)) and data:
                s.expect_keys(data[0], HIKE_KEYS, "hike objects carry the expected keys")
                sample_id = data[0].get("id")

    # The real contract: difficulty= filters server-side. DB-backed + deterministic.
    r = c.get("/hikes/search", params={"difficulty": "EASY"})
    if s.expect_status(r, 200, "GET /hikes/search?difficulty=EASY → 200"):
        ok, data = s.expect_json(r, "search returns JSON")
        if ok and isinstance(data, list):
            bad = [h.get("difficulty") for h in data if h.get("difficulty") != "EASY"]
            s.check("every searched hike is EASY", not bad, f"non-EASY difficulties returned: {set(bad)}")

    # state is a second server-side filter (case-insensitive) — subset invariant.
    r = c.get("/hikes/search", params={"state": "NC"})
    if s.expect_status(r, 200, "GET /hikes/search?state=NC → 200"):
        ok, data = s.expect_json(r, "state search returns JSON")
        if ok and isinstance(data, list):
            bad = {(h.get("state") or "") for h in data if (h.get("state") or "").upper() != "NC"}
            s.check("every state=NC result is in NC", not bad, f"non-NC states returned: {bad}")

    # max_length_km must exclude longer trails — proves the filter isn't ignored.
    r = c.get("/hikes/search", params={"max_length_km": 5})
    if s.expect_status(r, 200, "GET /hikes/search?max_length_km=5 → 200"):
        ok, data = s.expect_json(r, "length search returns JSON")
        if ok and isinstance(data, list):
            over = [h.get("length_km") for h in data if (h.get("length_km") or 0) > 5]
            s.check("every max_length_km=5 result is <= 5km", not over, f"over-length returned: {over[:5]}")

    # The upper two DB tiers must be queryable too — this is what the frontend
    # filter fix now sends (it previously sent "HARD", which the DB never stores,
    # so the filter 400'd and Expert/Difficult trails were unreachable).
    for tier in ("DIFFICULT", "EXPERT"):
        r = c.get("/hikes/search", params={"difficulty": tier})
        if s.expect_status(r, 200, f"GET /hikes/search?difficulty={tier} → 200"):
            ok, data = s.expect_json(r, f"{tier} search returns JSON")
            if ok and isinstance(data, list):
                bad = [h.get("difficulty") for h in data if h.get("difficulty") != tier]
                s.check(f"every searched hike is {tier}", not bad, f"off-tier returned: {set(bad)}")

    # "HARD" is NOT a valid tier (DB stores DIFFICULT/EXPERT) — must 400, which is
    # exactly why the frontend was changed to stop sending it.
    r = c.get("/hikes/search", params={"difficulty": "HARD"})
    s.expect_status(r, 400, "GET /hikes/search?difficulty=HARD → 400 (not a DB tier)")

    r = c.get("/hikes/search", params={"difficulty": "NOT_A_LEVEL"})
    s.expect_status(r, 400, "GET /hikes/search?difficulty=NOT_A_LEVEL → 400")

    r = c.get(f"/hikes/get/{RANDOM_UUID}")
    s.expect_status(r, 404, "GET /hikes/get/<unknown uuid> → 404")

    r = c.get("/hikes/get/not-a-uuid")
    s.expect_status(r, 422, "GET /hikes/get/not-a-uuid → 422 (validation)")

    if sample_id:
        r = c.get(f"/hikes/get/{sample_id}")
        if s.expect_status(r, 200, "GET /hikes/get/<real id> → 200"):
            ok, data = s.expect_json(r, "single hike returns JSON")
            if ok:
                s.check("returned hike id matches request", data.get("id") == sample_id)


# ── Items (public reads + self-cleaning CRUD) ──────────────────────────────

def check_items(c: Client, s: Suite) -> None:
    print("\n[items]")
    r = c.get("/items/")
    if s.expect_status(r, 200, "GET /items/ → 200"):
        ok, data = s.expect_json(r, "GET /items/ returns JSON")
        if ok:
            s.check("items list is an array", isinstance(data, list))

    r = c.get(f"/items/{RANDOM_UUID}")
    s.expect_status(r, 404, "GET /items/<unknown uuid> → 404")


def check_item_crud(c: Client, s: Suite) -> None:
    """Create → read → patch image → delete → confirm 404. Item write routes now
    require an authenticated user (any logged-in user — items are user-editable),
    so `c` must carry a token. It removes what it makes, so it's repeatable +
    clean. Doubles as proof that a normal (non-admin) user CAN write items."""
    print("\n[item CRUD cycle]")
    item_id = None
    try:
        r = c.post("/items/backpacks", json={
            "name": "IntegrationTest Backpack", "weight": 1200, "cost": 199, "capacity_liters": 55,
        })
        if not s.expect_status(r, 200, "POST /items/backpacks → 200"):
            return
        ok, data = s.expect_json(r, "create returns JSON")
        if not ok:
            return
        item_id = data.get("id")
        s.check("created item has an id", bool(item_id))
        s.check("created item echoes capacity_liters", data.get("capacity_liters") == 55, f"got {data.get('capacity_liters')}")
        if not item_id:
            return

        r = c.get(f"/items/{item_id}")
        if s.expect_status(r, 200, "GET /items/<new id> → 200"):
            _, got = s.expect_json(r, "read returns JSON")
            if got:
                s.check("read-back name matches", got.get("name") == "IntegrationTest Backpack")

        r = c.patch(f"/items/{item_id}/image", json={"image_url": "https://example.com/x.png"})
        if s.expect_status(r, 200, "PATCH /items/<id>/image → 200"):
            _, got = s.expect_json(r, "patch returns JSON")
            if got:
                s.check("image_url updated", got.get("image_url") == "https://example.com/x.png")

        r = c.delete(f"/items/{item_id}")
        s.expect_status(r, 204, "DELETE /items/<id> → 204")

        r = c.get(f"/items/{item_id}")
        s.expect_status(r, 404, "GET /items/<deleted id> → 404")
        item_id = None
    finally:
        # Belt-and-suspenders cleanup if an assertion above bailed early.
        if item_id:
            try:
                c.delete(f"/items/{item_id}")
            except requests.RequestException:
                pass


# ── Auth gates (no Groq, unlimited) ────────────────────────────────────────

def check_auth_gates(c: Client, s: Suite) -> None:
    """Protected routes must reject an unauthenticated caller. Uses a tokenless
    client so it's independent of whatever --token was passed."""
    print("\n[auth gates]")
    anon = Client(c.base, token=None)

    r = anon.get("/trips/")
    s.expect_status(r, 401, "GET /trips/ without token → 401")

    r = anon.get(f"/users/{RANDOM_UUID}")
    s.expect_status(r, 401, "GET /users/<id> without token → 401")

    # The important one: the trip-planner's auth gate runs BEFORE Groq, so this
    # exercises it without spending any AI quota.
    r = anon.post("/api/trip/chat", json={"message": "hi"})
    s.expect_status(r, 401, "POST /api/trip/chat without token → 401 (gated before Groq)")

    # The inline gear-add endpoint writes to the user's kit — must be authed.
    r = anon.post("/api/trip/gear/add", params={"session_id": "nope"}, json={
        "category": "rain_gear", "gear_category": "shell", "name": "x", "level": "hardshell",
    })
    s.expect_status(r, 401, "POST /api/trip/gear/add without token → 401")

    # Catalog writes are no longer world-open. Item writes require *any* logged-in
    # user; hike writes require an admin — but both reject an anonymous caller.
    r = anon.post("/items/backpacks", json={
        "name": "anon-should-fail", "weight": 1, "cost": 1, "capacity_liters": 10,
    })
    s.expect_status(r, 401, "POST /items/backpacks without token → 401")

    r = anon.delete(f"/hikes/delete/{RANDOM_UUID}")
    s.expect_status(r, 401, "DELETE /hikes/delete/<id> without token → 401 (admin-gated)")


# ── Request body size cap ──────────────────────────────────────────────────

def check_body_cap(c: Client, s: Suite) -> None:
    print("\n[body size cap]")
    big = b'{"x":"' + b"a" * (1_100_000) + b'"}'  # > 1 MB default cap
    try:
        r = c.post("/hikes/create", data=big, headers={"Content-Type": "application/json"})
    except requests.RequestException as e:
        # A server that rejects the oversized body before reading it can close
        # the socket, surfacing as a connection reset instead of a clean 413.
        # That still proves the cap is active — the failure mode we're guarding
        # against is the body being *accepted* (a 200/4xx-validation response).
        s.ok("POST >1MB body rejected (connection closed on oversized body)", str(e)[:80])
        return
    s.expect_status(r, 413, "POST >1MB body → 413 (rejected before routing)")


# ── Authenticated reads ────────────────────────────────────────────────────

def check_authed(c: Client, s: Suite, user_id: str | None) -> None:
    print("\n[authenticated reads]")
    r = c.get("/trips/")
    if s.expect_status(r, 200, "GET /trips/ with token → 200"):
        ok, data = s.expect_json(r, "GET /trips/ returns JSON")
        if ok:
            s.check("trips list is an array", isinstance(data, list))

    # Ownership path: a well-formed but non-existent trip id → 404 (not 500).
    r = c.get(f"/trips/{RANDOM_UUID}")
    s.expect_status(r, 404, "GET /trips/<unknown id> with token → 404")

    if user_id:
        r = c.get(f"/users/{user_id}")
        if s.expect_status(r, 200, "GET /users/<self> → 200"):
            ok, data = s.expect_json(r, "self user returns JSON")
            if ok:
                s.check("hashed_password not exposed", "hashed_password" not in data)
                s.check("google_sub not exposed", "google_sub" not in data)

        r = c.get(f"/users/{RANDOM_UUID}")
        s.expect_status(r, 403, "GET /users/<other id> → 403 (self-only)")
    else:
        s.skip("self-user checks skipped", "no --user-id (and not auto-registered)")

    # A normal (non-admin) token must NOT be able to mutate the hike catalog —
    # that's the admin gate. 403 (authenticated but forbidden), not 401.
    r = c.delete(f"/hikes/delete/{RANDOM_UUID}")
    s.expect_status(r, 403, "DELETE /hikes/delete/<id> with non-admin token → 403")


# ── Admin-only hike writes (needs the seeded CI admin) ─────────────────────

VALID_HIKE_PAYLOAD = {
    "source_id": "itest-admin-hike",
    "name": "ITest Admin Hike",
    "geometry": {"type": "LineString", "coordinates": [[-82.0, 35.0], [-82.01, 35.01]]},
    "difficulty": "EASY",
    "length_km": 2.0,
    "elevation_gain_m": 100,
    "min_altitude_m": 200,
    "max_altitude_m": 300,
    "region": "Integration Test Region",
    "season_start_month": 1,
    "season_end_month": 12,
    "permits_required": False,
    "gear_requirements": [],
}


def check_admin_writes(base_url: str, s: Suite, admin_email: str, admin_pw: str) -> None:
    """Positive path: an admin CAN create + delete a hike. Self-cleaning (creates
    then deletes its own hike, never touching seed rows). SKIPs when the admin
    can't log in — e.g. running locally against a DB where the CI admin wasn't
    seeded — so it's only asserted where the seed ran."""
    print("\n[admin hike writes]")
    anon = Client(base_url, token=None)
    r = anon.post("/users/login", json={"email": admin_email, "password": admin_pw})
    if r.status_code != 200:
        s.skip("admin-write checks skipped", f"admin login → {r.status_code} (seed the CI admin to run these)")
        return
    admin = Client(base_url, token=r.json().get("access_token"))

    created_id = None
    try:
        r = admin.post("/hikes/create", json=VALID_HIKE_PAYLOAD)
        if not s.expect_status(r, 200, "POST /hikes/create with admin token → 200"):
            return
        ok, data = s.expect_json(r, "admin hike create returns JSON")
        if ok:
            created_id = data.get("id")
            s.check("created hike has an id", bool(created_id))
        if created_id:
            r = admin.delete(f"/hikes/delete/{created_id}")
            s.expect_status(r, 204, "DELETE /hikes/delete/<id> with admin token → 204")
            created_id = None
    finally:
        if created_id:
            try:
                admin.delete(f"/hikes/delete/{created_id}")
            except requests.RequestException:
                pass


# ── Optional throwaway account provisioning ────────────────────────────────

def provision_temp_user(base_url: str, s: Suite) -> tuple[str | None, str | None]:
    """Create a random user and log in. Returns (token, user_id) or (None, None).
    Caller is responsible for calling delete_temp_user afterwards."""
    anon = Client(base_url, token=None)
    email = f"itest+{uuid.uuid4().hex[:12]}@example.com"
    password = "integration-test-pw-123"
    r = anon.post("/users/", json={"email": email, "password": password, "name": "Integration Test"})
    if r.status_code not in (200, 201):
        s.skip("could not auto-provision a user", f"POST /users/ → {r.status_code}: {(r.text or '')[:120]}")
        return None, None
    r = anon.post("/users/login", json={"email": email, "password": password})
    if r.status_code != 200:
        s.skip("could not log in auto-provisioned user", f"POST /users/login → {r.status_code}")
        return None, None
    data = r.json()
    return data.get("access_token"), data.get("user_id")


def delete_temp_user(base_url: str, token: str, user_id: str) -> None:
    try:
        Client(base_url, token=token).delete(f"/users/{user_id}")
    except requests.RequestException:
        pass


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Non-Groq integration tests (unlimited, CI-friendly).")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--token", default=os.environ.get("HIKEBUILDER_AUTH_TOKEN", ""),
                    help="JWT for the authenticated-read checks")
    ap.add_argument("--user-id", default=None, help="Your user id, for the self-user check")
    ap.add_argument("--register", action="store_true",
                    help="Auto-create a throwaway user for the authed checks, then delete it")
    ap.add_argument("--skip-write", action="store_true", help="Skip the item CRUD cycle and body-cap POST")
    ap.add_argument("--admin-email", default="ci-admin@example.com",
                    help="Seeded admin email for the admin-write checks (default: the ci_seed.sql admin)")
    ap.add_argument("--admin-password", default="ci-admin-pw-12345",
                    help="Seeded admin password (default: the ci_seed.sql admin)")
    args = ap.parse_args()

    c = Client(args.base_url)
    s = Suite("IntegrationTest (non-Groq surface)")

    print(f"HikeBuilder integration tests — {datetime.now(timezone.utc).isoformat()}")
    print(f"Target: {args.base_url}")

    # Public / unauthenticated surface.
    check_health(c, s)
    check_hikes(c, s)
    check_items(c, s)

    # Resolve a token up front — item writes are now auth-gated, so the item CRUD
    # cycle needs one (it used to run anonymously).
    token, user_id = args.token or None, args.user_id
    temp = None
    if not token and args.register:
        token, user_id = provision_temp_user(args.base_url, s)
        if token:
            temp = (token, user_id)
    authed = Client(args.base_url, token=token) if token else None

    try:
        if not args.skip_write:
            if authed:
                check_item_crud(authed, s)
            else:
                s.skip("item CRUD cycle skipped", "item writes now need a token — pass --token or --register")
            check_body_cap(c, s)  # anonymous: 413 fires in middleware before auth

        check_auth_gates(c, s)

        if authed:
            check_authed(authed, s, user_id)
        else:
            s.skip("authenticated-read checks skipped", "pass --token or --register to run them")

        if not args.skip_write:
            check_admin_writes(args.base_url, s, args.admin_email, args.admin_password)
    finally:
        # Always remove an auto-provisioned user, even if a check above raised —
        # otherwise a mid-run error would leak a throwaway account each time.
        if temp:
            delete_temp_user(args.base_url, temp[0], temp[1])

    s.summary()
    sys.exit(s.exit_code())


if __name__ == "__main__":
    main()
