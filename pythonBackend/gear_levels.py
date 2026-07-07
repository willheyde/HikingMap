"""
gear_levels.py

The single source of truth for the gear "capability level" vocabulary — the
ordered scales that let the app check *adequacy* ("do you have boots good enough
for THIS trail?"), not just *presence* ("do you own shoes?").

Shared by three consumers so they can never drift apart:
  - GearInferenceEngine.infer_gear_levels() — per-hike REQUIRED level per category
  - GearGapAnalyzer                          — compares user level vs required
  - the user gear model / onboarding         — captures the user's level

Design notes
------------
* Only a handful of categories are "level-bearing" — the ones where a stronger
  item is meaningfully different (footwear, traction, insulation, shell,
  shelter). The rest are presence-only (nav, light, first aid, water): you
  either have it or you don't.
* Sleep is special-cased on a numeric temperature rating rather than an ordinal
  level — a bag "meets" a trail when its comfort rating is at or below the
  expected overnight low.
* Levels are ordinals: index in the list = strength. meets() is just an index
  comparison, so adding a new tier only means inserting it in the right place.
"""

# ── Ordered capability scales (index = strength, low → high) ──────────────────

FOOTWEAR   = ["sandal", "trail_runner", "hiking_boot", "mountaineering_boot"]
TRACTION   = ["none", "microspikes", "crampons"]
INSULATION = ["none", "fleece", "puffy", "expedition"]
SHELL      = ["none", "water_resistant", "hardshell"]
SHELTER    = ["none", "3_season", "4_season"]
NAVIGATION = ["map", "gps", "satellite"]

# category name → its scale. Categories absent here are presence-only.
LEVEL_SCALES: dict[str, list[str]] = {
    "footwear":   FOOTWEAR,
    "traction":   TRACTION,
    "insulation": INSULATION,
    "shell":      SHELL,
    "shelter":    SHELTER,
    "navigation": NAVIGATION,
}

# Presence-only categories — no level, only "have it or not".
PRESENCE_CATEGORIES = frozenset({"illumination", "first_aid", "hydration"})

# Handled by numeric temperature, not an ordinal level.
SLEEP_CATEGORY = "sleep"

IMPORTANCE_REQUIRED    = "required"
IMPORTANCE_RECOMMENDED = "recommended"


def level_index(category: str, level: str | None) -> int:
    """
    Ordinal rank of `level` within `category`'s scale, or -1 if the category
    isn't level-bearing or the level is unknown. Unknown levels rank lowest so
    an unrecognized value never falsely satisfies a requirement.
    """
    scale = LEVEL_SCALES.get(category)
    if not scale or level is None:
        return -1
    try:
        return scale.index(level)
    except ValueError:
        return -1


def meets(category: str, have_level: str | None, need_level: str | None) -> bool:
    """
    True when the user's `have_level` is at least `need_level` on the category's
    scale. A required level the user can't be ranked against (unknown) fails
    closed — better a false "check this" than a false "you're set".
    """
    if need_level is None:
        return True
    return level_index(category, have_level) >= level_index(category, need_level)


def sleep_meets(have_temp_f, need_temp_f) -> bool:
    """
    A sleeping bag meets a trail's need when its comfort rating is at or below
    the expected overnight low (lower °F rating = warmer bag). Unknown user
    rating fails closed.
    """
    if need_temp_f is None:
        return True
    if have_temp_f is None:
        return False
    return float(have_temp_f) <= float(need_temp_f)


# ── Functional gear categories (user-facing) ↔ items.item_type ────────────────
#
# User gear stores a functional `gear_category` in items.attributes (the A+
# model), but the items table still needs an item_type for backward compat with
# the catalog/query code. This maps one to the other for the write path.

GEAR_CATEGORY_TO_ITEM_TYPE: dict[str, str] = {
    "footwear":     "footwear",
    "traction":     "technical",     # crampons/microspikes live under technical
    "insulation":   "clothing",
    "shell":        "clothing",
    "navigation":   "navigation",
    "illumination": "lighting",
    "first_aid":    "safety",
    "hydration":    "water",
    "shelter":      "shelter",
    "sleep":        "sleeping_bag",
    "misc":         "misc",
}

# All valid functional categories a user item can declare.
GEAR_CATEGORIES = frozenset(GEAR_CATEGORY_TO_ITEM_TYPE)

# Reverse-ish: item_type → functional category, for legacy items with no
# explicit gear_category. Clothing is ambiguous (insulation vs shell) and is
# resolved separately in resolve_gear_category() using the waterproof flag.
_ITEM_TYPE_TO_CATEGORY: dict[str, str] = {
    "footwear":     "footwear",
    "navigation":   "navigation",
    "lighting":     "illumination",
    "safety":       "first_aid",
    "water":        "hydration",
    "shelter":      "shelter",
    "sleeping_bag": "sleep",
    "technical":    "traction",
}


def valid_levels(category: str) -> list[str]:
    """The allowed level values for a category (empty if it's presence-only)."""
    return list(LEVEL_SCALES.get(category, []))


def is_valid_level(category: str, level: str | None) -> bool:
    """True if `level` is a legal value for `category` (None always allowed —
    presence-only categories and 'I have it but didn't specify a tier')."""
    if level is None:
        return True
    return level in LEVEL_SCALES.get(category, [])


def resolve_gear_category(item_type: str | None, attrs: dict | None) -> str:
    """
    The functional category for a gear item. Prefers an explicit
    attributes.gear_category (new user gear); otherwise derives it from
    item_type, splitting the ambiguous 'clothing' bucket into shell (waterproof)
    vs insulation using the waterproof flag.
    """
    attrs = attrs or {}
    explicit = attrs.get("gear_category")
    if explicit:
        return explicit
    if item_type == "clothing":
        return "shell" if attrs.get("waterproof") else "insulation"
    return _ITEM_TYPE_TO_CATEGORY.get(item_type, "misc")


def resolve_level(gear_category: str, attrs: dict | None) -> str | None:
    """
    The user's capability level for a level-bearing category. Prefers an explicit
    attributes.level; otherwise derives it from the legacy typed attribute keys
    so already-seeded catalog gear gains adequacy for free. Returns None when
    nothing usable is present (→ presence-only for that item).
    """
    attrs = attrs or {}
    scale = LEVEL_SCALES.get(gear_category)
    if not scale:
        return None

    explicit = attrs.get("level")
    if explicit in scale:
        return explicit

    # Fallbacks from existing typed attribute keys (see ItemRepo._row_to_item).
    if gear_category == "footwear":
        ft = attrs.get("footwear_type")
        return ft if ft in scale else None
    if gear_category == "shelter":
        sr = attrs.get("season_rating")
        return sr if sr in scale else None
    if gear_category == "shell":
        return "hardshell" if attrs.get("waterproof") else "water_resistant"
    if gear_category == "navigation":
        return {"map": "map", "compass": "map", "gps": "gps",
                "satellite": "satellite"}.get(attrs.get("nav_type"))
    return None
