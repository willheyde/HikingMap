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

    # Bare single number → TARGET with a hard band (floor+ceiling), NOT a bare
    # ceiling: "an 8 mile hike" must never surface a 2-mile trail, and the target
    # turns on length-proximity ranking. Band = target * 0.7 .. target * 1.3.
    from AI.TripInputParser import SINGLE_MILE_FLOOR_FACTOR, SINGLE_MILE_CEIL_FACTOR
    mn, mx, tg = elc("a 3 mile hike")
    s.check("'a 3 mile hike' → banded target (floor+ceiling+target)",
            mn == round(_mi(3) * SINGLE_MILE_FLOOR_FACTOR, 1)
            and mx == round(_mi(3) * SINGLE_MILE_CEIL_FACTOR, 1)
            and tg == _mi(3))
    mn, mx, tg = elc("an 8 mile hike near me")
    s.check("'8 mile' floor excludes a 2-mile trail (floor > 3.2 km)",
            mn is not None and mn > 3.2 and tg == _mi(8))
    # The gradient: "around N" stays looser (no floor, +20% ceiling) than bare N.
    mn_a, _, _ = elc("around 8 miles")
    mn_b, _, _ = elc("8 miles")
    s.check("'around 8' has no floor but bare '8 miles' does",
            mn_a is None and mn_b is not None)

    # Rejected length: a mid-chat refine that discards one distance for another
    # ("8 miles is too long, look at 4 mile instead") must target the number the
    # user WANTS (4), not the FIRST number it sees (8) — else the re-search just
    # re-runs the distance the user asked to move away from.
    _, _, tg = elc("wait actually 8 miles is too long, can we look at 4 mile hikes instead")
    s.check("'8 mi too long, look at 4 mile' → target 4 (not 8)", tg == _mi(4))
    _, _, tg = elc("that 8 mile hike is too far, show me 3 mile trails instead")
    s.check("'8 mi too far, show me 3 mile' → target 3 (not 8)", tg == _mi(3))
    _, _, tg = elc("not 8 miles, i want 5 miles")
    s.check("'not 8 miles, want 5 miles' → target 5 (not 8)", tg == _mi(5))
    # The rejection may carry an article ("instead of AN 8 mile hike").
    _, _, tg = elc("wait instead of an 8 mile hike can we look at a 4 mile one")
    s.check("'instead of an 8 mile … a 4 mile one' → target 4 (not 8)", tg == _mi(4))
    # Regression guard: the rejection strip must NOT eat a legitimate ceiling.
    mn, mx, tg = elc("no more than 6 miles")
    s.check("rejection strip leaves 'no more than 6 miles' as a ceiling",
            mn is None and mx == _mi(6) and tg is None)

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
    # Comparative forms show up in refine turns ("can we do something easier?").
    s.check("'something easier' → easy", d("can we do something easier") == "easy")
    s.check("'a bit tougher' → hard", d("something a bit tougher") == "hard")
    s.check("'harder' → hard (base-substring)", d("id like it harder") == "hard")

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
    # A duration/length digit is NOT a numbered pick: the "3" in "3 day" must not
    # select option 3 (the auto-jump-to-gear bug). Guard both the reported phrase
    # and a length variant, and confirm real selections still resolve.
    s.check("'3 day … trip near me' is NOT a selection (was picking option 3)",
            sel("i want to go on a 3 day hiking trip near me", 5) is None)
    s.check("'let's do a 2 mile loop' is NOT a selection", sel("let's do a 2 mile loop", 5) is None)
    s.check("'i want 3' (no unit) still selects index 2", sel("i want 3", 5) == 2)
    s.check("bare '3' still selects index 2", sel("3", 5) == 2)

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
    # "near me" mid-chat must NOT geocode the pronoun ("me" → Maine); it's routed
    # to the user's own coords in _try_relocate, so the extractor rejects it.
    s.check("relocate rejects 'near me'",           reloc("actually move it near me") is None)
    s.check("relocate rejects 'to here'",           reloc("something closer to here") is None)
    s.check("relocate rejects 'my location'",       reloc("how about near my location") is None)

    # ── is_near_me: the shared "search my own location" detector ────────────
    from AI.TripInputParser import (
        is_near_me, _strip_constraint_phrases, LocationRequired,
    )
    s.check("is_near_me 'near me'",        is_near_me("a 5 mile hike near me") is True)
    s.check("is_near_me 'around me'",      is_near_me("trails around me") is True)
    s.check("is_near_me 'close by'",       is_near_me("something close by") is True)
    s.check("is_near_me 'closest to me'",  is_near_me("closest to me please") is True)
    s.check("is_near_me 'near here'",      is_near_me("hikes near here") is True)
    # Must NOT false-match a real place that merely starts with "me".
    s.check("is_near_me rejects 'near Mendocino'", is_near_me("hike near Mendocino") is False)
    s.check("is_near_me rejects plain place",      is_near_me("hike near Asheville") is False)

    # near-me routes to the passed coords (no geocode, no Groq) …
    intent = p.parse("a 5 mile hike near me", user_lat=35.2, user_lng=-80.8)
    s.check("near-me uses user coords",     intent.lat == 35.2 and intent.lng == -80.8)
    s.check("near-me sets destination_raw", intent.destination_raw == "near me")
    # … and with no coords raises LocationRequired (caller asks for a place).
    try:
        p.parse("a hike near me", user_lat=None, user_lng=None)
        loc_raised = False
    except LocationRequired:
        loc_raised = True
    except Exception:
        loc_raised = False
    s.check("near-me without coords → LocationRequired", loc_raised)

    # ── _strip_constraint_phrases: length/feature clauses must not leak a
    #    destination token ("at least 4 miles" → the preposition "at") ───────
    cleaned = _strip_constraint_phrases(
        "i want to go on a hike near raleigh, that has a water fall and is at least 4 miles long"
    )
    s.check("strip removes 'at least'",  "at least" not in cleaned)
    s.check("strip removes '4 miles'",   "4 mile" not in cleaned)
    s.check("strip removes 'that' clause", "that has" not in cleaned)
    s.check("destination extracts to 'raleigh', not 'at'",
            (p._extract_destination_regex(cleaned) or "").lower() == "raleigh",
            f"got {p._extract_destination_regex(cleaned)!r}")
    # A place can come AFTER the feature clause ("a hike with a waterfall near
    # Asheville") — the trailing-clause strip must stop at the destination
    # preposition, not swallow the place to end-of-line (regression: it did).
    for phrase, want in (
        ("a hike with a waterfall near asheville",  "asheville"),
        ("trails with a lake near boone",           "boone"),
        ("hikes where i can swim near brevard",      "brevard"),
    ):
        got = (p._extract_destination_regex(_strip_constraint_phrases(phrase)) or "").lower()
        s.check(f"clause-before-place keeps the place ({want})", got == want, f"got {got!r}")

    # ── Invalid-token guard: a bare preposition the LLM latched onto never
    #    reaches the geocoder — it's "no place named", so NoDestinationProvided ─
    from AI.TripInputParser import (
        DestinationNotFound, NoDestinationProvided, _INVALID_DESTINATION_TOKENS,
    )
    s.check("'at' is an invalid destination token", "at" in _INVALID_DESTINATION_TOKENS)
    # Mock geocode so the guard is what's under test, not a network failure — a
    # miss here MUST come from the token guard, not an unreachable Nominatim.
    p._geocode = lambda place, state=None: {"lat": 35.7, "lng": -79.0, "state": "NC"}
    p._llm_extract = lambda text: {"destination": "at", "features": []}
    try:
        p.parse("i want a hike that is at least 4 miles long", user_lat=None, user_lng=None)
        tok_raised = False
    except NoDestinationProvided:
        tok_raised = True
    except Exception:
        tok_raised = False
    s.check("stray 'at' token → NoDestinationProvided (not geocoded)", tok_raised)

    # ── _is_named_wilderness: only a park/wilderness skips the overnight floor;
    #    a plain city keeps it (Bent Creek day-strolls must not be shown as
    #    backpacking legs near Asheville) ─────────────────────────────────────
    s.check("city 'Asheville' is NOT a wilderness", p._is_named_wilderness("Asheville", "asheville") is False)
    s.check("'Linville Gorge' IS a wilderness",     p._is_named_wilderness("Linville Gorge", None) is True)
    s.check("'Pisgah National Forest' IS a wilderness", p._is_named_wilderness("Pisgah National Forest", None) is True)
    # Town names that merely CONTAIN a wilderness word must not skip the floor —
    # bare "mountain"/"forest"/"range" form ordinary place names (regression).
    s.check("town 'Black Mountain' is NOT a wilderness", p._is_named_wilderness("Black Mountain", None) is False)
    s.check("town 'Forest City' is NOT a wilderness",    p._is_named_wilderness("Forest City", None) is False)
    s.check("town 'Mountain View' is NOT a wilderness",  p._is_named_wilderness("Mountain View", None) is False)
    s.check("'Great Smoky Mountains' IS a wilderness",   p._is_named_wilderness("Great Smoky Mountains", None) is True)

    # ── near-me + a concrete place: the named place wins over the pronoun ──────
    # "a waterfall hike near Brevard, close to me" must resolve Brevard (geocoded),
    # not silently return the user's own coordinates (regression). Geocode mocked.
    p._geocode = lambda place, state=None: {"lat": 35.6, "lng": -82.55, "state": "NC"}
    both = p.parse("a waterfall hike near Brevard, close to me", user_lat=99.9, user_lng=99.9)
    s.check("near-me + named place → resolves the place", both.destination_raw == "brevard",
            f"got {both.destination_raw!r}")
    s.check("near-me + named place → ignores the user coords", both.lat == 35.6)
    # A pure near-me ask (no place) still uses the user's coordinates.
    pure = p.parse("a 5 mile hike near me", user_lat=35.2, user_lng=-80.8)
    s.check("pure 'near me' still uses user coords", pure.destination_raw == "near me" and pure.lat == 35.2)

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


def test_phantom_place_and_multiday(s: Suite) -> None:
    print("\n[phantom-place + multi-day fixes]")
    from AI.TripInputParser import (
        TripInputParser, NoDestinationProvided, _is_feature_only_phrase,
        _strip_constraint_phrases, _effective_min_length, OVERNIGHT_MIN_KM_PER_DAY,
    )
    p = TripInputParser()

    # ── 1a. The "at" park-key trap is closed ───────────────────────────────
    s.check("'at' still resolves as an exact park key", "at" in p.national_parks)
    s.check("'at' is NOT in the bare-word scan keys", "at" not in p.park_scan_keys)
    # "at least 3" (no unit — the unit rode on an earlier "6 miles") is stripped
    # so the bare "at" never reaches the destination extractor.
    cleaned = _strip_constraint_phrases("no more than 6 miles, but at least 3")
    s.check("unit-less 'at least 3' stripped", "at least" not in cleaned, f"got {cleaned!r}")

    # ── 1b. Feature-only phrase is not a place ─────────────────────────────
    s.check("'a forest' is a feature-only phrase", _is_feature_only_phrase("a forest") is True)
    s.check("'a lake' is a feature-only phrase",   _is_feature_only_phrase("a lake") is True)
    s.check("'asheville' is NOT feature-only",     _is_feature_only_phrase("asheville") is False)
    # "in a forest" must not extract as a place.
    dest_text = _strip_constraint_phrases(
        "i've been wanting to go for a stroll in a forest, no more than 6 miles but at least 3"
    )
    s.check("'stroll in a forest' → no regex destination",
            p._extract_destination_regex(dest_text) is None,
            f"got {p._extract_destination_regex(dest_text)!r}")

    # The full placeless message raises NoDestinationProvided (ask "where?"),
    # never the phantom "at" / "that location". LLM is mocked (no Groq).
    p._llm_extract = lambda text: {"destination": None, "features": ["forest"]}
    for msg in (
        "i've been wanting to go for a stroll in a forest, no more than 6 miles but at least 3",
        "I didn't name a place",
    ):
        try:
            p.parse(msg, user_lat=None, user_lng=None)
            raised = "none"
        except NoDestinationProvided:
            raised = "no_dest"
        except Exception as e:
            raised = type(e).__name__
        s.check(f"placeless msg → NoDestinationProvided ({msg[:24]!r})", raised == "no_dest", f"got {raised}")

    # An LLM that still latches onto a feature is also treated as no-destination.
    p._llm_extract = lambda text: {"destination": "a forest", "features": []}
    try:
        p.parse("something with lots of trees", user_lat=None, user_lng=None)
        feat_raised = False
    except NoDestinationProvided:
        feat_raised = True
    except Exception:
        feat_raised = False
    s.check("LLM feature-only destination → NoDestinationProvided", feat_raised)

    # ── 2. Multi-day duration drives the search floor + duration_explicit ──
    s.check("explicit 3-day day_hike (region) → 30 km floor",
            _effective_min_length(None, None, None, "day_hike", 3, is_specific_place=False, duration_explicit=True)
            == OVERNIGHT_MIN_KM_PER_DAY * 3)
    s.check("1-day day_hike → still no floor",
            _effective_min_length(None, None, None, "day_hike", 1, is_specific_place=False, duration_explicit=True) is None)
    # A DEFAULTED (non-explicit) 2-day count must NOT impose a floor — that's the
    # regex path's "no activity keyword → assume 2" default, not a user request.
    s.check("defaulted (non-explicit) 2-day → no floor",
            _effective_min_length(None, None, None, "day_hike", 2, is_specific_place=False, duration_explicit=False) is None)
    s.check("explicit 3-day at a named wilderness still skips the floor",
            _effective_min_length(None, None, None, "day_hike", 3, is_specific_place=True, duration_explicit=True) is None)

    # parse() carries an explicit day count + flags it explicit; a bare place
    # doesn't. Mock geocode so no HTTP is needed.
    p._geocode = lambda place, state=None: {"lat": 35.6, "lng": -82.55, "state": "NC"}
    multi = p.parse("a 3 day hiking trip in Asheville")
    s.check("'3 day … Asheville' → duration_days 3", multi.duration_days == 3, f"got {multi.duration_days}")
    s.check("'3 day …' flagged duration_explicit", multi.duration_explicit is True)
    s.check("'3 day … Asheville' (city) gets the 30 km floor",
            multi.min_length_km == OVERNIGHT_MIN_KM_PER_DAY * 3, f"got {multi.min_length_km}")
    plain = p.parse("a hike in Asheville")
    s.check("bare 'hike in Asheville' → duration_explicit False", plain.duration_explicit is False)
    s.check("bare 'hike in Asheville' → no auto floor", plain.min_length_km is None, f"got {plain.min_length_km}")

    # A 3-day trip is Expedition rigor even on a short trail.
    from AI.rigor import rigor_tier
    s.check("short trail but 3-day trip → expedition",
            rigor_tier(4.0, 65, difficulty="EASY", duration_days=3) == "expedition")


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


def test_data_quality_fixes(s: Suite) -> None:
    print("\n[batch 2: parser typo, length ranking, markdown, Future filter, DEM denoise]")

    # ── Fix 1: DESTINATION_PREPS word boundaries — a preposition hidden inside a
    #    typo ("wn[at]" for "want") must not be captured as a place. ───────────
    import re as _re
    from AI.TripInputParser import DESTINATION_PREPS
    m_typo = _re.search(DESTINATION_PREPS, "i wnat to go backpacking in linville gorge")
    s.check("typo 'wnat' no longer donates 'at' as a preposition",
            bool(m_typo) and m_typo.group(1) == "linville gorge",
            f"got {m_typo.group(1)!r}" if m_typo else "no match")
    m_ok = _re.search(DESTINATION_PREPS, "i want to go backpacking in linville gorge")
    s.check("correct spelling still extracts the place",
            bool(m_ok) and m_ok.group(1) == "linville gorge")

    # ── Fix 5: length-proximity weight lets a correct-length trail beat a
    #    nearer-but-shorter one for "about 3 miles" (target 4.8 km). ───────────
    from types import SimpleNamespace
    from Services.HikeSearchService import (
        _proximity_bonus, _length_proximity_bonus,
        LENGTH_PROXIMITY_WEIGHT, POINT_PROXIMITY_FALLOFF_KM,
    )
    def _score(h, target):
        return (_proximity_bonus(h, POINT_PROXIMITY_FALLOFF_KM, weight=3.0)
                + _length_proximity_bonus(h, target, weight=LENGTH_PROXIMITY_WEIGHT))
    correct_far  = SimpleNamespace(length_km=4.8, distance_km=6.0, tags=[])   # ideal length, a bit farther
    short_near   = SimpleNamespace(length_km=1.71, distance_km=2.0, tags=[])  # too short, closer
    s.check("correct-length farther trail outranks short closer one (target 4.8)",
            _score(correct_far, 4.8) > _score(short_near, 4.8))
    s.check("length term is inert when no target given",
            _length_proximity_bonus(correct_far, None, weight=LENGTH_PROXIMITY_WEIGHT) == 0.0)

    # ── AI-driven ranking priority: rule-based determination (hybrid's cheap half)
    from AI.TripInputParser import _infer_primary_priority
    s.check("emphasized feature is primary",
            _infer_primary_priority(["lake"], ["lake"], [], _mi(8)) == "lake")
    s.check("sole distance (no feature) → distance is primary",
            _infer_primary_priority([], [], [], _mi(8)) == "distance")
    s.check("distance + a feature, none emphasized → ambiguous (None, Groq decides)",
            _infer_primary_priority([], ["lake"], [], _mi(8)) is None)
    s.check("two features, none emphasized → ambiguous (None)",
            _infer_primary_priority([], ["lake", "waterfall"], [], None) is None)
    s.check("nothing stated → balanced (None)",
            _infer_primary_priority([], [], [], None) is None)

    # ── Primary-driven sort: the chosen dimension leads, composite breaks ties ──
    from Services.HikeSearchService import _primary_sort_key
    far_on_len   = SimpleNamespace(length_km=12.9, distance_km=8.0, tags=["lake"])  # on target, farther
    near_off_len = SimpleNamespace(length_km=2.0,  distance_km=1.0, tags=[])        # off target, closer
    # distance-primary (target 12.9 km ≈ 8 mi): on-length wins despite being farther.
    order = sorted([(near_off_len, 5.0), (far_on_len, 1.0)],
                   key=lambda p: _primary_sort_key(p, "distance", 12.9))
    s.check("distance-primary ranks the on-target trail first",
            order[0][0] is far_on_len)
    # feature-primary ("lake"): the trail carrying the tag wins even with a lower score.
    order2 = sorted([(near_off_len, 9.0), (far_on_len, 1.0)],
                    key=lambda p: _primary_sort_key(p, "lake", None))
    s.check("feature-primary ranks the tag-matching trail first",
            order2[0][0] is far_on_len)
    # balanced (None): unchanged — higher composite score first.
    order3 = sorted([(far_on_len, 1.0), (near_off_len, 9.0)],
                    key=lambda p: _primary_sort_key(p, None, None))
    s.check("balanced falls back to composite score desc",
            order3[0][0] is near_off_len)

    # ── Fix 4a: strip stray markdown emphasis Groq emits around re-typed names ─
    from AI.TripChat import _strip_markdown_emphasis
    s.check("'**Future - High Knob Trail**' loses its asterisks",
            "*" not in _strip_markdown_emphasis("1. **Future - High Knob Trail**: 11 km"))
    s.check("inner name text is preserved",
            "Future - High Knob Trail" in _strip_markdown_emphasis("**Future - High Knob Trail**"))
    s.check("mis-placed bold ('Name (ID**:') is cleaned",
            "*" not in _strip_markdown_emphasis("**Tower Trail (ID**: e729)"))
    s.check("a lone '*' (bullet/prose) is left alone",
            _strip_markdown_emphasis("a * b") == "a * b")

    # ── Fix 4b: planned/unbuilt OSM trails are treated as noise ────────────────
    from ingestion.characterizations import is_noise
    s.check("'Future - High Knob Trail' is noise", is_noise("Future - High Knob Trail", {}) is True)
    s.check("'Proposed Greenway' is noise",        is_noise("Proposed Greenway", {}) is True)
    s.check("highway=proposed is noise",           is_noise("Some Trail", {"highway": "proposed"}) is True)
    s.check("a normal trail name is NOT noise",    is_noise("Boyd Branch Trail", {}) is False)
    s.check("a mid-word 'future' is NOT noise (prefix only)",
            is_noise("The Future Farms Loop", {}) is False)

    # ── Fix 2/3: DEM gain hysteresis denoising (_recompute is pure) ────────────
    _ing = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ingestion")
    if _ing not in sys.path:
        sys.path.insert(0, _ing)
    import backfill_elevation
    rec, pk = backfill_elevation._recompute, backfill_elevation._point_key
    def _seg(eles):
        pts = [[0.0, i * 0.001] for i in range(len(eles))]  # distinct keys at 5dp
        ebk = {pk(p[0], p[1]): e for p, e in zip(pts, eles)}
        return [[list(p) for p in pts]], ebk
    # Flat + noise (±3 m around 100): the old raw sum inflated this; hysteresis → 0.
    noisy = [100, 102, 99, 101, 98, 101, 100, 103, 98, 100, 102, 99]
    seg, ebk = _seg(noisy)
    s.check("flat noisy profile → 0 gain at 8 m band", rec(seg, ebk, 8.0)[0] == 0.0)
    s.check("same profile, raw sum (band 0) DOES inflate", rec(seg, ebk, 0.0)[0] > 8.0)
    # Clean staircase climb of 30 m is counted in full.
    seg2, ebk2 = _seg([100, 110, 120, 130])
    s.check("clean 30 m climb counted in full", rec(seg2, ebk2, 8.0)[0] == 30.0)
    # Climb then descent: only the climb counts.
    seg3, ebk3 = _seg([100, 120, 100])
    s.check("climb-then-descent counts only the climb", rec(seg3, ebk3, 8.0)[0] == 20.0)
    # A void (None — what sampling now returns for a 0 m DEM void) breaks the
    # delta chain, so a 200 m trail dropping into a void and back does NOT book a
    # phantom ~400 m spike (the Academy Loop / Field Trip inflation).
    _pts = [[0.0, 0.0], [0.0, 0.001], [0.0, 0.002]]
    _ebk = {pk(0.0, 0.0): 200.0, pk(0.0, 0.001): None, pk(0.0, 0.002): 200.0}
    s.check("a void (None) breaks the chain — no phantom spike",
            rec([[list(p) for p in _pts]], _ebk, 8.0)[0] == 0.0)

    # ── Difficulty grade-feel: the rating is length×gain blind to steepness, so
    #    a flat rail-trail must not read "Expert" and a short wall not "Easy". ──
    from ingestion.characterizations import calculate_difficulty, apply_grade_feel
    from PyObjects.Hike import DifficultyLevel as DL
    # Flat 44-mile rail-trail: rating alone → Expert; grade ~6 m/km → capped Moderate.
    s.check("flat 71km/400m rail-trail → Moderate (not Expert)",
            calculate_difficulty(71.2, 400) == DL.MODERATE)
    s.check("flat greenway 22km/214m → Moderate (not Difficult)",
            calculate_difficulty(22.4, 214) == DL.MODERATE)
    # Short steep wall: rating alone → Easy; grade 150 m/km → bumped up.
    s.check("steep 2km/300m → Moderate (bumped up from Easy)",
            calculate_difficulty(2.0, 300) == DL.MODERATE)
    s.check("short-steep 3km/500m → Difficult",
            calculate_difficulty(3.0, 500) == DL.DIFFICULT)
    # Mid-grade trails (distance & gain correlate) are left alone.
    s.check("real mountain 15km/900m stays Expert",
            calculate_difficulty(15.0, 900) == DL.EXPERT)
    s.check("Spence-like 4.6km/266m → Moderate", calculate_difficulty(4.58, 266) == DL.MODERATE)
    # apply_grade_feel in isolation: flat caps, steep bumps, mid untouched.
    s.check("apply_grade_feel: flat caps Expert→Moderate",
            apply_grade_feel(DL.EXPERT, 70.0, 400) == DL.MODERATE)
    s.check("apply_grade_feel: steep bumps Easy→Moderate",
            apply_grade_feel(DL.EASY, 2.0, 300) == DL.MODERATE)
    s.check("apply_grade_feel: mid-grade untouched",
            apply_grade_feel(DL.DIFFICULT, 15.0, 900) == DL.DIFFICULT)


def test_per_day_distance_caps(s: Suite) -> None:
    print("\n[per-day distance cap: backpacking multi-day + over-long trails hidden]")
    from types import SimpleNamespace
    from AI.TripInputParser import TripInputParser, _default_duration_days, OVERNIGHT_ACTIVITIES
    from trip_metrics import min_days_for_length, MAX_KM_PER_DAY
    from Services.HikeSearchService import HikeSearchService

    # ── _default_duration_days: overnight ⇒ ≥2 days, else 1; explicit always wins ─
    s.check("backpacking (no count) → 2 days", _default_duration_days("backpacking", None) == 2)
    s.check("overnight (no count) → 2 days",   _default_duration_days("overnight", None) == 2)
    s.check("day_hike (no count) → 1 day",     _default_duration_days("day_hike", None) == 1)
    s.check("unknown activity (no count) → 1 day", _default_duration_days(None, None) == 1)
    s.check("explicit count overrides activity", _default_duration_days("backpacking", 4) == 4)
    s.check("every overnight activity implies ≥2",
            all(_default_duration_days(a, None) >= 2 for a in OVERNIGHT_ACTIVITIES))

    # ── min_days_for_length: fewest days to stay within MAX_KM_PER_DAY (24 km) ──
    s.check("24 km fits in 1 day",   min_days_for_length(24.0) == 1)
    s.check("25 km needs 2 days",    min_days_for_length(25.0) == 2)
    s.check("48 km fits in 2 days",  min_days_for_length(48.0) == 2)
    s.check("90 km needs 4 days",    min_days_for_length(90.0) == 4)
    s.check("182 km needs 8 days",   min_days_for_length(182.0) == 8)  # the Falls Lake bug
    s.check("None/0 length → 1 day", min_days_for_length(None) == 1 and min_days_for_length(0) == 1)

    # An extended day count keeps every split leg within the cap — the whole point
    # (a 113-mile trail no longer crammed into one day). Assert via split_days.
    from trip_metrics import split_days, km_to_miles
    legs = split_days(182.0, 0, min_days_for_length(182.0))
    cap_mi = km_to_miles(MAX_KM_PER_DAY)
    s.check("182 km split over its min days → every leg ≤ cap",
            all(mi <= cap_mi + 0.1 for mi, _ in legs), f"legs={legs} cap={cap_mi}")

    # ── "backpacking near me" now defaults to a multi-day trip (was 1 day) ──────
    p = TripInputParser()
    bp = p.parse("i want to go on a backpacking trip near me", user_lat=35.2, user_lng=-80.8)
    s.check("'backpacking near me' → 2 days", bp.duration_days == 2, f"got {bp.duration_days}")
    s.check("'backpacking near me' activity backpacking", bp.activity_type == "backpacking")
    s.check("'backpacking near me' flagged ambiguous (confirm the count)", bp.duration_ambiguous is True)
    s.check("'backpacking near me' not duration_explicit", bp.duration_explicit is False)

    # ── find_hikes_for_intent derives a per-day ceiling from duration when the
    #    user named none (stub the DB so we assert the max_length_km it passes). ─
    calls: list[dict] = []
    fake_hs = SimpleNamespace(search_hikes=lambda **kw: (calls.append(kw), [])[1])
    svc = HikeSearchService(fake_hs)

    def _intent(duration_days=2, max_length_km=None, **extra):
        base = dict(
            lat=35.0, lng=-80.0, avoid_permits=False, difficulty_hint=None,
            destination_type="point", duration_days=duration_days,
            required_tags=[], preferred_tags=[], priority_tags=[],
            min_length_km=None, max_length_km=max_length_km, target_length_km=None,
            region_tag=None, state=None, primary_priority=None,
        )
        base.update(extra)
        return SimpleNamespace(**base)

    calls.clear(); svc.find_hikes_for_intent(_intent(duration_days=2))
    s.check("2-day trip caps trail at 2 × MAX_KM_PER_DAY",
            calls[-1]["max_length_km"] == MAX_KM_PER_DAY * 2, f"got {calls[-1]['max_length_km']}")
    calls.clear(); svc.find_hikes_for_intent(_intent(duration_days=1))
    s.check("1-day trip caps trail at MAX_KM_PER_DAY (≈15 mi)",
            calls[-1]["max_length_km"] == MAX_KM_PER_DAY, f"got {calls[-1]['max_length_km']}")
    calls.clear(); svc.find_hikes_for_intent(_intent(duration_days=1, max_length_km=10.0))
    s.check("a user-typed max is never overridden by the cap",
            calls[-1]["max_length_km"] == 10.0, f"got {calls[-1]['max_length_km']}")
    calls.clear(); svc.find_hikes_for_intent(_intent(duration_days=2, max_km_per_day_cap=None))
    s.check("cap disabled (last-resort pass) → no derived ceiling",
            calls[-1]["max_length_km"] is None, f"got {calls[-1]['max_length_km']}")


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
    test_phantom_place_and_multiday(s)
    test_feature_honesty(s)
    test_data_quality_fixes(s)
    test_per_day_distance_caps(s)

    s.summary()
    sys.exit(s.exit_code())


if __name__ == "__main__":
    main()
