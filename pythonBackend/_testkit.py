#!/usr/bin/env python3
"""
_testkit.py — shared HTTP + assertion harness for the HikeBuilder integration
tests (SystemTest.py and IntegrationTest.py).

No pytest, no extra deps beyond `requests`, matching this repo's "install deps
by hand, no requirements.txt" reality. It provides three things:

  • Client   — a thin requests wrapper that injects the bearer token + base URL.
  • Suite    — a PASS / FAIL / SKIP recorder with assertion helpers and an
               exit code (0 = no failures, 1 = at least one FAIL). CI-ready.
  • helpers  — signal-token leak detection + a free-tier degradation classifier.

THE ONE RULE every assertion here follows: check the CONTRACT (status code,
JSON shape, documented invariants), never the LLM's content quality. On a free
Groq tier the model's answers get worse or rate-limited partway through a run;
that must surface as SKIP, not FAIL, so a flaky/limited LLM never fails the
build. Anything that is DB- or code-backed (search filters, auth gates, token
stripping, response shape) is deterministic and *is* asserted.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

try:
    import requests
except ImportError:
    sys.exit("Needs the 'requests' package: pip install requests")

# Windows consoles default to cp1252, which can't encode characters like "→"
# and crashes on print(). Switch our streams to UTF-8 (which encodes everything)
# so test output never dies on a stray Unicode character.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ── Contract constants ─────────────────────────────────────────────────────

# Literal signal tokens TripChat is prompted to emit and MUST strip before
# returning `response` to the client (see TripChat.py module docstring, and the
# strip-before-return invariant in CLAUDE.md). If any of these leak into
# user-facing text it's a real regression — and it's checkable no matter how
# good or bad the underlying LLM answer is.
SIGNAL_TOKENS = [
    "DESTINATION RESET",
    "GEAR ADD:",
    "ADVANCE_PHASE",
    "SEARCH_REFINE",
    "SAVE CONFIRMED",
]

# TripSession.PHASES — the only legal values of ChatResponse.phase.
TRIP_PHASES = {"destination", "gear_review", "itinerary", "finalize"}

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


# ── HTTP client ────────────────────────────────────────────────────────────

class Client:
    """Thin requests.Session wrapper: fixed base URL, optional bearer token,
    default timeout. Returns raw requests.Response so callers assert on it."""

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 30):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def request(self, method: str, path: str, **kw) -> requests.Response:
        kw.setdefault("timeout", self.timeout)
        return self.session.request(method, self.base + path, **kw)

    def get(self, path, **kw):    return self.request("GET", path, **kw)
    def post(self, path, **kw):   return self.request("POST", path, **kw)
    def put(self, path, **kw):    return self.request("PUT", path, **kw)
    def patch(self, path, **kw):  return self.request("PATCH", path, **kw)
    def delete(self, path, **kw): return self.request("DELETE", path, **kw)


# ── Free-tier / dependency degradation ─────────────────────────────────────

def _detail(resp: requests.Response) -> str:
    try:
        d = resp.json().get("detail")
        if d:
            return str(d)
    except Exception:
        pass
    return (resp.text or "")[:200]


def degradation_reason(resp: requests.Response) -> str | None:
    """If this response reflects a runtime/dependency condition that should SKIP
    (not FAIL) — a rate-limited or unavailable LLM, or a down session store —
    return a human-readable reason. Otherwise None.

    These are the status codes the backend uses for exactly those conditions:
      429  AI quota / burst cap hit          (rate_limit.py)
      502  "AI service unavailable"          (Groq error or rate limit)
      503  "Session service unavailable"     (Redis / session store down)
    None of them mean the API contract is broken, so a test run treats them as
    "couldn't exercise this" rather than a failure.
    """
    code = resp.status_code
    if code == 429:
        return f"rate-limited (429) — AI quota/burst cap: {_detail(resp)}"
    if code == 502:
        return f"AI service unavailable (502) — Groq error or free-tier limit: {_detail(resp)}"
    if code == 503:
        return f"session store unavailable (503) — is Redis running? {_detail(resp)}"
    return None


def leaked_tokens(text: str | None) -> list[str]:
    """Signal tokens found in user-facing text (should always be empty)."""
    hay = text or ""
    return [t for t in SIGNAL_TOKENS if t in hay]


# ── Result recorder ────────────────────────────────────────────────────────

@dataclass
class Suite:
    """Accumulates PASS/FAIL/SKIP records, prints them live, and exposes an
    exit code. Assertion helpers return a bool so callers can branch (e.g. skip
    dependent checks when a precondition fails)."""

    name: str
    verbose: bool = True
    records: list[tuple[str, str, str]] = field(default_factory=list)  # (status, title, detail)

    # -- low level --
    def _add(self, status: str, title: str, detail: str = "") -> None:
        self.records.append((status, title, detail))
        if self.verbose:
            marker = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}[status]
            line = f"  [{marker}] {title}"
            if detail:
                line += f"  — {detail}"
            print(line)

    def ok(self, title: str, detail: str = "") -> bool:
        self._add(PASS, title, detail); return True

    def fail(self, title: str, detail: str = "") -> bool:
        self._add(FAIL, title, detail); return False

    def skip(self, title: str, detail: str = "") -> None:
        self._add(SKIP, title, detail)

    # -- assertion helpers (each returns True on pass) --
    def check(self, title: str, condition: bool, detail: str = "") -> bool:
        return self.ok(title) if condition else self.fail(title, detail)

    def expect_status(self, resp: requests.Response, expected, title: str) -> bool:
        """expected is an int or a set/tuple of acceptable codes."""
        allowed = {expected} if isinstance(expected, int) else set(expected)
        if resp.status_code in allowed:
            return self.ok(title)
        return self.fail(title, f"expected {sorted(allowed)}, got {resp.status_code}: {_detail(resp)}")

    def expect_json(self, resp: requests.Response, title: str):
        """Returns (ok, parsed_or_None)."""
        try:
            return True, resp.json()
        except ValueError:
            self.fail(title, f"body was not JSON: {(resp.text or '')[:120]}")
            return False, None

    def expect_keys(self, data, keys, title: str) -> bool:
        if not isinstance(data, dict):
            return self.fail(title, f"expected an object, got {type(data).__name__}")
        missing = [k for k in keys if k not in data]
        if missing:
            return self.fail(title, f"missing keys: {missing}")
        return self.ok(title)

    # -- reporting --
    @property
    def counts(self) -> dict[str, int]:
        c = {PASS: 0, FAIL: 0, SKIP: 0}
        for status, _, _ in self.records:
            c[status] += 1
        return c

    @property
    def failed(self) -> int:
        return self.counts[FAIL]

    def summary(self) -> None:
        c = self.counts
        print(f"\n{self.name}: {c[PASS]} passed, {c[FAIL]} failed, {c[SKIP]} skipped")
        if c[FAIL]:
            print("  Failures:")
            for status, title, detail in self.records:
                if status == FAIL:
                    print(f"    - {title}" + (f"  — {detail}" if detail else ""))

    def exit_code(self) -> int:
        return 1 if self.failed else 0
