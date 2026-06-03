# AI/TripInputParser.py
import re
import httpx
from dataclasses import dataclass, field
from typing import Optional
from groq import Groq
import json
import os

# ── Activity keywords ──────────────────────────────────────────────────────────

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

DESTINATION_PREPS = r"(?:in|near|at|to|around|through|across)\s+(?:the\s+)?(.+?)(?:\s+for|\s+this|\s+and|\.|$)"

# ── Tag derivation maps ────────────────────────────────────────────────────────

# activity_type → duration tags the trail should have (OR match — any one qualifies)
ACTIVITY_DURATION_TAGS: dict[str, list[str]] = {
    "day_hike":       ["short", "half_day", "full_day"],
    "overnight":      ["overnight"],
    "backpacking":    ["overnight", "multi_day"],
    "extended":       ["multi_day"],
    "mountaineering": ["full_day", "overnight", "multi_day"],
}

# difficulty_hint → gain tier tags (preferred, not hard-required)
DIFFICULTY_GAIN_TAGS: dict[str, list[str]] = {
    "easy":     ["flat", "gentle_gain"],
    "moderate": ["moderate_gain", "gentle_gain"],
    "hard":     ["high_gain", "very_high_gain"],
}

# Natural language keywords → feature tags (Overpass-enriched or derived)
# Any match → that tag goes into preferred_tags.
FEATURE_KEYWORD_MAP: dict[str, list[str]] = {
    "waterfall":    ["waterfall", "falls", "cascade"],
    "lake":         ["lake", "pond", "tarn", "swimming hole", "swim"],
    "summit":       ["summit", "peak", "mountaintop", "highest point", "top of"],
    "canyon":       ["canyon", "gorge", "slot canyon", "ravine"],
    "ridge":        ["ridge", "ridgeline", "exposed ridge"],
    "glacier":      ["glacier", "glacial", "icefield"],
    "meadow":       ["meadow", "wildflower", "wildflowers", "open field"],
    "forest":       ["forest", "woods", "wooded", "tree cover"],
    "beach":        ["beach", "coastal", "shoreline", "ocean"],
    "cave":         ["cave", "cavern", "grotto"],
    "viewpoint":    ["view", "views", "overlook", "vista", "scenic", "scenery"],
    "hot_spring":   ["hot spring", "hot springs", "thermal"],
    "river":        ["river", "creek", "stream", "waterway"],
    "historic":     ["historic", "ruins", "petroglyphs", "old growth"],
    "desert":       ["desert", "arid", "cactus", "red rock"],
    # Altitude tier preferences
    "alpine":       ["alpine", "above treeline", "above tree line", "high alpine", "exposed"],
    "subalpine":    ["subalpine"],
    "lowland":      ["lowland", "flat ground", "gentle terrain"],
}

# Activities that imply camping is a hard requirement (not just a preference)
CAMPING_ACTIVITIES = {"overnight", "backpacking", "extended"}

# Keywords that explicitly require camping (regardless of activity type)
CAMPING_KEYWORDS = ["camping", " camp ", "campsite", "base camp", "bivouac", "sleep out", "spend the night"]

# Keywords that signal the user wants to avoid permits
NO_PERMIT_KEYWORDS = ["no permit", "without permit", "permit-free", "don't need a permit", "no reservation"]


# ── TripIntent dataclass ───────────────────────────────────────────────────────

@dataclass
class TripIntent:
    destination_raw:  str
    destination_full: str
    lat:              float
    lng:              float
    activity_type:    str           # day_hike | overnight | backpacking | extended | mountaineering
    duration_days:    int
    difficulty_hint:  Optional[str] # easy | moderate | hard | None
    raw_goal:         str
    # ── Tag hints for HikeSearchService ───────────────────────────────────────
    # required_tags: WHERE hikes.tags @> required_tags  (must have ALL of these)
    # preferred_tags: boost score for each match        (nice to have)
    required_tags:  list[str] = field(default_factory=list)
    preferred_tags: list[str] = field(default_factory=list)
    avoid_permits:  bool = False


# ── Parser ─────────────────────────────────────────────────────────────────────

class TripInputParser:
    def __init__(self):
        self._groq = Groq(api_key=os.environ["GROQ_API_KEY"])
        lookup_path = os.path.join(os.path.dirname(__file__), 'parks_look.json')
        with open(lookup_path, 'r') as f:
            self.national_parks = json.load(f)
        self.park_keys = sorted(self.national_parks.keys(), key=len, reverse=True)

    def parse(self, user_input: str) -> TripIntent:
        text = user_input.lower().strip()

        destination_raw = self._extract_destination_regex(text)
        activity        = self._extract_activity(text)
        duration        = self._extract_duration(text)
        difficulty      = self._extract_difficulty(text)
        required, preferred, avoid_permits = self._extract_tags(text, activity, difficulty)

        # Fast path: regex got a destination
        if destination_raw:
            destination_full = self.national_parks.get(destination_raw, destination_raw.title())
            coords = self._geocode(destination_full)
            if coords:
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
                    avoid_permits    = avoid_permits,
                )

        # Slow path: LLM extraction
        extracted = self._llm_extract(user_input)
        destination_full = self.national_parks.get(
            extracted.get("destination", "").lower(),
            extracted.get("destination", "")
        )
        coords = self._geocode(destination_full)
        if not coords:
            raise ValueError(f"Could not locate '{destination_full}' — try being more specific.")

        # Merge LLM feature suggestions into preferred_tags
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
            avoid_permits    = avoid_permits,
        )

    # ── Tag extraction ─────────────────────────────────────────────────────────

    def _extract_tags(
        self,
        text:       str,
        activity:   Optional[str],
        difficulty: Optional[str],
    ) -> tuple[list[str], list[str], bool]:
        """
        Returns (required_tags, preferred_tags, avoid_permits).

        required_tags  — hard constraints; HikeSearchService uses WHERE tags @> these.
        preferred_tags — scoring hints; each match boosts rank.
        avoid_permits  — caller should exclude hikes with permits_required tag.
        """
        required:  set[str] = set()
        preferred: set[str] = set()

        # ── Camping ────────────────────────────────────────────────────────────
        # Multi-day activities inherently require camping. Explicit keywords too.
        needs_camping = (
            activity in CAMPING_ACTIVITIES
            or any(kw in text for kw in CAMPING_KEYWORDS)
        )
        if needs_camping:
            required.add("can_camp")

        # ── Duration tags (preferred — OR match in HikeSearchService) ─────────
        # Put in preferred so HikeSearchService can score vs. hard-exclude.
        # A "day hike" request shouldn't surface a 3-day trail, but a small
        # trail slightly over the threshold is better than no results.
        duration_tags = ACTIVITY_DURATION_TAGS.get(activity or "day_hike", ["full_day"])
        preferred.update(duration_tags)

        # ── Difficulty → gain tier (preferred) ────────────────────────────────
        if difficulty:
            preferred.update(DIFFICULTY_GAIN_TAGS.get(difficulty, []))

        # ── Feature keywords ───────────────────────────────────────────────────
        for tag, keywords in FEATURE_KEYWORD_MAP.items():
            if any(kw in text for kw in keywords):
                preferred.add(tag)

        # ── Permit avoidance ───────────────────────────────────────────────────
        avoid_permits = any(kw in text for kw in NO_PERMIT_KEYWORDS)

        # ── Mountaineering implies alpine terrain ──────────────────────────────
        if activity == "mountaineering":
            preferred.update(["alpine", "subalpine", "summit"])

        # Required tags are strict — don't let them bleed into preferred
        preferred -= required

        return sorted(required), sorted(preferred), avoid_permits

    # ── Regex helpers ──────────────────────────────────────────────────────────

    def _extract_destination_regex(self, text: str) -> Optional[str]:
        for key in self.park_keys:
            if re.search(r'\b' + re.escape(key) + r'\b', text):
                return key
        match = re.search(DESTINATION_PREPS, text)
        if match:
            candidate = match.group(1).strip().rstrip(".,")
            if len(candidate) > 2:
                return candidate
        return None

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
        if any(w in text for w in ["easy", "beginner", "casual", "leisure"]):
            return "easy"
        if any(w in text for w in ["moderate", "medium", "intermediate"]):
            return "moderate"
        if any(w in text for w in ["hard", "difficult", "challenge", "push myself", "strenuous"]):
            return "hard"
        return None

    # ── LLM fallback ──────────────────────────────────────────────────────────

    def _llm_extract(self, text: str) -> dict:
        """
        Used when regex can't identify a destination. Also pulls feature hints
        that keyword scanning might miss (e.g. 'somewhere dramatic and remote').
        """
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
                params={"q": place, "format": "json", "limit": 1},
                headers={"User-Agent": "HikeBuilder/1.0"},
                timeout=5.0,
            )
            results = r.json()
            if results:
                return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
        except Exception:
            pass
        return None