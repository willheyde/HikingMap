# AI/TripInputParser.py
from pydoc import text
import re
import httpx
from dataclasses import dataclass, field
from typing import Optional
from groq import Groq
import json
import os

# ── Activity keywords ──────────────────────────────────────────────────────────
# Assumed flat hiking pace, used only to convert a stated time budget for a
# single hike ("2 hour max", "back in 3 hrs") into an approximate distance
# ceiling. This is explicitly an estimate, not a promise — real pace varies
# with elevation, fitness, and terrain. Tune this constant if it's off.
ASSUMED_HIKING_PACE_KMH: float = 3.0

_TIME_BUDGET_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hour|hr)s?\b", re.IGNORECASE)
KM_PER_MILE: float = 1.60934

_MILE_RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*mi(?:les?)?\b", re.IGNORECASE
)
_MILE_CEILING_RE = re.compile(
    r"(?:under|less than|no more than|at most|up to|max(?:imum)?(?:\s+of)?)\s*"
    r"(\d+(?:\.\d+)?)\s*mi(?:les?)?\b", re.IGNORECASE
)
_MILE_SINGLE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mi(?:les?)?\b", re.IGNORECASE)
# ← NEW: must be checked BEFORE _MILE_SINGLE_RE, since "around 3 miles" also
# satisfies the bare-number pattern and would otherwise be silently treated
# as a hard ceiling with the word "around" thrown away.
_MILE_APPROX_RE = re.compile(
    r"(?:around|about|roughly|approximately)\s*(\d+(?:\.\d+)?)\s*mi(?:les?)?\b",
    re.IGNORECASE,
)
_NEGATED_DIFFICULTY_RE = re.compile(
    r"\b(?:no|not|nothing|without|avoid)\b(?:\s+\w+){0,6}\s+"
    r"\b(?:strenuous|difficult|hard|challeng\w*)\b"
)
ACTIVITY_KEYWORDS = {
    "day_hike":       ["day hike", "day trip", "morning hike", "afternoon hike"],
    "overnight":      ["overnight", "spend a night", "one night", "1 night"],
    "backpacking":    ["backpack", "backpacking", "multi-day", "multiday", "several days"],
    "extended":       ["week", "7 days", "10 days", "long trip", "thru"],
    "mountaineering": ["glacier", "summit", "mountaineer", "ice axe", "crampon", "alpine"],
}

DURATION_PATTERNS = [
    (r"(\d+)\s*night",    lambda m: int(m.group(1)) + 1),
    (r"(\d+)\s*day",      lambda m: int(m.group(1))),
    (r"a\s+night",        lambda m: 2),
    (r"a\s+weekend",      lambda m: 3),
    (r"a\s+week",         lambda m: 7),
    (r"a\s+few\s+days",   lambda m: 3),
]

DESTINATION_PREPS = r"(?:in|near|at|around|through|across)\s+(?:the\s+)?(.+?)(?:\s+for|\s+this|\s+and|\.|$)"

# ── Tag derivation maps ────────────────────────────────────────────────────────

ACTIVITY_DURATION_TAGS: dict[str, list[str]] = {
    "day_hike":       ["short", "half_day", "full_day"],
    "overnight":      ["overnight"],
    "backpacking":    ["overnight", "multi_day"],
    "extended":       ["multi_day"],
    "mountaineering": ["full_day", "overnight", "multi_day"],
}

DIFFICULTY_GAIN_TAGS: dict[str, list[str]] = {
    "easy":     ["flat", "gentle_gain"],
    "moderate": ["moderate_gain", "gentle_gain"],
    "hard":     ["high_gain", "very_high_gain"],
}

FEATURE_KEYWORD_MAP: dict[str, list[str]] = {
    "waterfall":    ["waterfall", "falls", "cascade"],
    "lake":         ["lake", "pond", "tarn", "swimming hole", "swim"],
    "summit":       ["summit", "peak", "mountaintop", "highest point", "top of"],
    "canyon":       ["canyon", "gorge", "slot canyon", "ravine"],
    "ridge":        ["ridge", "ridgeline", "exposed ridge"],
    "glacier":      ["glacier", "glacial", "icefield"],
    "meadow":       ["meadow", "open field"],
    "wildflower":   ["wildflower", "wildflowers"],
    "forest":       ["forest", "woods", "wooded", "tree cover"],
    "beach":        ["beach", "coastal", "shoreline", "ocean"],
    "cave":         ["cave", "cavern", "grotto"],
    "viewpoint":    ["view", "views", "overlook", "vista", "scenic", "scenery"],
    "hot_spring":   ["hot spring", "hot springs", "thermal"],
    "river":        ["river", "creek", "stream", "waterway"],
    "historic":     ["historic", "ruins", "petroglyphs", "old growth"],
    "desert":       ["desert", "arid", "cactus", "red rock"],
    "montane":      ["montane", "mountain", "mountainous", "highland", "highlands", "high country"],
    "subalpine":    [
        "subalpine", "alpine", "above treeline", "above tree line",
        "high alpine", "exposed", "treeline", "near treeline",
    ],
    "lowland":      ["lowland", "flat ground", "gentle terrain"],
    "seasonal":     [
        "seasonal", "spring or fall", "spring/fall",
        "shoulder season", "seasonal access", "open seasonally",
    ],
    "technical":    [
        "technical", "scramble", "scrambling", "via ferrata",
        "rock hopping", "bouldering", "exposed scramble",
    ],
    "family":       [
        "family friendly", "family-friendly", "kid friendly",
        "kid-friendly", "with kids", "good for kids", "toddler",
        "stroller friendly",
    ],
    "water_feature": ["water feature", "water source", "near water", "by the water", "on the water"],
}
# Keys in FEATURE_KEYWORD_MAP that are ALSO keys in HikeSearchService.CONCEPT_EXPANSIONS —
# these expand to multiple DB tags with OR semantics, so they can't be a hard
# SQL @> filter. Everything else is a direct 1:1 DB tag and should hard-filter.
# Must stay in sync with CONCEPT_EXPANSIONS keys (no import to avoid a cycle).
CONCEPT_FEATURE_TAGS: frozenset[str] = frozenset({"water_feature", "seasonal", "family", "wildflower"})
# Flattened set of every literal keyword phrase across FEATURE_KEYWORD_MAP's
# values. Two uses: (1) the existing keyword-matching loop in _extract_tags,
# and (2) has_location_signal() below, where it filters out preposition
# candidates that describe a FEATURE ("near a lake") rather than naming a
# PLACE ("near Asheville"). Single source of truth — grows automatically
# whenever a feature/keyword pair is added above, with no second list to
# keep in sync (trip_chat.py imports this directly rather than maintaining
# its own copy).
ALL_FEATURE_KEYWORDS: frozenset[str] = frozenset(
    kw for kws in FEATURE_KEYWORD_MAP.values() for kw in kws
)

# Common filler words that can precede a feature noun without changing
# whether the phrase names a place. "near a really nice lake" should still
# be recognized as a feature phrase, not a place, once these are stripped.
_LOCATION_CANDIDATE_FILLER_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "some", "any", "really", "very",
    "nice", "good", "great", "beautiful", "pretty",
    "small", "big", "little",
})

CAMPING_ACTIVITIES  = {"overnight", "backpacking", "extended"}
CAMPING_KEYWORDS    = ["camping", " camp ", "campsite", "base camp", "bivouac", "sleep out", "spend the night"]
NO_PERMIT_KEYWORDS  = ["no permit", "without permit", "permit-free", "don't need a permit", "no reservation"]
EMPHASIS_PHRASES    = [
    "really want", "really need", "must have", "have to have",
    "need to have", "needs to have", "needs to include",
    "definitely want", "non-negotiable", "top priority",
    "most important", "make sure", "absolutely need", "absolutely want",
]

# ── Geographic region keywords ────────────────────────────────────────────────
#
# Named mountain ranges, trail corridors, and macro-regions that map to the
# hikes.region column.  Kept separate from STATE_KEYWORDS so the two can be
# matched and stored independently on TripIntent.

REGION_KEYWORDS: dict[str, str] = {
    "appalachian":          "appalachian",
    "appalachians":         "appalachian",
    "appalachian trail":    "appalachian",
    "the rockies":          "rockies",
    "rocky mountains":      "rockies",
    "cascades":             "cascades",
    "cascade range":        "cascades",
    "the south":            "south",
    "sierra nevada":        "sierra_nevada",
    "sierras":              "sierra_nevada",
    "white mountains":      "white_mountains",
    "adirondacks":          "adirondacks",
    "adirondack mountains": "adirondacks",
    "catskills":            "catskills",
    "catskill mountains":   "catskills",
    "smokies":              "smokies",
    "great smoky mountains":"smokies",
    "smoky mountains":      "smokies",
    "blue ridge":           "blue_ridge",
    "blue ridge mountains": "blue_ridge",
    "ozarks":               "ozarks",
    "ozark mountains":      "ozarks",
    "pnw":                  "pnw",
    "pacific northwest":    "pnw",
    "olympics":             "olympics",
    "olympic peninsula":    "olympics",
    "wasatch":              "wasatch",
    "wasatch range":        "wasatch",
    "tetons":               "tetons",
    "grand tetons":         "tetons",
    "shenandoah":           "shenandoah",
    "green mountains":      "green_mountains",
    "black hills":          "black_hills",
}

# ── US state keywords ─────────────────────────────────────────────────────────
#
# Maps full state names to the normalised value stored in hikes.state.
# Two-letter abbreviations are intentionally omitted — they appear too often
# in ordinary text ("ok", "or", "in") to be safe pattern matches.
# Normalisation uses lowercase with underscores so it can round-trip cleanly
# through the DB column (TEXT, case-sensitive exact match in HikeRepo.search).

STATE_KEYWORDS: dict[str, str] = {
    "alabama":        "AL",
    "alaska":         "AK",
    "arizona":        "AZ",
    "arkansas":       "AR",
    "california":     "CA",
    "colorado":       "CO",
    "connecticut":    "CT",
    "delaware":       "DE",
    "florida":        "FL",
    "georgia":        "GA",
    "hawaii":         "HI",
    "idaho":          "ID",
    "illinois":       "IL",
    "indiana":        "IN",
    "iowa":           "IA",
    "kansas":         "KS",
    "kentucky":       "KY",
    "louisiana":      "LA",
    "maine":          "ME",
    "maryland":       "MD",
    "massachusetts":  "MA",
    "michigan":       "MI",
    "minnesota":      "MN",
    "mississippi":    "MS",
    "missouri":       "MO",
    "montana":        "MT",
    "nebraska":       "NE",
    "nevada":         "NV",
    "new hampshire":  "NH",
    "new jersey":     "NJ",
    "new mexico":     "NM",
    "new york":       "NY",
    "north carolina": "NC",
    "north dakota":   "ND",
    "ohio":           "OH",
    "oklahoma":       "OK",
    "oregon":         "OR",
    "pennsylvania":   "PA",
    "rhode island":   "RI",
    "south carolina": "SC",
    "south dakota":   "SD",
    "tennessee":      "TN",
    "texas":          "TX",
    "utah":           "UT",
    "vermont":        "VT",
    "virginia":       "VA",
    "washington":     "WA",
    "west virginia":  "WV",
    "wisconsin":      "WI",
    "wyoming":        "WY",
}
STATE_ABBREVIATIONS: frozenset[str] = frozenset(STATE_KEYWORDS.values())
_STATE_ABBR_TO_NAME: dict[str, str] = {v: k for k, v in STATE_KEYWORDS.items()}

# Abbreviations that collide with common English words, pronouns, or
# prepositions. These are only trusted as a state match when they appear
# ALL CAPS in the user's ORIGINAL (pre-lowercased) message — "NC" counts,
# "in"/"me"/"ok"/"or" typed normally in a sentence don't. Non-ambiguous
# codes (NC, VA, TX, ...) aren't real English words on their own, so they
# match regardless of case.
AMBIGUOUS_STATE_ABBREVIATIONS: frozenset[str] = frozenset({
    "IN", "ME", "OK", "OR", "HI", "PA", "MA",
})


def _find_state_abbreviation(source: str) -> Optional[str]:
    """
    Scans `source` for a 2-letter US state code. `source` MUST be the
    original-case text (not pre-lowercased) — case is how ambiguous codes
    are disambiguated from ordinary words.

    Single source of truth for this check — used by both
    _extract_destination_type() and has_location_signal() so the two can't
    drift out of sync the way the old duplicated regex logic did.
    """
    for m in re.finditer(r'\b[A-Za-z]{2}\b', source):
        token = m.group(0)
        upper = token.upper()
        if upper not in STATE_ABBREVIATIONS:
            continue
        if upper in AMBIGUOUS_STATE_ABBREVIATIONS and token != upper:
            continue  # ambiguous code wasn't actually capitalized in source
        return upper
    return None


# ── TripIntent dataclass ───────────────────────────────────────────────────────

@dataclass
class TripIntent:
    destination_raw:  str
    destination_full: str
    lat:              float
    lng:              float
    activity_type:    str
    duration_days:    int
    difficulty_hint:  Optional[str]
    raw_goal:         str
    required_tags:    list[str] = field(default_factory=list)
    preferred_tags:   list[str] = field(default_factory=list)
    priority_tags:    list[str] = field(default_factory=list)
    avoid_permits:    bool = False
    destination_type: str  = "point"
    region_tag:       Optional[str] = None
    state:            Optional[str] = None    # ← NEW: matches hikes.state column
    max_length_km:    Optional[float] = None
    target_length_km: Optional[float] = None


@dataclass
class RefinementIntent:
    """
    Tag/preference extraction only — no destination resolution.
    See docstring in TripInputParser.parse_refinement().
    """
    activity_type:   Optional[str]
    duration_days:   Optional[int]
    difficulty_hint: Optional[str]
    required_tags:   list[str]
    preferred_tags:  list[str]
    priority_tags:   list[str]
    avoid_permits:   bool
    max_length_km:    Optional[float] = None   # ← NEW
    target_length_km: Optional[float] = None


# ── Parser ─────────────────────────────────────────────────────────────────────
NEAR_ME_PATTERNS = [
            r"\bnear\s+me\b",
            r"\bnearby\b",
            r"\bclose\s+to\s+me\b",
            r"\baround\s+me\b",
            r"\blocal\s+hike\b",
            r"\bnear\s+my\s+location\b",
            r"\bnear\s+where\s+i\s+am\b",
        ]
class TripInputParser:
    def __init__(self):
        self._groq = Groq(api_key=os.environ["HikeKey"])
        _AI_DIR   = os.path.dirname(os.path.abspath(__file__))
        _BASE_DIR = os.path.dirname(_AI_DIR)
        lookup_path = os.path.join(_BASE_DIR, 'Services', 'parks_lookup.json')
        with open(lookup_path, 'r') as f:
            self.national_parks = json.load(f)
        self.park_keys = sorted(self.national_parks.keys(), key=len, reverse=True)
    
    def parse(
        self,
        user_input: str,
        user_lat:   Optional[float] = None,
        user_lng:   Optional[float] = None,
    ) -> TripIntent:
        text = user_input.lower().strip()
        max_length_km, target_length_km = self._extract_length_constraints(text)   # ← renamed

        if any(re.search(p, text) for p in NEAR_ME_PATTERNS):
            if user_lat is None or user_lng is None:
                raise ValueError(
                    "You said 'near me' but no location was shared — "
                    "please enable location in the app or name a specific place."
                )
            activity   = self._extract_activity(text)
            duration   = self._extract_duration(text)
            difficulty = self._extract_difficulty(text)
            required, preferred, avoid_permits, priority = self._extract_tags(text, activity, difficulty)
            _, region_tag, state = self._extract_destination_type(
                text, raw_text=user_input, allow_abbreviations=False
            )
            return TripIntent(
                destination_raw  = "near me",
                destination_full = "Near your current location",
                lat              = user_lat,
                lng              = user_lng,
                activity_type    = activity or "day_hike",
                duration_days    = duration or 1,
                difficulty_hint  = difficulty,
                raw_goal         = user_input,
                required_tags    = required,
                preferred_tags   = preferred,
                priority_tags    = priority,
                avoid_permits    = avoid_permits,
                destination_type = "point",
                region_tag       = region_tag,
                state            = state,
                max_length_km    = max_length_km,
                target_length_km = target_length_km,   # ← NEW
            )

        destination_raw = self._extract_destination_regex(text, raw_text=user_input)
        activity        = self._extract_activity(text)
        duration        = self._extract_duration(text)
        difficulty      = self._extract_difficulty(text)
        required, preferred, avoid_permits, priority = self._extract_tags(text, activity, difficulty)
        dest_type, region_tag, regex_state = self._extract_destination_type(text, raw_text=user_input)
        state = regex_state   # ← Bug 1 fix: seed state so the LLM-fallback path below always has a value

        if destination_raw:
            destination_full = self.national_parks.get(destination_raw, destination_raw.title())
            coords = self._geocode(destination_full)
            if coords:
                state = coords.get("state") or regex_state
                return TripIntent(
                    destination_raw  = destination_raw,
                    destination_full = destination_full,
                    lat              = coords["lat"],
                    lng              = coords["lng"],
                    activity_type    = activity or "day_hike",
                    duration_days    = duration or (1 if activity == "day_hike" else 2),
                    difficulty_hint  = difficulty,
                    raw_goal         = user_input,
                    required_tags    = required,
                    preferred_tags   = preferred,
                    priority_tags    = priority,
                    avoid_permits    = avoid_permits,
                    destination_type = dest_type,
                    region_tag       = region_tag,
                    state            = state,
                    max_length_km    = max_length_km,
                    target_length_km = target_length_km,   # ← NEW
                )

        extracted = self._llm_extract(user_input)
        dest = extracted.get("destination") or ""
        destination_full = self.national_parks.get(dest.lower(), dest)
        coords = self._geocode(destination_full)
        if not coords:
            raise ValueError(f"Could not locate '{destination_full}' — try being more specific.")

        llm_features = extracted.get("features", [])
        preferred = sorted(set(preferred) | {f for f in llm_features if f in FEATURE_KEYWORD_MAP})

        return TripIntent(
            destination_raw  = extracted.get("destination", destination_full),
            destination_full = destination_full,
            lat              = coords["lat"],
            lng              = coords["lng"],
            activity_type    = extracted.get("activity_type") or activity or "day_hike",
            duration_days    = extracted.get("duration_days") or duration or 1,
            difficulty_hint  = extracted.get("difficulty") or difficulty,
            raw_goal         = user_input,
            required_tags    = required,
            preferred_tags   = preferred,
            priority_tags    = priority,
            avoid_permits    = avoid_permits,
            destination_type = dest_type,
            region_tag       = region_tag,
            state            = state,
            max_length_km    = max_length_km,
            target_length_km = target_length_km,   # ← NEW
    )

    def parse_refinement(self, user_input: str) -> RefinementIntent:
        text       = user_input.lower().strip()
        activity   = self._extract_activity(text)
        duration   = self._extract_duration(text)
        difficulty = self._extract_difficulty(text)
        required, preferred, avoid_permits, priority = self._extract_tags(text, activity, difficulty)
        max_length_km, target_length_km = self._extract_length_constraints(text)   # ← NEW
        return RefinementIntent(
            activity_type    = activity,
            duration_days    = duration,
            difficulty_hint  = difficulty,
            required_tags    = required,
            preferred_tags   = preferred,
            priority_tags    = priority,
            avoid_permits    = avoid_permits,
            max_length_km    = max_length_km,       # ← NEW
            target_length_km = target_length_km,    # ← NEW
        )
    def _extract_length_constraints(self, text: str) -> tuple[Optional[float], Optional[float]]:
        """
        Returns (max_length_km, target_length_km).

        max_length_km is the hard ceiling forwarded to HikeService.search_hikes()
        -> HikeRepository.search() as `length_km <= ...`.

        target_length_km is set ONLY for approximate phrasing ("around 3 miles")
        and is never passed to the DB — HikeSearchService's length-proximity
        scoring term uses it so a 3.4mi trail actually outranks a 1.8mi trail
        when the user asked for "around 3 miles," instead of length dropping out
        of ranking entirely once a trail clears the ceiling.

        An approximate mention still loosens the ceiling to target*1.2 so a
        trail slightly over the ballpark number isn't hard-excluded before
        scoring gets a chance to weigh in.
        """
        m = _MILE_RANGE_RE.search(text)
        if m:
            return round(max(float(m.group(1)), float(m.group(2))) * KM_PER_MILE, 1), None

        m = _MILE_CEILING_RE.search(text)
        if m:
            return round(float(m.group(1)) * KM_PER_MILE, 1), None

        m = _MILE_APPROX_RE.search(text)
        if m:
            target_km = round(float(m.group(1)) * KM_PER_MILE, 1)
            return round(target_km * 1.2, 1), target_km

        m = _MILE_SINGLE_RE.search(text)
        if m:
            return round(float(m.group(1)) * KM_PER_MILE, 1), None

        return self._extract_time_budget_km(text), None
    def _extract_time_budget_km(self, text: str) -> Optional[float]:
        """
        Converts a stated single-hike time budget into an approximate
        max_length_km ceiling via ASSUMED_HIKING_PACE_KMH. Only the first hour
        figure in the message is used. Returns None if no hour figure present.
        """
        match = _TIME_BUDGET_RE.search(text)
        if not match:
            return None
        hours = float(match.group(1))
        if hours <= 0:
            return None
        return round(hours * ASSUMED_HIKING_PACE_KMH, 1)
    def _extract_tags(
        self,
        text:       str,
        activity:   Optional[str],
        difficulty: Optional[str],
        infer_duration_default: bool = True,
    ) -> tuple[list[str], list[str], bool, list[str]]:
        required:  set[str] = set()
        preferred: set[str] = set()
        mentioned_features: set[str] = set()

        needs_camping = (
            activity in CAMPING_ACTIVITIES
            or any(kw in text for kw in CAMPING_KEYWORDS)
        )
        if needs_camping:
            required.add("can_camp")

        if activity is not None:
            preferred.update(ACTIVITY_DURATION_TAGS.get(activity, []))
        elif infer_duration_default:
            preferred.update(ACTIVITY_DURATION_TAGS["day_hike"])

        if difficulty:
            preferred.update(DIFFICULTY_GAIN_TAGS.get(difficulty, []))

        for tag, keywords in FEATURE_KEYWORD_MAP.items():
            if any(kw in text for kw in keywords):
                if tag in CONCEPT_FEATURE_TAGS:
                    preferred.add(tag)
                else:
                    required.add(tag)
                mentioned_features.add(tag)

        avoid_permits = any(kw in text for kw in NO_PERMIT_KEYWORDS)

        if activity == "mountaineering":
            preferred.update(["subalpine", "summit"])

        has_emphasis = any(p in text for p in EMPHASIS_PHRASES)
        priority = sorted(mentioned_features) if has_emphasis else []

        preferred -= required
        return sorted(required), sorted(preferred), avoid_permits, priority

    # ── Regex helpers ──────────────────────────────────────────────────────────

    def _extract_destination_regex(self, text: str, raw_text: Optional[str] = None) -> Optional[str]:
        for key in self.park_keys:
            if re.search(r'\b' + re.escape(key) + r'\b', text):
                return key
        match = re.search(DESTINATION_PREPS, text)
        if match:
            candidate = match.group(1).strip().rstrip(".,")
            if len(candidate) > 2:
                return candidate
            if len(candidate) == 2:
                # Bare 2-letter destination ("hike in NC"): the length guard
                # above exists to reject junk like "in ok" (fine, not a real
                # word), but it was also silently rejecting real state codes,
                # forcing every one of these through the full LLM-extraction
                # fallback just to re-derive a place name the regex-based
                # state matcher already knows — burning a Groq call (and its
                # tokens) for nothing. Reuse the same ambiguity-safe check
                # used elsewhere so "NC" still resolves directly while "ok"/
                # "in" typed as ordinary words still don't.
                code = _find_state_abbreviation(raw_text if raw_text is not None else text)
                if code and code.lower() == candidate:
                    return _STATE_ABBR_TO_NAME.get(code, candidate)
        return None
    def has_location_signal(self, text: str) -> bool:
        """
        True if `text` contains any recognizable location reference: a
        "near me" phrase, a national park/monument from parks_lookup.json,
        a US state (any of the 50 in STATE_KEYWORDS, full name or 2-letter
        code), a named region/range (REGION_KEYWORDS), or a destination
        preposition phrase ("near X", "in X") where X isn't just a trail
        feature in disguise.

        Single source of truth for "does this message name (or imply) a
        place" — shared between this parser's own destination resolution
        and trip_chat.py's no-location short-circuit. Built entirely from
        the same lookup tables _extract_destination_type() and
        _extract_destination_regex() already use, so coverage automatically
        stays in sync as STATE_KEYWORDS/REGION_KEYWORDS/parks_lookup.json
        grow — there's no separate hardcoded list to go stale as the hikes
        dataset expands past NC/RI into more states.

        The preposition-phrase check is deliberately conservative in one
        direction: it strips filler words and skips the candidate only when
        every remaining word is a known feature keyword ("near a lake" →
        skip). Anything else with a real word after the preposition counts
        as a location, even if it's a place we don't recognize yet (a town
        name not in any lookup). That's the safer failure mode — worst case
        it costs one wasted parse/geocode cycle, instead of telling someone
        who already named a real place "where would you like to go?"
        """
        if not text or not text.strip():
            return False
        t = text.lower().strip()

        if any(re.search(p, t) for p in NEAR_ME_PATTERNS):
            return True

        if any(re.search(r'\b' + re.escape(key) + r'\b', t) for key in self.park_keys):
            return True

        # Full state names — all 50 already enumerated in STATE_KEYWORDS,
        # so this scales to any state the hikes table grows into with no
        # changes needed here.
        if any(name in t for name in STATE_KEYWORDS if len(name) > 2):
            return True

        # Two-letter state codes. Use the ORIGINAL-case `text` param here
        # (not `t`, which was already lowercased above) — ambiguous codes
        # like IN/ME/OK/OR only count when actually capitalized in the
        # source message. See _find_state_abbreviation() for the shared
        # logic with _extract_destination_type's second pass.
        if _find_state_abbreviation(text) is not None:
            return True

        # Named regions / mountain ranges / trail corridors
        if any(phrase in t for phrase in REGION_KEYWORDS if len(phrase) > 2):
            return True

        # Generic destination preposition — but only counts if the captured
        # candidate isn't entirely made of feature words ("a lake", "a
        # scenic viewpoint" don't count; "Asheville", "the Pisgah area" do).
        match = re.search(DESTINATION_PREPS, t)
        if match:
            candidate = match.group(1).strip().rstrip(".,")
            candidate_words = [
                w for w in candidate.split()
                if w not in _LOCATION_CANDIDATE_FILLER_WORDS
            ]
            is_feature_phrase = candidate_words and all(
                w in ALL_FEATURE_KEYWORDS for w in candidate_words
            )
            if len(candidate) > 2 and not is_feature_phrase:
                return True

        return False
    def _extract_activity(self, text: str) -> Optional[str]:
        for activity, keywords in ACTIVITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return activity
        return None

    def _extract_duration(self, text: str) -> Optional[int]:
        for pattern, fn in DURATION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return fn(match)
        return None

    def _extract_difficulty(self, text: str) -> Optional[str]:
        # "nothing strenuous" / "not too difficult" mean the user wants EASY —
        # check this before the positive keyword scan below, since those same
        # words ("strenuous", "difficult") would otherwise trip the hard-keyword
        # branch and flip the request's intent to the opposite of what was asked.
        if _NEGATED_DIFFICULTY_RE.search(text):
            return "easy"
        if any(w in text for w in ["easy", "beginner", "casual", "leisure"]):
            return "easy"
        if any(w in text for w in ["moderate", "medium", "intermediate"]):
            return "moderate"
        if any(w in text for w in ["hard", "difficult", "challenge", "challenging", "push myself", "strenuous"]):
            return "hard"
        return None

    def _extract_destination_type(
        self,
        text: str,
        raw_text: Optional[str] = None,
        allow_abbreviations: bool = True,
    ) -> tuple[str, Optional[str], Optional[str]]:
        """
        Returns (dest_type, region_tag, state).

        Scans REGION_KEYWORDS and STATE_KEYWORDS independently so both can be
        set simultaneously (e.g. "hiking in the Rockies in Colorado" → region=rockies,
        state=colorado).

        `text` should be the lowercased input (used for full-name/region
        matching, which is safely case-insensitive). `raw_text`, if given,
        should be the ORIGINAL-case input — it's required to correctly
        disambiguate 2-letter codes; passing only the lowercased `text` here
        means every 2-letter word looks identical and ambiguous codes like
        IN/ME can't be told apart from ordinary words. Falls back to `text`
        if `raw_text` isn't provided (abbreviation matching will then be
        more conservative, matching only non-ambiguous codes as literal
        lowercase — still safe, just less permissive).

        dest_type is "region" when either is matched, "point" otherwise.
        """
        region_tag: Optional[str] = None
        state:      Optional[str] = None

        # Long phrases first (no length guard needed — these are unambiguous)
        for phrase, tag in sorted(REGION_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if len(phrase) <= 2:
                continue
            if phrase in text:
                region_tag = tag
                break

        # Full state names — same guard as before
        for phrase, tag in sorted(STATE_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if len(phrase) <= 2:
                continue   # skip the 2-letter codes in this pass
            if phrase in text:
                state = tag
                break

        # Second pass: two-letter codes only. Must use the ORIGINAL-case
        # source — `text` here has already been lowercased by the caller,
        # so checking case on it would be a no-op (this was the actual bug:
        # uppercasing an already-lowercased string makes every 2-letter word
        # look capitalized, so "in"/"me"/"ok"/"or" matched right alongside
        # "nc"/"va", and whichever appeared first in the sentence won).
        if state is None and allow_abbreviations:
            source = raw_text if raw_text is not None else text
            state = _find_state_abbreviation(source)

        dest_type = "region" if (region_tag or state) else "point"
        return dest_type, region_tag, state

    # ── LLM fallback ──────────────────────────────────────────────────────────

    def _llm_extract(self, text: str) -> dict:
        valid_features = sorted(FEATURE_KEYWORD_MAP.keys())
        response = self._groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract hiking trip intent from the user's message. "
                        "Respond ONLY with JSON, no other text:\n"
                        '{"destination": "string", '
                        '"activity_type": "day_hike|overnight|backpacking|extended|mountaineering", '
                        '"duration_days": int, '
                        '"difficulty": "easy|moderate|hard|null", '
                        f'"features": [/* zero or more of: {", ".join(valid_features)} */]'
                        "}"
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)

    # ── Geocoding ──────────────────────────────────────────────────────────────

    def _geocode(self, place: str) -> Optional[dict]:
        try:
            r = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": place, "format": "json", "limit": 1, "addressdetails": 1},  # ← NEW
                headers={"User-Agent": "HikeBuilder/1.0"},
                timeout=5.0,
            )
            results = r.json()
            if results:
                addr = results[0].get("address", {})
                state_name = addr.get("state")
                return {
                    "lat":   float(results[0]["lat"]),
                    "lng":   float(results[0]["lon"]),
                    "state": STATE_KEYWORDS.get(state_name.lower()) if state_name else None,  # ← NEW
                }
        except Exception:
            pass
        return None