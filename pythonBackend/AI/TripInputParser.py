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

# A bare mileage ("8 mile hike") is a TARGET, not a ceiling — a hard band around
# it (±30%) so a request for 8 miles never surfaces a 2-mile trail. The target
# also turns on HikeSearchService's length-proximity ranking. Deliberately
# tighter than "around N" (which stays a soft, floor-less +20% ceiling): a bare
# number reads as more committed than "around."
SINGLE_MILE_FLOOR_FACTOR: float = 0.7   # "8 mi" → floor ~5.6 mi
SINGLE_MILE_CEIL_FACTOR:  float = 1.3   # "8 mi" → ceiling ~10.4 mi

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
# ← NEW: length FLOOR ("at least 3 miles", "minimum 3mi", "over 3 miles",
# "longer than 3 miles"). Must be checked BEFORE _MILE_SINGLE_RE, since the
# bare-number pattern also matches the "3 miles" inside "at least 3 miles" and
# would otherwise treat a MINIMUM as a MAXIMUM — silently inverting the request
# and hard-excluding the very trails that satisfy it.
_MILE_FLOOR_RE = re.compile(
    r"\b(?:at least|no less than|no fewer than|min(?:imum)?(?:\s+of)?|"
    # "(?<!no )more than" so the ceiling phrase "no more than" (at most) is NOT
    # swallowed here — text reaching this is already lowercased by the caller.
    r"(?<!no )more than|over|longer than|greater than)\s*"
    r"(\d+(?:\.\d+)?)\s*mi(?:les?)?\b",
    re.IGNORECASE,
)
# The trailing-plus floor form: "3+ miles", "5+ mi".
_MILE_FLOOR_PLUS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+\s*mi(?:les?)?\b", re.IGNORECASE
)
# ← NEW: a length the user is REJECTING, not requesting. In a mid-chat refine
# like "8 miles is too long, can we look at 4 mile hikes instead", the length
# extractors below take the FIRST mile number they see — which is the "8" the
# user just said was wrong — and silently re-search the same distance the user
# asked to move away from. Strip the rejected span BEFORE extraction so only the
# number the user actually wants ("4 mile") survives. Two shapes:
#   1. "<N> mi[les] … too long/far/big/much/short"   ("8 miles is too long")
#   2. "not/instead of/rather than <N> mi[les]"        ("not 8 miles")
# The {0,3} word window in (1) tolerates "is", "would be", "is a bit", etc.
_REJECTED_LENGTH_RES = [
    re.compile(
        r"\b\d+(?:\.\d+)?\s*mi(?:les?)?\b(?:\s+\w+){0,3}?\s*"
        r"\btoo\s+(?:long|far|much|big|short|small|extreme|intense)\b",
        re.IGNORECASE,
    ),
    # NB: deliberately excludes "no more than N miles" — that's a real ceiling
    # (_MILE_CEILING_RE), not a rejected length. The optional article lets
    # "instead of an 8 mile hike" strip too (not just "instead of 8 miles").
    re.compile(
        r"\b(?:not|instead of|rather than)\s+(?:an?\s+)?"
        r"\d+(?:\.\d+)?\s*mi(?:les?)?\b",
        re.IGNORECASE,
    ),
]
# ← NEW: a UNIT-LESS floor clause — "at least 3", "no less than 5", "minimum of
# 4", "more than 6" with NO trailing mi/km. Companion to _MILE_FLOOR_RE for the
# DESTINATION strip ONLY. When the unit rode on an earlier clause ("no more than
# 6 miles, but at least 3"), the bare "at least 3" still leaves the preposition
# "at" for the destination extractor (which geocodes it to the Appalachian
# Trail). Length itself is parsed from the full text elsewhere, so removing this
# span costs no length signal. Deliberately NOT added to length parsing.
_COUNT_FLOOR_RE = re.compile(
    r"\b(?:at least|no less than|no fewer than|min(?:imum)?(?:\s+of)?|"
    r"(?<!no )more than|over|longer than|greater than)\s*"
    r"(\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)

# Constraint spans stripped from the text BEFORE destination extraction so a
# length/time idiom can't donate a bogus place token. The classic failure:
# "…is at least 4 miles long" leaves the bare preposition "at" for the extractor,
# which geocodes it to the Appalachian Trail. Length is parsed separately from
# the FULL text (_extract_length_constraints), so removing these spans here is
# purely for the destination pass and loses no length signal. Order-independent —
# each regex is removed globally.
_CONSTRAINT_STRIP_RES = [
    _MILE_RANGE_RE, _MILE_FLOOR_RE, _MILE_FLOOR_PLUS_RE, _MILE_CEILING_RE,
    _MILE_APPROX_RE, _MILE_SINGLE_RE, _TIME_BUDGET_RE,
    # Last: unit-less floor, after the mile-specific spans have been removed, so
    # it only mops up a bare "at least 3" whose unit was carried by an earlier
    # clause. (?<!no )more than keeps the ceiling "no more than 6" out of it.
    _COUNT_FLOOR_RE,
]
# A trailing relative/feature clause ("raleigh, that has a waterfall") — the
# destination extractor's terminator set doesn't stop at ",that", so it swallows
# the whole clause and then fails to geocode. Cut it off for the destination pass.
# BUT the place can appear INSIDE/after the clause ("a hike with a waterfall near
# Asheville"), so the strip stops at the next destination preposition rather than
# running to end-of-line — otherwise it would eat "near Asheville" and lose the
# place entirely. With no following prep it still strips to the end.
_TRAILING_CLAUSE_RE = re.compile(
    r"[,;]?\s*\b(?:that|which|with|where|who)\b"
    r".*?(?=\s+\b(?:in|near|at|around|through|across)\b|$)",
    re.IGNORECASE,
)


def _strip_constraint_phrases(text: str) -> str:
    """Return `text` with length/time constraint spans, near-me pronouns, and
    trailing relative clauses removed, for DESTINATION extraction only.
    Feature/activity/difficulty extractors keep using the full text."""
    cleaned = text
    for rx in _CONSTRAINT_STRIP_RES:
        cleaned = rx.sub(" ", cleaned)
    # A near-me pronoun ("near me", "in my area") is never a place — drop it so
    # the destination extractor can't capture "brevard close to me" as one token
    # (and so a concrete place in the same message still resolves).
    cleaned = _NEAR_ME_RE.sub(" ", cleaned)
    cleaned = _TRAILING_CLAUSE_RE.sub(" ", cleaned)
    # collapse whitespace left by the substitutions
    return re.sub(r"\s+", " ", cleaned).strip()


# Stray prepositions / pronouns that must never reach the geocoder as a place.
# "at" → Appalachian Trail, "me"/"here" → the user's location (handled upstream),
# bare articles/prepositions → whatever Nominatim ranks first. If the extractor
# resolves to one of these, we raise DestinationNotFound instead of geocoding.
_INVALID_DESTINATION_TOKENS: frozenset[str] = frozenset({
    "at", "in", "near", "around", "the", "me", "here",
    "this", "there", "my location", "my area",
})

# A named wilderness/park whose real backpacking trails are often short stitched
# segments — for these the overnight length floor is skipped (a 20 km floor would
# hard-exclude the whole network). A plain city ("Asheville") is just a search
# ORIGIN, not a trail network, so it keeps the floor and stops day-strolls being
# served as backpacking legs.
#
# The ambiguous single words (bare "forest"/"mountain"/"range"/"national") are
# deliberately NOT matched on their own: they also form ordinary town names
# ("Black Mountain", "Forest City", "Mountain View") that would then wrongly skip
# the floor. Only unambiguous designations count — a multi-word "national/state
# forest|park", plural "mountains"/"mountain range", "gorge", "wilderness", etc.
_WILDERNESS_NAME_RE = re.compile(
    r"\b(?:wilderness|gorge|backcountry|preserve|"
    r"national\s+(?:forest|park|monument|seashore|recreation|wilderness)|"
    r"state\s+(?:forest|park)|"
    r"wildlife\s+(?:management|refuge)|game\s+land|"
    r"mountains|mountain\s+range)\b",
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

# Activities that imply a night out. If one of these is detected but no explicit
# day count was given, duration_days is only an assumption → duration_ambiguous.
OVERNIGHT_ACTIVITIES = frozenset({"backpacking", "extended", "overnight", "mountaineering"})


def _default_duration_days(activity, duration):
    """Resolve the trip's day count. An explicit count always wins; otherwise an
    overnight/backpacking activity implies at least 2 days (a single-day
    "backpacking" trip is a contradiction), and everything else defaults to 1.
    duration_ambiguous still flags the assumed value so the user can adjust it."""
    if duration:
        return duration
    return 2 if activity in OVERNIGHT_ACTIVITIES else 1

# When the user asks for an overnight/backpacking trip but names no explicit
# length, a trail's own km is the only distance signal we have — and without a
# floor the search just returns the nearest *short* day-hikes (a 4 km "half day"
# loop for a "backpacking" ask). Derive a duration-scaled minimum so day-length
# trails drop out. Deliberately conservative (10 km/day, not 15) so real regions
# still return candidates; find_hikes_with_fallback discloses honestly when a
# sparse area has nothing long enough rather than silently serving day hikes.
OVERNIGHT_MIN_KM_PER_DAY = 10.0


def _effective_min_length(min_length_km, max_length_km, target_length_km, activity, duration_days,
                          is_specific_place=False, duration_explicit=False):
    """Length floor for the search. An explicit "at least N mi" always wins; an
    overnight activity OR a multi-day count (>= 2 days) with NO stated length at
    all gets a duration-scaled floor; a plain single-day hike gets none.

    A numeric day count is enough on its own: "3 day hiking trip in Asheville"
    parses activity as `day_hike` (no "backpacking" keyword), but 3 days out is
    inherently overnight, so it must get the floor or the search just returns the
    nearest 3 km day-strolls tagged "Standard prep".

    Critically, if the user gave a ceiling or an approximate length ("around 8
    miles", "under 5 miles") we impose NO floor — their number is the intent, and
    a duration floor above their ceiling would make min > max and return zero
    hikes for a perfectly reasonable request.

    `is_specific_place`: when the user named a specific destination point (e.g.
    "Linville Gorge") rather than a broad region or "near me", the auto overnight
    floor is skipped. A named wilderness's real backpacking trails are often short
    segments stitched into loops (Conley Cove 3.6 km, Spence Ridge 4.6 km, …); a
    20 km floor would hard-exclude the entire network and fall back to long
    through-trails that only pass nearby. Proximity + tag ranking carries relevance
    for a specific place. The floor still applies to region/near-me searches, where
    it stops a vague "backpacking" ask from returning a 3 km greenway."""
    if min_length_km is not None:
        return min_length_km
    if max_length_km is not None or target_length_km is not None:
        return None
    # A multi-day count only counts when the user actually STATED it — a defaulted
    # duration (an overnight activity implies 2 days even with no explicit count)
    # must not silently impose a 20 km floor on a plain "hike in Asheville".
    multi_day = duration_explicit and (duration_days or 1) >= 2
    if (activity in OVERNIGHT_ACTIVITIES or multi_day) and not is_specific_place:
        return OVERNIGHT_MIN_KM_PER_DAY * max(1, int(duration_days or 1))
    return None

DURATION_PATTERNS = [
    (r"(\d+)\s*night",              lambda m: int(m.group(1)) + 1),
    (r"(\d+)\s*day",               lambda m: int(m.group(1))),
    (r"a\s+night",                 lambda m: 2),
    (r"a\s+couple\s+(?:of\s+)?days", lambda m: 2),
    (r"long\s+weekend",            lambda m: 3),
    (r"a\s+weekend",               lambda m: 3),
    (r"a\s+week",                  lambda m: 7),
    (r"a\s+few\s+days",            lambda m: 3),
    (r"several\s+days",            lambda m: 3),
    (r"multi[\s-]?day",            lambda m: 3),
]

# \b around the preposition group so a preposition hidden INSIDE another word
# can't match — without it the "at" in a typo like "wn[at]" (for "want") was
# captured as a preposition, turning "i wnat to go backpacking in linville gorge"
# into the place "to go backpacking in linville gorge".
DESTINATION_PREPS = r"\b(?:in|near|at|around|through|across)\b\s+(?:the\s+)?(.+?)(?:\s+for|\s+this|\s+and|\.|$)"

# Relocation cues — a mid-search "move the map" ("closer to Asheville", "how
# about Boone", "over near Brevard"). Broader than DESTINATION_PREPS because
# "closer to"/"how about" aren't destination prepositions, so the normal
# destination parse never catches them. Deliberately omits bare "in"/"at" (too
# noisy mid-sentence); the caller geocode-confirms the candidate and checks it's
# actually a different place, so a stray capture just no-ops.
_RELOCATION_PREPS = re.compile(
    r"(?:closer to|nearer(?:\s+to)?|over\s+(?:near|by)|how about(?:\s+near)?|"
    r"what about(?:\s+near)?|towards?|around|near)\s+(?:the\s+)?(.+?)"
    r"(?:\s+for\b|\s+this\b|\s+and\b|\s+instead\b|[.,?!]|$)",
    re.IGNORECASE,
)

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

# The full set of feature tags a message can mention (the keys above). Used to
# recover "which features did the user mention" from a TripIntent's required +
# preferred tags — those two also carry non-feature tags (activity-duration,
# difficulty-gain, camping), which this intersection filters back out.
_FEATURE_TAGS: frozenset[str] = frozenset(FEATURE_KEYWORD_MAP.keys())


def _infer_primary_priority(
    priority_tags:    list[str],
    required_tags:    list[str],
    preferred_tags:   list[str],
    target_length_km: Optional[float],
) -> Optional[str]:
    """
    Rule-based half of the hybrid "what should ranking key on?" decision.
    Returns a single primary dimension when the request is unambiguous, else
    None (the caller — TripChat — then makes one cheap Groq call to break a
    genuinely ambiguous tie). Deliberately Groq-free so the parser stays a pure
    unit-testable function.

    - An emphasized feature ("I really want a lake") is primary — reuses the
      existing emphasis→priority_tags detection.
    - A stated distance with NO feature mentioned → "distance" is primary.
    - Otherwise (a feature + a distance, or multiple features, none emphasized)
      → None: ambiguous, leave it for the hybrid Groq step.
    """
    if priority_tags:
        return priority_tags[0]
    mentioned_features = (set(required_tags) | set(preferred_tags)) & _FEATURE_TAGS
    if target_length_km is not None and not mentioned_features:
        return "distance"
    return None

# Common filler words that can precede a feature noun without changing
# whether the phrase names a place. "near a really nice lake" should still
# be recognized as a feature phrase, not a place, once these are stripped.
_LOCATION_CANDIDATE_FILLER_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "some", "any", "really", "very",
    "nice", "good", "great", "beautiful", "pretty",
    "small", "big", "little",
})


def _is_feature_only_phrase(candidate: str) -> bool:
    """True if `candidate` is made ENTIRELY of trail-feature/filler words
    ("a forest", "a lake", "waterfall") — a described feature, not a place. Used
    to stop the destination extractor from geocoding "in a forest" as a place.
    Mirrors the is_feature_phrase check in has_location_signal()."""
    words = [
        w for w in candidate.lower().split()
        if w not in _LOCATION_CANDIDATE_FILLER_WORDS
    ]
    return bool(words) and all(w in ALL_FEATURE_KEYWORDS for w in words)

# Conversational / grammatical words that are NOT place names. Used by
# has_possible_place_token() to decide whether a message that named no
# recognized location nonetheless contains a bare proper-noun place ("Linville
# Gorge") — anything left after removing these plus feature/filler words is
# treated as a candidate place. Deliberately broad on the safe side: a false
# positive here just costs one wasted parse/geocode cycle (the parser fails safe
# to None), while a false negative strands a real destination the user typed.
_PLACE_SCAN_STOPWORDS: frozenset[str] = frozenset({
    # difficulty / activity / trip-shape / length
    "easy", "moderate", "hard", "challenging", "difficult", "strenuous", "tough",
    "gentle", "short", "long", "longer", "shorter", "quick", "flat", "steep",
    "hike", "hiking", "hikes", "trail", "trails", "walk", "walking", "trek",
    "stroll", "strolls", "strolling", "wander", "wandering", "amble", "ambling",
    "ramble", "rambling", "roam", "roaming", "jaunt", "saunter",
    "backpacking", "backpack", "camping", "camp", "overnight", "trip", "trips",
    "adventure", "outing", "day", "days", "night", "nights", "week", "weekend",
    "mile", "miles", "mi", "km", "kilometer", "kilometers", "hour", "hours",
    # pronouns / auxiliaries
    "i", "me", "my", "mine", "we", "us", "our", "you", "your", "it", "its",
    "am", "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
    "doing", "have", "has", "had", "having", "will", "would", "could", "should",
    "can", "may", "might", "must", "shall",
    # common verbs
    "want", "wanna", "like", "love", "looking", "look", "go", "going", "get",
    "getting", "find", "take", "see", "plan", "planning", "think", "thinking",
    "hope", "hoping", "prefer", "need", "try", "trying", "explore",
    # articles / conjunctions / prepositions
    "and", "or", "but", "so", "then", "with", "without", "for", "to", "of",
    "in", "on", "at", "by", "from", "as", "that", "this", "these", "those",
    "near", "close", "closer", "around", "about", "over", "under", "up", "down",
    "out", "into", "than", "too", "if", "there",
    # politeness / discourse markers
    "sorry", "please", "thanks", "thank", "ok", "okay", "yeah", "yes", "no",
    "nope", "yep", "sure", "maybe", "actually", "just", "really", "kinda",
    "kind", "bit", "well", "lets", "let", "also", "still", "again", "hey",
    # generic nouns / quantifiers
    "something", "anything", "somewhere", "anywhere", "place", "spot", "options",
    "option", "one", "ones", "more", "less", "few", "couple", "some", "any",
    "nothing", "everything", "stuff", "things", "thing",
})

# Words that, alongside a state code/name, mean the user just named a STATE
# ("anywhere in NC is fine") rather than a specific place. Used to route such
# messages to a state-scoped search instead of geocoding the literal filler.
_STATE_ONLY_FILLER: frozenset[str] = frozenset({
    "anywhere", "somewhere", "everywhere", "around", "is", "are", "fine",
    "works", "work", "good", "great", "okay", "ok", "sure", "cool", "area",
    "region", "state", "place", "somewhere", "anyplace", "please", "thanks",
    "in", "of", "within", "throughout",
})

# Words that mean a message is a difficulty/length/generic REFINEMENT, not a
# place — so "how about something easier" / "closer to a shorter one" don't get
# mistaken for a relocation. None of these ever appear in a real place name.
_NON_PLACE_WORDS: frozenset[str] = frozenset({
    "easy", "easier", "moderate", "hard", "harder", "difficult", "difficulty",
    "challenging", "strenuous", "tough", "tougher", "gentle", "gentler", "mild",
    "shorter", "longer", "bigger", "smaller", "steeper", "flatter", "closer",
    "nearer", "farther", "further", "short", "long", "flat", "steep", "hilly",
    "something", "anything", "somewhere", "anywhere", "one", "another", "it",
    "that", "this", "those", "these", "trail", "trails", "hike", "hikes",
    "route", "routes", "option", "options", "different", "else",
})

# Pronoun words that mean "the user's own location" — a relocation candidate made
# up entirely of these is not a place to geocode ("me" → Maine); it's routed to
# the user's coordinates in _try_relocate instead.
_NEAR_ME_WORDS: frozenset[str] = frozenset({
    "me", "here", "myself", "my", "location", "area", "current",
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


def _is_state_only_candidate(candidate: str, state_abbr: str) -> bool:
    """
    True when the destination candidate is essentially just a state name/code
    plus filler ("nc is fine", "anywhere in north carolina") — i.e. the user
    named a STATE, not a specific place. Such messages should search the state,
    not geocode the literal filler string (which matched a Minnesota town).
    """
    state_full = _STATE_ABBR_TO_NAME.get(state_abbr.upper(), "")
    text = candidate.lower()
    if state_full:
        text = text.replace(state_full, " ")
    leftovers = [
        w for w in re.split(r"[^a-z]+", text)
        if w and w != state_abbr.lower()
        and w not in _STATE_ONLY_FILLER
        and w not in _LOCATION_CANDIDATE_FILLER_WORDS
    ]
    return not leftovers


# ── Exceptions ─────────────────────────────────────────────────────────────────


class DestinationNotFound(ValueError):
    """
    Raised by parse() when a place was named but could not be geocoded (a
    misspelling, or somewhere we simply can't resolve). Subclasses ValueError so
    every existing `except ValueError` keeps catching it, while callers that want
    to surface a specific "did you mean…?" reply can catch it by type.

    Carries the attempted display string so the caller can name it back to the
    user without re-deriving it.
    """

    def __init__(self, place: str):
        self.place = place
        super().__init__(f"Could not locate '{place}' — try being more specific.")


class LocationRequired(ValueError):
    """
    Raised by parse() when the user asked for something "near me" but no
    coordinates were shared (GPS denied and no saved home_location). Subclasses
    ValueError so existing `except ValueError` handlers still catch it, while the
    caller can catch it by type to surface a "share your location or name a
    place" reply instead of blindly geocoding the pronoun ("me" → Maine).
    """


class NoDestinationProvided(ValueError):
    """
    Raised by parse() when the message names NO place at all — the destination
    extractor found only trail features / activity words ("a stroll in a
    forest"), or the LLM fallback returned an empty/null destination. Distinct
    from DestinationNotFound (a place WAS named but wouldn't geocode): the caller
    should ask "where would you like to hike?" rather than "I couldn't find a
    place called X" for a place the user never typed.
    """


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
    min_length_km:    Optional[float] = None  # ← NEW: length FLOOR ("at least N mi")
    max_length_km:    Optional[float] = None
    target_length_km: Optional[float] = None
    # Which single dimension ranking should key on: "distance", a feature tag
    # ("lake"), or None (balanced composite). Set by the rule-based
    # _infer_primary_priority here; None means "ambiguous" and TripChat resolves
    # it with one cheap Groq call before searching. See HikeSearchService sort.
    primary_priority: Optional[str] = None
    # True when the request implies an overnight (backpacking/extended/etc.) but
    # gave no explicit day count, so duration_days below is only an assumption.
    # The destination phase uses this to confirm trip length rather than guess.
    duration_ambiguous: bool = False
    # True when THIS message stated a day count explicitly (e.g. "3 day trip"),
    # vs duration_days being a default. Lets _apply_intent_to_plan avoid
    # clobbering a previously-known duration when a later turn (a place
    # disambiguation like "Asheville NC") carries no day count of its own.
    duration_explicit: bool = False


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
    min_length_km:    Optional[float] = None   # ← NEW: length FLOOR ("at least N mi")
    max_length_km:    Optional[float] = None   # ← NEW
    target_length_km: Optional[float] = None
    primary_priority: Optional[str] = None     # see TripIntent.primary_priority


# ── Parser ─────────────────────────────────────────────────────────────────────
# "Search where I physically am" phrasings. A closed allow-list (rather than a
# heuristic) so it never fires on a real place — the \b anchors keep "near
# Me[ndocino]" out. Deliberately broad on the phrasing side because everything
# it MISSES drains into the destination extractor, which then geocodes the bare
# pronoun "me" → the state of Maine. Kept as a module-level list + is_near_me()
# helper so both the initial parse and the mid-chat relocation path share one
# definition.
NEAR_ME_PATTERNS = [
    r"\bnear\s+me\b",
    r"\bnearby\b",
    r"\bby\s+me\b",
    r"\bnext\s+to\s+me\b",
    r"\bclose\s+to\s+me\b",
    r"\bclose\s+by\b",
    r"\bclosest\s+to\s+me\b",
    r"\baround\s+me\b",
    r"\blocal\s+hike\b",
    r"\bnear\s+(?:my\s+location|here|where\s+i\s+am)\b",
    r"\baround\s+here\b",
    r"\bin\s+my\s+area\b",
    r"\bmy\s+(?:current\s+)?location\b",
    r"\bwhere\s+i\s+am\b",
    r"\bcurrent\s+location\b",
]
_NEAR_ME_RE = re.compile("|".join(NEAR_ME_PATTERNS), re.IGNORECASE)


def is_near_me(text: Optional[str]) -> bool:
    """True when the message asks to search the user's own location. Shared by
    parse() (initial) and _try_relocate() (mid-chat 'move it near me')."""
    return bool(text) and _NEAR_ME_RE.search(text) is not None


class TripInputParser:
    def __init__(self):
        self._groq = Groq(api_key=os.environ["HikeKey"])
        _AI_DIR   = os.path.dirname(os.path.abspath(__file__))
        _BASE_DIR = os.path.dirname(_AI_DIR)
        lookup_path = os.path.join(_BASE_DIR, 'Services', 'parks_lookup.json')
        with open(lookup_path, 'r') as f:
            self.national_parks = json.load(f)
        self.park_keys = sorted(self.national_parks.keys(), key=len, reverse=True)
        # Keys used for the BARE-WORD regex scan drop 2-letter abbreviations
        # ("at" → Appalachian Trail, "ct" → Colorado Trail). A standalone "at"
        # in "…but at least 3" would otherwise match and geocode to the AT. The
        # full abbreviations ("appalachian trail") and 3+ letter codes still
        # resolve; only the ambiguous 2-letter word-collision path is removed.
        self.park_scan_keys = [k for k in self.park_keys if len(k) > 2]
    
    def parse(
        self,
        user_input: str,
        user_lat:   Optional[float] = None,
        user_lng:   Optional[float] = None,
    ) -> TripIntent:
        text = user_input.lower().strip()
        min_length_km, max_length_km, target_length_km = self._extract_length_constraints(text)   # ← renamed

        if is_near_me(text):
            # A message can say "near me" yet still name a concrete place
            # ("a waterfall hike near Brevard, close to me"). Prefer the named
            # place: only take the user's-own-location fast path when NO real
            # destination survives once the near-me phrase + constraint idioms
            # are stripped (_strip_constraint_phrases drops the near-me pronoun).
            probe = self._extract_destination_regex(
                _strip_constraint_phrases(text), raw_text=user_input
            )
            named_place = (
                bool(probe) and probe.strip().lower() not in _INVALID_DESTINATION_TOKENS
            )
            if not named_place:
                if user_lat is None or user_lng is None:
                    raise LocationRequired(
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
                    duration_days    = _default_duration_days(activity, duration),
                    difficulty_hint  = difficulty,
                    raw_goal         = user_input,
                    required_tags    = required,
                    preferred_tags   = preferred,
                    priority_tags    = priority,
                    avoid_permits    = avoid_permits,
                    duration_ambiguous = duration is None and activity in OVERNIGHT_ACTIVITIES,
                    duration_explicit = duration is not None,
                    destination_type = "point",
                    region_tag       = region_tag,
                    state            = state,
                    # near-me keeps the overnight floor: a "backpacking near me" ask
                    # should still mean real trails, not a 3 km loop by the user's house.
                    min_length_km    = _effective_min_length(min_length_km, max_length_km, target_length_km, activity or "day_hike", _default_duration_days(activity, duration), is_specific_place=False, duration_explicit=duration is not None),
                    max_length_km    = max_length_km,
                    target_length_km = target_length_km,   # ← NEW
                    primary_priority = _infer_primary_priority(priority, required, preferred, target_length_km),
                )
            # else: a concrete place was named alongside the near-me phrase —
            # fall through to normal extraction, which resolves that place.

        # Strip length/time idioms + trailing clauses so the destination pass
        # can't mistake "at least 4 miles" for a place ("at") — length itself is
        # already parsed above from the full text. Tag/activity/difficulty
        # extraction below still uses the full `text` (it needs the feature words).
        dest_text = _strip_constraint_phrases(text)
        destination_raw = self._extract_destination_regex(dest_text, raw_text=user_input)
        activity        = self._extract_activity(text)
        duration        = self._extract_duration(text)
        difficulty      = self._extract_difficulty(text)
        required, preferred, avoid_permits, priority = self._extract_tags(text, activity, difficulty)
        dest_type, region_tag, regex_state = self._extract_destination_type(text, raw_text=user_input)
        state = regex_state   # ← Bug 1 fix: seed state so the LLM-fallback path below always has a value

        if destination_raw:
            # Belt-and-suspenders: never geocode a bare preposition/pronoun that
            # slipped through ("at", "the", "me"). Checked on the RAW token BEFORE
            # the park-abbreviation lookup, since that lookup expands "at" →
            # "Appalachian Trail" and would otherwise mask the junk token. A bare
            # preposition is "no place named" (ask where to?), not a mistyped
            # place, so raise NoDestinationProvided rather than DestinationNotFound.
            if destination_raw.strip().lower() in _INVALID_DESTINATION_TOKENS:
                raise NoDestinationProvided(destination_raw)
            # "Anywhere in NC is fine" captures the filler "nc is fine" — search
            # the STATE, not that literal string (which geocoded to Minnesota).
            if regex_state and _is_state_only_candidate(destination_raw, regex_state):
                destination_full = _STATE_ABBR_TO_NAME[regex_state].title()
                dest_type        = "region"
            else:
                destination_full = self.national_parks.get(destination_raw, destination_raw.title())
            coords = self._geocode(destination_full, state=regex_state)
            if coords:
                # An explicitly-typed state wins over a low-confidence geocode
                # match's state, so a stray worldwide hit can't relabel NC as MN.
                state = regex_state or coords.get("state")
                return TripIntent(
                    destination_raw  = destination_raw,
                    destination_full = destination_full,
                    lat              = coords["lat"],
                    lng              = coords["lng"],
                    activity_type    = activity or "day_hike",
                    duration_days    = _default_duration_days(activity, duration),
                    difficulty_hint  = difficulty,
                    raw_goal         = user_input,
                    required_tags    = required,
                    preferred_tags   = preferred,
                    priority_tags    = priority,
                    avoid_permits    = avoid_permits,
                    duration_ambiguous = duration is None and activity in OVERNIGHT_ACTIVITIES,
                    duration_explicit = duration is not None,
                    destination_type = dest_type,
                    region_tag       = region_tag,
                    state            = state,
                    # A named WILDERNESS/park ("Linville Gorge") skips the auto
                    # overnight floor — its real backpacking trails are short
                    # stitched segments, so trust proximity/tag ranking. A plain
                    # city ("Asheville") is just a search origin, not a trail
                    # network, so it KEEPS the floor (else 2 km day-strolls get
                    # served as backpacking legs). A region ("NC") keeps it too.
                    min_length_km    = _effective_min_length(min_length_km, max_length_km, target_length_km, activity or "day_hike", _default_duration_days(activity, duration), is_specific_place=(dest_type == "point" and self._is_named_wilderness(destination_full, destination_raw)), duration_explicit=duration is not None),
                    max_length_km    = max_length_km,
                    target_length_km = target_length_km,   # ← NEW
                    primary_priority = _infer_primary_priority(priority, required, preferred, target_length_km),
                )
            # The regex confidently captured a place, but it wouldn't geocode.
            # Re-running the LLM extractor on the same words would burn a Groq
            # call only to extract the identical (still-unresolvable) string —
            # so fail fast here and let the caller surface a "did you mean…?"
            # reply. The _llm_extract fallback below is reserved for messages
            # where the regex found NO destination candidate at all.
            raise DestinationNotFound(destination_full)

        extracted = self._llm_extract(dest_text)
        dest = extracted.get("destination") or ""
        # No place named at all — the LLM returned null/empty (per its prompt),
        # or only a trail feature ("a forest"). Signal NoDestinationProvided so
        # the caller asks "where would you like to hike?" instead of naming a
        # phantom place ("that location") the user never typed.
        if not dest or _is_feature_only_phrase(dest):
            raise NoDestinationProvided(dest or "no place named")
        # Same guard as the regex path, on the RAW token before the park-lookup
        # expansion: a bare preposition/pronoun the LLM latched onto ("at" from
        # "at least 4 miles", which the lookup would expand to "Appalachian
        # Trail") must never be geocoded.
        if dest.strip().lower() in _INVALID_DESTINATION_TOKENS:
            raise NoDestinationProvided(dest)
        destination_full = self.national_parks.get(dest.lower(), dest)
        coords = self._geocode(destination_full, state=regex_state)
        if not coords:
            raise DestinationNotFound(destination_full)
        # Explicit state wins; else adopt the (now US-scoped) geocoded state.
        state = regex_state or coords.get("state")

        llm_features = extracted.get("features", [])
        preferred = sorted(set(preferred) | {f for f in llm_features if f in FEATURE_KEYWORD_MAP})

        return TripIntent(
            destination_raw  = extracted.get("destination", destination_full),
            destination_full = destination_full,
            lat              = coords["lat"],
            lng              = coords["lng"],
            activity_type    = extracted.get("activity_type") or activity or "day_hike",
            duration_days    = _default_duration_days(extracted.get("activity_type") or activity, extracted.get("duration_days") or duration),
            difficulty_hint  = extracted.get("difficulty") or difficulty,
            raw_goal         = user_input,
            required_tags    = required,
            preferred_tags   = preferred,
            priority_tags    = priority,
            avoid_permits    = avoid_permits,
            duration_ambiguous = (
                (extracted.get("duration_days") or duration) is None
                and (extracted.get("activity_type") or activity) in OVERNIGHT_ACTIVITIES
            ),
            duration_explicit = (extracted.get("duration_days") or duration) is not None,
            destination_type = dest_type,
            region_tag       = region_tag,
            state            = state,
            # Same rule as the regex path: only a named wilderness/park skips the
            # auto overnight floor; a plain city or region keeps it.
            min_length_km    = _effective_min_length(min_length_km, max_length_km, target_length_km, extracted.get("activity_type") or activity or "day_hike", _default_duration_days(extracted.get("activity_type") or activity, extracted.get("duration_days") or duration), is_specific_place=(dest_type == "point" and self._is_named_wilderness(destination_full, dest)), duration_explicit=(extracted.get("duration_days") or duration) is not None),
            max_length_km    = max_length_km,
            target_length_km = target_length_km,   # ← NEW
            # preferred here already folds in llm_features, so a feature the LLM
            # surfaced (not just the regex) also counts against "sole distance".
            primary_priority = _infer_primary_priority(priority, required, preferred, target_length_km),
    )

    def _is_named_wilderness(self, destination_full: str, raw_key: Optional[str]) -> bool:
        """True when the destination is a recognized park/wilderness (a park-lookup
        key, or a name containing wilderness/gorge/forest/… ) as opposed to a plain
        city. Only these skip the overnight length floor — see _effective_min_length."""
        if raw_key and raw_key.lower() in self.national_parks:
            return True
        return bool(_WILDERNESS_NAME_RE.search(destination_full or ""))

    def parse_refinement(self, user_input: str) -> RefinementIntent:
        text       = user_input.lower().strip()
        activity   = self._extract_activity(text)
        duration   = self._extract_duration(text)
        difficulty = self._extract_difficulty(text)
        required, preferred, avoid_permits, priority = self._extract_tags(text, activity, difficulty)
        min_length_km, max_length_km, target_length_km = self._extract_length_constraints(text)   # ← NEW
        return RefinementIntent(
            activity_type    = activity,
            duration_days    = duration,
            difficulty_hint  = difficulty,
            required_tags    = required,
            preferred_tags   = preferred,
            priority_tags    = priority,
            avoid_permits    = avoid_permits,
            min_length_km    = min_length_km,       # ← NEW
            max_length_km    = max_length_km,       # ← NEW
            target_length_km = target_length_km,    # ← NEW
            primary_priority = _infer_primary_priority(priority, required, preferred, target_length_km),
        )
    def _extract_length_constraints(
        self, text: str
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Returns (min_length_km, max_length_km, target_length_km).

        min_length_km is a hard FLOOR forwarded to HikeService.search_hikes()
        -> HikeRepository.search() as `length_km >= ...`. Set for "at least N
        miles", "minimum N", "over N", "longer than N", and the "N+ miles" form.

        max_length_km is the hard ceiling forwarded as `length_km <= ...`.

        A range ("3 to 5 miles") sets BOTH bounds.

        target_length_km is set ONLY for approximate phrasing ("around 3 miles")
        and is never passed to the DB — HikeSearchService's length-proximity
        scoring term uses it so a 3.4mi trail actually outranks a 1.8mi trail
        when the user asked for "around 3 miles," instead of length dropping out
        of ranking entirely once a trail clears the ceiling.

        An approximate mention still loosens the ceiling to target*1.2 so a
        trail slightly over the ballpark number isn't hard-excluded before
        scoring gets a chance to weigh in.
        """
        # Drop any length the user is explicitly rejecting ("8 miles is too
        # long, look at 4 mile hikes instead") so the extractors below don't
        # latch onto the discarded number. See _REJECTED_LENGTH_RES.
        for rx in _REJECTED_LENGTH_RES:
            text = rx.sub(" ", text)

        m = _MILE_RANGE_RE.search(text)
        if m:
            lo, hi = sorted((float(m.group(1)), float(m.group(2))))
            return round(lo * KM_PER_MILE, 1), round(hi * KM_PER_MILE, 1), None

        # FLOOR before the bare-number ceiling — "at least 3 miles" must not be
        # read as "at most 3 miles" (see _MILE_FLOOR_RE comment).
        m = _MILE_FLOOR_RE.search(text) or _MILE_FLOOR_PLUS_RE.search(text)
        if m:
            return round(float(m.group(1)) * KM_PER_MILE, 1), None, None

        m = _MILE_CEILING_RE.search(text)
        if m:
            return None, round(float(m.group(1)) * KM_PER_MILE, 1), None

        m = _MILE_APPROX_RE.search(text)
        if m:
            target_km = round(float(m.group(1)) * KM_PER_MILE, 1)
            return None, round(target_km * 1.2, 1), target_km

        # Bare "8 mile[s]": treat as a TARGET with a hard band (floor+ceiling), not
        # a ceiling-only. Sets target_length_km so length-proximity ranking turns
        # on, and a floor so far-too-short trails are filtered out entirely.
        m = _MILE_SINGLE_RE.search(text)
        if m:
            target_km = round(float(m.group(1)) * KM_PER_MILE, 1)
            return (
                round(target_km * SINGLE_MILE_FLOOR_FACTOR, 1),   # min floor
                round(target_km * SINGLE_MILE_CEIL_FACTOR, 1),    # max ceiling
                target_km,                                        # target (rank signal)
            )

        return None, self._extract_time_budget_km(text), None
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
        for key in self.park_scan_keys:
            if re.search(r'\b' + re.escape(key) + r'\b', text):
                return key
        match = re.search(DESTINATION_PREPS, text)
        if match:
            candidate = match.group(1).strip().rstrip(".,")
            # "in a forest" / "near a lake" describe a trail FEATURE, not a
            # place — don't hand a feature-only phrase to the geocoder.
            if _is_feature_only_phrase(candidate):
                return None
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

        if is_near_me(t):
            return True

        if any(re.search(r'\b' + re.escape(key) + r'\b', t) for key in self.park_scan_keys):
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

    def has_possible_place_token(self, message: str) -> bool:
        """
        True if the message contains a word that could be a place name — a token
        that is not a known feature/filler/conversational word.

        Complements has_location_signal(): that only recognizes places via a
        preposition phrase or a lookup hit, so a bare proper-noun reply
        ("Linville Gorge", typed when we asked "where to?") registers as NO
        location signal — and because "gorge" is itself the `canyon` feature
        keyword, trip_chat's no-destination short-circuit would then strand it in
        the tag-accumulate branch and never geocode. Consulting this lets such a
        message fall through to a real parse/geocode attempt.

        Errs toward True on purpose: a false positive costs one wasted
        parse/geocode cycle (parse() fails safe to None), while a false negative
        loses a destination the user actually named.
        """
        for w in re.findall(r"[a-z']+", (message or "").lower()):
            if (
                w in _LOCATION_CANDIDATE_FILLER_WORDS
                or w in ALL_FEATURE_KEYWORDS
                or w in _PLACE_SCAN_STOPWORDS
            ):
                continue
            return True
        return False

    def extract_relocation_place(self, text: str) -> Optional[str]:
        """
        A place named as a MID-SEARCH MOVE — "closer to Asheville", "how about
        Boone", "over near Brevard". Returns the candidate place string, or None
        when there's no relocation cue or the candidate is only trail-feature
        words ("closer to a lake") or a length ("around 5 miles").

        The refine handler geocode-confirms this (US-scoped) and only relocates
        when it resolves to coordinates meaningfully different from the current
        destination — so a loose capture here safely no-ops.
        """
        if not text or not text.strip():
            return None
        m = _RELOCATION_PREPS.search(text.strip())
        if not m:
            return None
        candidate = m.group(1).strip().rstrip(".,?! ")
        if not candidate or any(ch.isdigit() for ch in candidate):
            return None   # "around 5 miles" is a length refinement, not a place
        words = [w for w in candidate.lower().split()
                 if w not in _LOCATION_CANDIDATE_FILLER_WORDS]
        if not words:
            return None
        if all(w in ALL_FEATURE_KEYWORDS for w in words):
            return None   # "a lake" / "a waterfall" — a feature, not a place
        if any(w in _NON_PLACE_WORDS for w in words):
            return None   # "something easier", "a shorter one" — a refinement, not a place
        if all(w in _NEAR_ME_WORDS for w in words):
            return None   # "near me" / "here" / "my location" — the user's OWN
                          # location (handled positively in _try_relocate); never
                          # geocode the pronoun ("me" → the state of Maine).
        return candidate

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
        # Comparative forms ("easier", "simpler", "tougher") are common in a
        # refine turn ("can we do something easier?"). "harder" already matches
        # via the "hard" substring below; "easier"/"simpler"/"tough(er)" need to
        # be listed explicitly since they don't contain their base keyword.
        if any(w in text for w in ["easy", "easier", "simpler", "beginner", "casual", "leisure"]):
            return "easy"
        if any(w in text for w in ["moderate", "medium", "intermediate"]):
            return "moderate"
        if any(w in text for w in ["hard", "difficult", "challenge", "challenging", "push myself", "strenuous", "tough"]):
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
                        '{"destination": "string or null", '
                        '"activity_type": "day_hike|overnight|backpacking|extended|mountaineering", '
                        '"duration_days": int, '
                        '"difficulty": "easy|moderate|hard|null", '
                        f'"features": [/* zero or more of: {", ".join(valid_features)} */]'
                        "}\n"
                        "destination MUST be null if the user names no place, "
                        "park, town, or state. Never invent one, and never treat "
                        "a trail feature (forest, lake, waterfall) as a place."
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

    def _geocode(self, place: str, state: Optional[str] = None) -> Optional[dict]:
        # Scope to the US so a bare/odd query can't match a same-named town
        # abroad, and bias to the named state when known ("Anywhere in NC" must
        # not resolve to a locality in Minnesota). Nominatim ignores structured
        # params alongside `q`, so we fold the state into the freeform query.
        q = place
        if state:
            state_full = _STATE_ABBR_TO_NAME.get(state.upper())
            if state_full and state_full.lower() not in place.lower():
                q = f"{place}, {state_full.title()}"
        try:
            r = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1,
                        "addressdetails": 1, "countrycodes": "us"},
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