#!/usr/bin/env python3
"""
UnitTest.py — deterministic, no-server, no-Groq unit tests for the bug-prone
PURE logic in the backend.

Why this exists
---------------
The two existing suites (IntegrationTest.py, SystemTest.py) both require a
running server, and the only one that touches the AI/search core (SystemTest)
also needs live Groq — so it's non-deterministic and can't gate CI. Yet the
densest, most-churned, most bug-prone code in the repo is exactly there: the
natural-language distance/difficulty parsing, the phase-transition regex banks,
the hike-selection parser, the tag-scoring/concept-expansion helpers, the gear
adequacy vocabulary, and the signal-token strip patterns.

All of that is pure (strings/dicts in, decisions out), so it's fast and
deterministic to test in isolation with zero infrastructure. This runner does
exactly that, reusing _testkit.Suite for the same PASS/FAIL/SKIP + exit-code
contract the integration suites use (0 = clean, 1 = a failure). Wire it into CI
as a fast pre-boot step — it needs no DB, no Redis, no Groq, no HTTP.

    python UnitTest.py
"""
from __future__ import annotations

import os
import sys

# These modules read env at import (GroqClient / TripInputParser need HikeKey;
# SessionStore reads REDIS_URL). None of them make a network call at import —
# Groq() just stores the key, SessionStore.ping() fails silently — so dummy
# values let us import the AI layer fully offline. Set BEFORE importing them.
os.environ.setdefault("HikeKey", "unit-test-dummy-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-dummy-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "unit-test-dummy-client")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _testkit import Suite  # noqa: E402

KM_PER_MILE = 1.60934


def _mi(miles: float) -> float:
    return round(miles * KM_PER_MILE, 1)


# ── gear_levels: the adequacy vocabulary ────────────────────────────────────

def test_gear_levels(s: Suite) -> None:
    print("\n[gear_levels]")
    from gear_levels import (
        level_index, meets, sleep_meets, is_valid_level,
        resolve_gear_category, resolve_level,
    )

    # level_index: ordinal rank; unknown / presence-only → -1 (never satisfies)
    s.check("level_index footwear hiking_boot == 2", level_index("footwear", "hiking_boot") == 2)
    s.check("level_index unknown value → -1", level_index("footwear", "flip_flop") == -1)
    s.check("level_index presence-only category → -1", level_index("hydration", "anything") == -1)

    # meets: index comparison, fails closed on unknown
    s.check("boot meets trail_runner need", meets("footwear", "hiking_boot", "trail_runner"))
    s.check("sandal does NOT meet boot need", not meets("footwear", "sandal", "hiking_boot"))
    s.check("None need always meets", meets("footwear", None, None))
    s.check("unknown have + real need fails closed", not meets("footwear", None, "trail_runner"))

    # sleep_meets: numeric, warmer (lower °F) is better, fails closed
    s.check("warmer bag (15F) meets 20F need", sleep_meets(15, 20))
    s.check("cooler-rated bag (30F) fails 20F need", not sleep_meets(30, 20))
    s.check("unknown bag rating fails closed", not sleep_meets(None, 20))
    s.check("no need → meets", sleep_meets(None, None))

    # is_valid_level
    s.check("valid footwear level", is_valid_level("footwear", "hiking_boot"))
    s.check("invalid footwear level rejected", not is_valid_level("footwear", "nope"))
    s.check("None level always valid", is_valid_level("footwear", None))
    s.check("presence-only + non-None level → invalid", not is_valid_level("hydration", "x"))

    # resolve_gear_category: explicit wins; clothing splits on waterproof
    s.check("explicit gear_category wins", resolve_gear_category("clothing", {"gear_category": "shell"}) == "shell")
    s.check("clothing + waterproof → shell", resolve_gear_category("clothing", {"waterproof": True}) == "shell")
    s.check("clothing + not waterproof → insulation", resolve_gear_category("clothing", {}) == "insulation")
    s.check("footwear item_type → footwear", resolve_gear_category("footwear", None) == "footwear")
    s.check("technical item_type → traction", resolve_gear_category("technical", {}) == "traction")
    s.check("unknown item_type → misc", resolve_gear_category("mystery", None) == "misc")

    # resolve_level: explicit level, then typed-attribute fallbacks
    s.check("explicit level in scale", resolve_level("footwear", {"level": "hiking_boot"}) == "hiking_boot")
    s.check("footwear fallback via footwear_type", resolve_level("footwear", {"footwear_type": "trail_runner"}) == "trail_runner")
    s.check("shell + waterproof → hardshell", resolve_level("shell", {"waterproof": True}) == "hardshell")
    s.check("shell + not waterproof → water_resistant", resolve_level("shell", {}) == "water_resistant")
    s.check("shelter fallback via season_rating", resolve_level("shelter", {"season_rating": "3_season"}) == "3_season")
    s.check("presence-only category → None", resolve_level("hydration", {"level": "x"}) is None)


# ── TripInputParser: distance/difficulty/duration NL parsing ─────────────────

def test_trip_input_parser(s: Suite) -> None:
    print("\n[TripInputParser]")
    from AI.TripInputParser import TripInputParser

    # __init__ needs HikeKey + a parks file and builds a Groq client; the pure
    # extract helpers below don't touch self, so bypass __init__ entirely.
    p = TripInputParser.__new__(TripInputParser)
    elc = p._extract_length_constraints  # returns (min_km, max_km, target_km)

    # Range sets BOTH bounds.
    s.check("'3 to 5 miles' sets both bounds", elc("3 to 5 miles") == (_mi(3), _mi(5), None))

    # The documented precedence hazard: a FLOOR must not be read as a ceiling.
    mn, mx, tg = elc("at least 5 miles")
    s.check("'at least 5 miles' → min only (not max)", mn == _mi(5) and mx is None and tg is None)
    mn, mx, tg = elc("5+ miles")
    s.check("'5+ miles' → min only", mn == _mi(5) and mx is None and tg is None)

    # Ceiling forms, including "no more than" which must NOT be swallowed as a floor.
    mn, mx, tg = elc("under 4 miles")
    s.check("'under 4 miles' → max only", mn is None and mx == _mi(4) and tg is None)
    mn, mx, tg = elc("no more than 4 miles")
    s.check("'no more than 4 miles' → max only (not min)", mn is None and mx == _mi(4) and tg is None)

    # Approximate → target set, ceiling loosened to target*1.2.
    mn, mx, tg = elc("around 3 miles")
    s.check("'around 3 miles' → target set + loosened ceiling",
            mn is None and tg == _mi(3) and mx == round(_mi(3) * 1.2, 1))

    # Bare single number → hard ceiling; approximate word absent.
    mn, mx, tg = elc("a 3 mile hike")
    s.check("'a 3 mile hike' → max only", mn is None and mx == _mi(3) and tg is None)

    # Time budget only fires when no mile phrase present (pace = 3.0 km/h).
    mn, mx, tg = elc("i want to be back in 2 hours")
    s.check("'back in 2 hours' → time-budget km ceiling", mn is None and mx == 6.0 and tg is None)

    # Difficulty: negation must beat the positive-keyword scan.
    d = p._extract_difficulty
    s.check("'nothing too strenuous' → easy (negation wins)", d("nothing too strenuous") == "easy")
    s.check("'not too difficult' → easy", d("not too difficult") == "easy")
    s.check("'really hard climb' → hard", d("a really hard climb") == "hard")
    s.check("'easy beginner hike' → easy", d("an easy beginner hike") == "easy")
    s.check("no difficulty words → None", d("a hike by the water") is None)

    # Duration: "N nights" → N+1 days; bare weekend/week phrases.
    du = p._extract_duration
    s.check("'2 nights' → 3 days", du("2 nights out") == 3)
    s.check("'3 day trip' → 3", du("a 3 day trip") == 3)
    s.check("'a weekend' → 3", du("just a weekend") == 3)
    s.check("no duration → None", du("a quick hike") is None)

    # Multi-day phrasings must yield a concrete number, not silently default.
    s.check("'multi-day' → 3", du("a multi-day trip") == 3)
    s.check("'multiday' → 3", du("multiday hike") == 3)
    s.check("'several days' → 3", du("out for several days") == 3)
    s.check("'a couple of days' → 2", du("a couple of days") == 2)
    s.check("'long weekend' → 3", du("a long weekend") == 3)

    # Ambiguity signal: an overnight-implying activity with no explicit count is
    # ambiguous (→ the destination phase confirms), but an explicit count is not.
    from AI.TripInputParser import OVERNIGHT_ACTIVITIES
    act = p._extract_activity
    def _amb(text):
        return du(text) is None and act(text) in OVERNIGHT_ACTIVITIES
    s.check("'backpacking trip' (no count) is ambiguous", _amb("a backpacking trip"))
    s.check("'3 day backpacking' is NOT ambiguous", not _amb("a 3 day backpacking trip"))
    s.check("plain 'day hike' is NOT ambiguous", not _amb("a day hike"))

    # Length FLOOR from an overnight activity when no explicit length is given —
    # stops "backpacking" from returning 4 km day-hikes (proximity ranking with
    # no min_length gate). An explicit floor always wins; day-hikes get none.
    from AI.TripInputParser import _effective_min_length, OVERNIGHT_MIN_KM_PER_DAY
    # signature: (min_km, max_km, target_km, activity, duration_days)
    s.check("backpacking (1 night, no length) → duration-scaled floor",
            _effective_min_length(None, None, None, "backpacking", 2) == OVERNIGHT_MIN_KM_PER_DAY * 2)
    s.check("day_hike (no length) → no floor",
            _effective_min_length(None, None, None, "day_hike", 1) is None)
    s.check("explicit 'at least N' floor wins over activity default",
            _effective_min_length(_mi(6), None, None, "backpacking", 3) == _mi(6))
    s.check("overnight floor scales with duration_days",
            _effective_min_length(None, None, None, "extended", 3) == OVERNIGHT_MIN_KM_PER_DAY * 3)
    # Conflict guard: a ceiling/approx length must suppress the floor so we never
    # build an impossible min>max range (e.g. "around 8 mi backpacking").
    s.check("ceiling length suppresses backpacking floor (no min>max)",
            _effective_min_length(None, _mi(5), None, "backpacking", 2) is None)
    s.check("approximate/target length suppresses backpacking floor",
            _effective_min_length(None, None, _mi(8), "backpacking", 2) is None)
    # A specific named place ("Linville Gorge") skips the auto overnight floor so a
    # dense wilderness's own short trail segments aren't hard-excluded; region /
    # near-me searches (is_specific_place=False) keep the floor.
    s.check("specific named place skips the overnight floor",
            _effective_min_length(None, None, None, "backpacking", 2, is_specific_place=True) is None)
    s.check("region/near-me still gets the overnight floor",
            _effective_min_length(None, None, None, "backpacking", 2, is_specific_place=False) == OVERNIGHT_MIN_KM_PER_DAY * 2)
    s.check("explicit floor still wins even for a specific place",
            _effective_min_length(_mi(6), None, None, "backpacking", 2, is_specific_place=True) == _mi(6))


# ── PhaseController: selection parser + transition signal banks ──────────────

def test_phase_controller(s: Suite) -> None:
    print("\n[PhaseController]")
    from AI.PhaseController import (
        PhaseController, GEAR_DONE_SIGNALS, ITINERARY_DONE_SIGNALS,
        DESTINATION_RESET_SIGNALS,
    )

    sel = PhaseController.extract_hike_selection  # (text, count) → 0-based idx | None
    s.check("bare '2' → index 1", sel("2", 3) == 1)
    s.check("'the first one' → index 0", sel("the first one", 3) == 0)
    s.check("'option 3' → index 2", sel("option 3", 3) == 2)
    s.check("'go with 2' → index 1", sel("let's go with 2", 3) == 1)
    s.check("out-of-range '5' of 3 → None", sel("5", 3) is None)
    s.check("count 0 → None", sel("1", 0) is None)
    s.check("no selection → None", sel("tell me more about these", 3) is None)

    ma = PhaseController._matches_any
    s.check("'looks good' is a gear-done signal", ma("looks good", GEAR_DONE_SIGNALS))
    s.check("'let's proceed' is a gear-done signal", ma("let's proceed", GEAR_DONE_SIGNALS))
    s.check("bare 'ok' is NOT a gear-done signal", not ma("ok", GEAR_DONE_SIGNALS))
    s.check("\"that's the plan\" approves itinerary", ma("that's the plan", ITINERARY_DONE_SIGNALS))
    s.check("'start over' is a reset signal", ma("can we start over", DESTINATION_RESET_SIGNALS))
    s.check("plain chat is not a reset signal", not ma("what's the weather like", DESTINATION_RESET_SIGNALS))


# ── HikeSearchService: pure scoring / label helpers ─────────────────────────

def test_hike_search_helpers(s: Suite) -> None:
    print("\n[HikeSearchService helpers]")
    from Services.HikeSearchService import (
        HikeSearchService, _tag_match_score, _expand_concept_tags, CONCEPT_EXPANSIONS,
    )

    fsl = HikeSearchService._format_state_label
    s.check("'NC' stays uppercase", fsl("NC") == "NC")
    s.check("'blue_ridge' → 'Blue Ridge'", fsl("blue_ridge") == "Blue Ridge")
    s.check("None → None", fsl(None) is None)

    s.check("exact tag match scores 1.0", _tag_match_score({"river", "forest"}, ["river"]) == 1.0)
    s.check("no match scores 0.0", _tag_match_score({"summit"}, ["river"]) == 0.0)
    s.check("two exact matches sum to 2.0", _tag_match_score({"river", "forest"}, ["river", "forest"]) == 2.0)

    # A concept term (multi-tag, OR semantics) must be demoted out of required
    # and expanded into preferred, or the DB @> ALL-tags filter can't be satisfied.
    req, pref = _expand_concept_tags(["water_feature", "gentle_gain"], [])
    s.check("concept term demoted from required", "water_feature" not in req and "gentle_gain" in req)
    s.check("concept term expanded into preferred",
            set(CONCEPT_EXPANSIONS["water_feature"]).issubset(set(pref)))


# ── TripChat: signal-token strip patterns (strip-before-return invariant) ────

def test_signal_token_strip(s: Suite) -> None:
    print("\n[TripChat signal-token strip]")
    # This import is heavier (instantiates the AI service singletons), so guard
    # it: a missing optional dep should SKIP, not crash the whole unit run.
    try:
        from AI.TripChat import _GEAR_ADD_RE, _LEAKED_HIKE_LINE_RE
    except Exception as e:  # pragma: no cover - env without AI deps
        s.skip("TripChat signal-regex import", f"{type(e).__name__}: {str(e)[:100]}")
        return

    # GEAR ADD: <category> — captured for the side effect, then stripped.
    m = _GEAR_ADD_RE.search("Here's a great option.\nGEAR ADD: rain_shell")
    s.check("GEAR ADD regex captures the category", bool(m) and m.group(1).strip() == "rain_shell")
    s.check("GEAR ADD token stripped from reply",
            _GEAR_ADD_RE.sub("", "You'll want a shell. GEAR ADD: rain_shell").strip()
            == "You'll want a shell.")

    # Leaked internal lines (Tags:[...], Gear check:, "Here are the N hike options")
    leaked = "Nice picks!\nTags: [river, forest]\nGear check: you're set\n"
    cleaned = _LEAKED_HIKE_LINE_RE.sub("", leaked)
    s.check("leaked 'Tags: [...]' line stripped", "Tags:" not in cleaned)
    s.check("leaked 'Gear check:' line stripped", "Gear check:" not in cleaned)
    s.check("legitimate prose preserved", "Nice picks!" in cleaned)


# ── rigor: the prep-level tier engine ───────────────────────────────────────

def test_rigor_tier(s: Suite) -> None:
    print("\n[rigor]")
    from AI.rigor import rigor_tier, tier_index, RIGOR_TIERS

    # The linear ramp the tiers encode: trivial → casual, half-day → standard,
    # committing day → serious, any overnight → expedition.
    s.check("short flat easy day → casual",
            rigor_tier(3.2, 60, difficulty="EASY", duration_days=1) == "casual")
    s.check("moderate ~10km day → standard",
            rigor_tier(9.8, 258, difficulty="MODERATE", duration_days=1) == "standard")
    s.check("hard high-gain day → serious",
            rigor_tier(18, 900, difficulty="DIFFICULT", duration_days=1) == "serious")
    s.check("any overnight → expedition",
            rigor_tier(9.8, 258, difficulty="MODERATE", duration_days=2) == "expedition")
    s.check("trail too big for one day → expedition",
            rigor_tier(30, 400, difficulty="MODERATE", duration_days=1) == "expedition")

    # Casual is genuinely trivial-only: gain past the 250 m guard leaves casual.
    s.check("gain 249 easy short → casual",
            rigor_tier(3.0, 249, difficulty="EASY", duration_days=1) == "casual")
    s.check("gain 260 easy short → standard (not casual)",
            rigor_tier(3.0, 260, difficulty="EASY", duration_days=1) == "standard")

    # Ordinals are ordered low→high and stable.
    s.check("tier_index orders casual<serious<expedition",
            tier_index("casual") < tier_index("serious") < tier_index("expedition"))
    s.check("RIGOR_TIERS has the four bands",
            RIGOR_TIERS == ["casual", "standard", "serious", "expedition"])


# ── GearGapAnalyzer: tier suppression + multi-day escalation ─────────────────

def test_gear_gap_scaling(s: Suite) -> None:
    print("\n[GearGapAnalyzer scaling]")
    from types import SimpleNamespace
    from AI.GearGapAnalyzer import GearGapAnalyzer
    from PyObjects.Hike import DifficultyLevel

    def hike(**kw):
        return SimpleNamespace(
            id="t", length_km=kw.get("length_km", 5), elevation_gain_m=kw.get("gain", 100),
            max_altitude_m=kw.get("alt", 300), difficulty=kw.get("diff", DifficultyLevel.EASY),
            tags=kw.get("tags", []), can_camp=kw.get("can_camp", False),
            gear_requirements=kw.get("reqs", {}),
        )

    a = GearGapAnalyzer()
    cats = lambda gaps: {g.category for g in gaps}
    no_gear: list[dict] = []   # user owns nothing → every real gap surfaces

    # Casual (short/flat/easy) suppresses the ten-essentials nag entirely.
    casual = hike(length_km=3.2, gain=60, diff=DifficultyLevel.EASY)
    s.check("casual legacy hike → no baseline gaps", a.analyze_for_hike(no_gear, casual, 1) == [])

    # The SAME missing categories DO surface on a standard (moderate) hike.
    standard = hike(length_km=9.8, gain=258, diff=DifficultyLevel.MODERATE)
    std_cats = cats(a.analyze_for_hike(no_gear, standard, 1))
    s.check("standard legacy hike surfaces first_aid", "first_aid" in std_cats)
    s.check("standard legacy hike surfaces navigation", "navigation" in std_cats)

    # Requirement-driven path: casual suppresses first_aid/navigation, keeps the
    # committing footwear requirement.
    reqs = {
        "footwear":   {"min_level": "trail_runner", "importance": "required"},
        "first_aid":  {"importance": "required"},
        "navigation": {"min_level": "map", "importance": "required"},
        "hydration":  {"importance": "required"},
    }
    casual_bf = hike(length_km=3.2, gain=60, diff=DifficultyLevel.EASY, reqs=reqs)
    bf_cats = cats(a.analyze_for_hike(no_gear, casual_bf, 1))
    s.check("casual req-path suppresses first_aid", "first_aid" not in bf_cats)
    s.check("casual req-path keeps footwear", "footwear" in bf_cats)

    # Multi-day escalation: shelter + sleep appear once nights are requested,
    # even on a trail that isn't itself flagged can_camp.
    day_cats   = cats(a.analyze_for_hike(no_gear, standard, 1))
    multi_cats = cats(a.analyze_for_hike(no_gear, standard, 2))
    s.check("single day → no shelter gap", "shelter" not in day_cats)
    s.check("multi-day adds shelter", "shelter" in multi_cats)
    s.check("multi-day adds sleep system", "sleep_system" in multi_cats)


def test_split_days(s: Suite) -> None:
    print("\n[trip_metrics.split_days — deterministic per-day itinerary math]")
    from trip_metrics import split_days, km_to_miles, m_to_feet

    # The whole point: per-day parts sum EXACTLY to the displayed trail total.
    parts = split_days(42.96, 2218, 3)   # the Shut-In example
    s.check("3-day split returns 3 days", len(parts) == 3)
    s.check("3-day distance sums to trail total",
            round(sum(p[0] for p in parts), 1) == km_to_miles(42.96))
    s.check("3-day gain sums to trail total",
            sum(p[1] for p in parts) == m_to_feet(2218))

    one = split_days(3.2, 118, 1)
    s.check("1-day split is the whole trail",
            one == [(km_to_miles(3.2), m_to_feet(118))])

    s.check("duration 0 coerced to 1 day", len(split_days(10, 100, 0)) == 1)
    s.check("no totals → zeros, no crash", split_days(None, None, 3) == [(0.0, 0)] * 3)

    p2 = split_days(20, 0, 4)
    s.check("zero-gain split still sums distance",
            round(sum(p[0] for p in p2), 1) == km_to_miles(20))
    s.check("zero-gain split has all-zero gain", all(p[1] == 0 for p in p2))


def test_gear_gap_metadata(s: Suite) -> None:
    print("\n[GearGap A+ metadata — powers the inline gear-entry form]")
    from types import SimpleNamespace
    from AI.GearGapAnalyzer import GearGapAnalyzer
    from PyObjects.Hike import DifficultyLevel

    def hike(**kw):
        return SimpleNamespace(
            id="t", length_km=kw.get("length_km", 15), elevation_gain_m=kw.get("gain", 800),
            max_altitude_m=kw.get("alt", 1200), difficulty=kw.get("diff", DifficultyLevel.DIFFICULT),
            tags=kw.get("tags", []), can_camp=kw.get("can_camp", False),
            gear_requirements=kw.get("reqs", {}),
        )

    a = GearGapAnalyzer()
    reqs = {
        "footwear":  {"min_level": "hiking_boot", "importance": "required"},
        "shell":     {"min_level": "hardshell",   "importance": "recommended"},
        "first_aid": {"importance": "required"},
    }
    gaps = {g.category: g for g in a.analyze_for_hike([], hike(reqs=reqs), 1)}

    fw = gaps.get("footwear")
    s.check("footwear gap present", fw is not None)
    s.check("footwear gap carries functional gear_category", bool(fw) and fw.gear_category == "footwear")
    s.check("footwear gap carries min_level", bool(fw) and fw.min_level == "hiking_boot")
    s.check("footwear gap carries importance", bool(fw) and fw.importance == "required")

    # shell requirement → emitted under the CAT_RAIN_GEAR ("rain_gear") category,
    # but its functional gear_category must be "shell" (what create_user_gear wants).
    shell = gaps.get("rain_gear")
    s.check("shell gap mapped to rain_gear category", shell is not None)
    s.check("shell gap gear_category is 'shell'", bool(shell) and shell.gear_category == "shell")
    s.check("shell gap min_level hardshell", bool(shell) and shell.min_level == "hardshell")

    fa = gaps.get("first_aid")
    s.check("first_aid (presence) gap present", fa is not None)
    s.check("presence gap has no min_level", bool(fa) and fa.min_level is None)
    s.check("presence gap still carries gear_category", bool(fa) and fa.gear_category == "first_aid")

    d = fw.to_dict() if fw else {}
    s.check("GearGap.to_dict exposes form fields",
            {"min_level", "gear_category", "importance"} <= set(d))


def test_location_fixes(s: Suite) -> None:
    print("\n[location: relocation, state scoping, token strip]")
    from AI.TripInputParser import TripInputParser, _is_state_only_candidate
    from AI.TripChat import _strip_signal

    p = TripInputParser()

    # ── Relocation extractor ("move the map") ──────────────────────────────
    reloc = p.extract_relocation_place
    s.check("relocate 'closer to Asheville'",       reloc("closer to Asheville") == "Asheville")
    s.check("relocate 'how about Boone'",           (reloc("how about Boone") or "").lower() == "boone")
    s.check("relocate 'over near Brevard'",         (reloc("over near Brevard") or "").lower() == "brevard")
    s.check("relocate rejects a feature",           reloc("closer to a lake") is None)
    s.check("relocate rejects a length",            reloc("around 5 miles") is None)
    s.check("relocate rejects a pure refinement",   reloc("make it easier") is None)

    # ── "anywhere in <state>" resolves to the state, not filler ────────────
    s.check("state-only 'nc is fine'",              _is_state_only_candidate("nc is fine", "NC") is True)
    s.check("state-only 'anywhere in north carolina'", _is_state_only_candidate("anywhere in north carolina", "NC") is True)
    s.check("state-only rejects a real place",      _is_state_only_candidate("asheville", "NC") is False)

    # parse("anywhere in NC …") must NOT geocode the literal filler and must
    # keep NC (mock _geocode so there's no HTTP and no clobber).
    p._geocode = lambda place, state=None: {"lat": 35.7, "lng": -79.0, "state": "MN"}  # deliberately wrong state
    intent = p.parse("anywhere in NC is fine")
    s.check("anywhere-in-NC resolves to the state", intent.destination_full == "North Carolina", f"got {intent.destination_full!r}")
    s.check("explicit state NC not clobbered by geocode", intent.state == "NC", f"got {intent.state!r}")

    # ── Bare place name after a vague destination must still search ────────
    # "Sorry Linville Gorge": no preposition, and "gorge" is the canyon feature
    # keyword — so has_location_signal misses it. has_possible_place_token must
    # catch "linville" so trip_chat doesn't strand it in the no-destination
    # branch. Mirror _has_no_destination's logic: feature word + no location
    # signal + no possible place token.
    from AI.TripInputParser import ALL_FEATURE_KEYWORDS
    # trip_chat._NO_LOCATION_FEATURE_KEYWORDS = ALL_FEATURE_KEYWORDS | these activity words
    _activity_kws = {"easy", "moderate", "hard", "challenging", "short", "hike"}
    def _no_dest(msg):  # replicates trip_chat._has_no_destination (unimportable: Redis at import)
        has_feature = any(kw in msg.lower() for kw in (ALL_FEATURE_KEYWORDS | _activity_kws))
        if not has_feature:
            return False
        if p.has_location_signal(msg):
            return False
        return not p.has_possible_place_token(msg)

    s.check("'Linville Gorge' has a possible place token", p.has_possible_place_token("Linville Gorge"))
    s.check("'Sorry Linville Gorge' has a possible place token", p.has_possible_place_token("Sorry Linville Gorge"))
    s.check("'Sorry Linville Gorge' is NOT treated as no-destination", _no_dest("Sorry Linville Gorge") is False)
    s.check("'Linville Gorge' is NOT treated as no-destination", _no_dest("Linville Gorge") is False)
    # Genuinely locationless feature/difficulty requests still short-circuit.
    s.check("'something with a lake' has no place token", p.has_possible_place_token("something with a lake") is False)
    s.check("'something with a lake' IS no-destination", _no_dest("something with a lake") is True)
    s.check("'nothing too hard' IS no-destination", _no_dest("nothing too hard") is True)
    s.check("'an easy hike near a lake' IS no-destination", _no_dest("an easy hike near a lake") is True)

    # ── Signal token strip removes the token AND its trailing em-dash ──────
    stripped = _strip_signal("SEARCH_REFINE — sure, shorter trails", "SEARCH_REFINE")
    s.check("strip SEARCH_REFINE + em-dash", stripped == "sure, shorter trails", f"got {stripped!r}")
    s.check("no leading em-dash left",
            not _strip_signal("DESTINATION RESET — near Asheville?", "DESTINATION RESET").startswith("—"))


def test_feature_honesty(s: Suite) -> None:
    print("\n[feature-honesty: unbacked feature claims vs card tags]")
    from AI.feature_honesty import unbacked_feature_claims

    def _card(tags, name="Some Trail"):
        return {"name": name, "tags": tags}

    # The reported backpacking case: prose credits lake + waterfall, no card has
    # either → both flagged. "Avery Creek" is a NAME, not a river claim, so
    # "creek" must NOT flag 'river' (name redaction).
    prose = "North Mills features a lake, and Avery Creek has a waterfall."
    cards = [
        _card(["dem elevation", "forest", "gentle gain", "half day"], name="North Mills"),
        _card(["dem elevation", "forest", "gentle gain", "montane"], name="Avery Creek"),
    ]
    s.check("fabricated lake + waterfall flagged; creek-in-name not read as river",
            unbacked_feature_claims(prose, cards) == ["lake", "waterfall"])

    # Name redaction: a 'Lake Johnson Trail' with no lake tag must not self-back
    # via its name, and mentioning it by name is not a lake claim.
    s.check("'Lake Johnson' named but no lake tag / no lake claim → clean",
            unbacked_feature_claims("Lake Johnson Trail is a great pick",
                                    [_card(["forest", "beach"], name="Lake Johnson Trail")]) == [])

    # Backed claim: at least one card actually carries the tag → not flagged.
    s.check("waterfall claim backed by a waterfall tag → clean",
            unbacked_feature_claims("has a waterfall", [_card(["forest", "waterfall"])]) == [])

    # Synonym tag backs the canonical feature: a 'stream'-tagged trail backs a
    # 'river' mention; 'falls' backs 'waterfall'.
    s.check("'river' mention backed by a 'stream' tag → clean",
            unbacked_feature_claims("follows a river", [_card(["stream", "forest"])]) == [])
    s.check("'falls' mention backed by a 'waterfall' tag → clean",
            unbacked_feature_claims("passes the falls", [_card(["waterfall"])]) == [])

    # No cards / no prose → nothing to check.
    s.check("no cards → no claims", unbacked_feature_claims("has a lake", []) == [])
    s.check("empty prose → no claims", unbacked_feature_claims("", [_card(["forest"])]) == [])

    # Descriptive terrain words are intentionally NOT scanned (forest is noise).
    s.check("'forest' walk not flagged (not a verifiable draw)",
            unbacked_feature_claims("a nice forest walk", [_card(["lake"])]) == [])


def main() -> None:
    s = Suite("UnitTest (pure logic, no server / Groq / DB)")
    print("HikeBuilder unit tests — deterministic pure-logic checks")

    test_gear_levels(s)
    test_trip_input_parser(s)
    test_phase_controller(s)
    test_hike_search_helpers(s)
    test_signal_token_strip(s)
    test_rigor_tier(s)
    test_gear_gap_scaling(s)
    test_split_days(s)
    test_gear_gap_metadata(s)
    test_location_fixes(s)
    test_feature_honesty(s)

    s.summary()
    sys.exit(s.exit_code())


if __name__ == "__main__":
    main()
