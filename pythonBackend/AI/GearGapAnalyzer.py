"""
GearGapAnalyzer.py

Per-hike gear compatibility analysis.

Compares a user's owned-gear list against what a specific Hike object
demands and returns a list of GearGap objects.

Called once per hike candidate during the destination phase (before the
Groq prompt is assembled) so gear readiness is visible alongside trail
options.  No separate gear-discovery conversation is needed — Groq sees
the results as context, not as a task to perform.

Public API:

    analyzer = GearGapAnalyzer()
    gaps = analyzer.analyze_for_hike(user_gear, hike)

user_gear is the list[dict] returned by trip_chat._load_user_gear().
hike is any PyObjects.Hike instance from HikeSearchService.
"""

from __future__ import annotations

import logging
from typing import Set

from PyObjects.Items import ItemType
from .TripPlan import GearGap
from gear_levels import meets, sleep_meets, level_index

logger = logging.getLogger(__name__)

# ── Category identifiers ──────────────────────────────────────────────────────
#
# These must exactly match the `category` values stored on user gear items
# in the database (written at gear-creation time in the gear management UI).

CAT_SHELTER        = "shelter"
CAT_SLEEP_SYSTEM   = "sleep_system"
CAT_NAVIGATION     = "navigation"
CAT_ILLUMINATION   = "illumination"
CAT_FIRST_AID      = "first_aid"
CAT_HYDRATION      = "hydration"
CAT_INSULATION     = "insulation"
CAT_RAIN_GEAR      = "rain_gear"
CAT_TREKKING_POLES = "trekking_poles"
CAT_FOOTWEAR       = "footwear"

CATEGORY_TO_ITEM_TYPE: dict[str, str] = {
    CAT_SHELTER:        ItemType.SHELTER.value,
    CAT_SLEEP_SYSTEM:   ItemType.SLEEPING_BAG.value,
    CAT_NAVIGATION:     ItemType.NAVIGATION.value,
    CAT_ILLUMINATION:   ItemType.LIGHTING.value,
    CAT_FIRST_AID:      ItemType.SAFETY.value,
    CAT_HYDRATION:      ItemType.WATER.value,
    CAT_INSULATION:     ItemType.CLOTHING.value,
    CAT_RAIN_GEAR:      ItemType.CLOTHING.value,
    CAT_TREKKING_POLES: ItemType.TREKKING_POLES.value,
    CAT_FOOTWEAR:       ItemType.FOOTWEAR.value,
}

# Difficulty names that trigger extra checks.
# Must match the lowercased Hike.difficulty.name values in the DB.
_HARD_OR_ABOVE     = frozenset({"hard", "expert", "strenuous", "black"})
_MODERATE_OR_ABOVE = frozenset({"moderate", "hard", "expert", "strenuous", "black", "blue"})

_WATERPROOF_REQUIRED: dict[str, bool] = {
    CAT_RAIN_GEAR:  True,
    CAT_INSULATION: False,
}

def _user_owns_category(user_gear: list[dict], category: str) -> bool:
    """
    Returns True if the user's gear satisfies the given gap category.

    Compares against item_type (via CATEGORY_TO_ITEM_TYPE), not the raw gap
    category string — user gear items carry item_type as their "category"
    field (see trip_chat._load_user_gear), which doesn't match these CAT_*
    constants directly for most categories.

    insulation / rain_gear both resolve to "clothing"; `waterproof` further
    distinguishes a rain shell from a mid-layer.
    """
    item_type = CATEGORY_TO_ITEM_TYPE.get(category)
    if item_type is None:
        return False

    matches = [
        item for item in user_gear
        if item.get("category", "").lower().strip() == item_type
    ]
    if not matches:
        return False

    needs_waterproof = _WATERPROOF_REQUIRED.get(category)
    if needs_waterproof is None:
        return True

    return any(bool(item.get("waterproof")) == needs_waterproof for item in matches)


# ── Requirement-level metadata ────────────────────────────────────────────────
#
# Bridges the per-hike requirement categories emitted by
# GearInferenceEngine.infer_gear_levels() to the CAT_* / item_type vocabulary
# the rest of the gear pipeline (GEAR ADD, PromptBuilder) already speaks.

# req category → the GearGap.category to emit. Must be a CAT_* value so the
# GEAR ADD flow's CATEGORY_TO_ITEM_TYPE lookup still resolves. Traction has no
# item_type of its own; it rides under footwear, matching the legacy analyzer.
_REQ_TO_CAT: dict[str, str] = {
    "footwear":     CAT_FOOTWEAR,
    "traction":     CAT_FOOTWEAR,
    "insulation":   CAT_INSULATION,
    "shell":        CAT_RAIN_GEAR,
    "navigation":   CAT_NAVIGATION,
    "illumination": CAT_ILLUMINATION,
    "first_aid":    CAT_FIRST_AID,
    "hydration":    CAT_HYDRATION,
    "shelter":      CAT_SHELTER,
    "sleep":        CAT_SLEEP_SYSTEM,
}

_REQ_LABEL: dict[str, str] = {
    "footwear": "footwear", "traction": "traction devices",
    "insulation": "insulation layer", "shell": "rain shell",
    "navigation": "navigation", "illumination": "headlamp",
    "first_aid": "first-aid kit", "hydration": "water carry or treatment",
    "shelter": "shelter", "sleep": "sleep system",
}

_REQ_SUGGESTION: dict[str, str] = {
    "footwear":     "Boots suited to the terrain",
    "traction":     "Kahtoola MICROspikes (crampons for glacier/ice)",
    "insulation":   "Lightweight puffy or a fleece mid-layer",
    "shell":        "Patagonia Torrentshell 3L or any packable hardshell",
    "navigation":   "Gaia GPS (free tier) or a paper topo + compass",
    "illumination": "Black Diamond Spot 400",
    "first_aid":    "Adventure Medical Kits Ultralight .7",
    "hydration":    "Sawyer Squeeze + two 1 L soft flasks",
    "shelter":      "Big Agnes Copper Spur HV UL2 or a bivy for solo use",
    "sleep":        "Bag rated ~10 °F below the overnight low",
}

# Human display for capability levels, used in gap detail text.
_LEVEL_DISPLAY: dict[str, str] = {
    "sandal": "sandals", "trail_runner": "trail runners",
    "hiking_boot": "hiking boots", "mountaineering_boot": "mountaineering boots",
    "microspikes": "microspikes", "crampons": "crampons",
    "fleece": "a fleece layer", "puffy": "a puffy", "expedition": "an expedition-weight layer",
    "water_resistant": "a water-resistant shell", "hardshell": "a hardshell",
    "map": "a map & compass", "gps": "a GPS unit", "satellite": "a satellite communicator",
    "3_season": "a 3-season shelter", "4_season": "a 4-season shelter",
    "carry": "water capacity", "filter": "water filtration",
}

# Traction devices have no item_type; infer the user's level from item names.
_TRACTION_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("crampon", "crampons"),
    ("microspike", "microspikes"),
    ("yaktrax", "microspikes"),
    ("yak trax", "microspikes"),
    ("traction", "microspikes"),
)


def _display_level(level) -> str:
    return _LEVEL_DISPLAY.get(level, level or "the right gear")


def _user_traction_level(user_gear: list[dict]):
    """Best traction device the user owns, inferred from item names (there's no
    dedicated item_type). Returns a level from the traction scale, or None."""
    best, best_idx = None, -1
    for item in user_gear:
        name = item.get("name", "").lower()
        for kw, lvl in _TRACTION_KEYWORDS:
            if kw in name:
                idx = level_index("traction", lvl)
                if idx > best_idx:
                    best, best_idx = lvl, idx
    return best


def _user_min_sleep_temp(user_gear: list[dict]):
    """Warmest (lowest °F) temperature rating among the user's sleeping bags."""
    sleep_type = CATEGORY_TO_ITEM_TYPE[CAT_SLEEP_SYSTEM]
    temps = [
        float(item["temp_rating_f"]) for item in user_gear
        if (item.get("gear_category") == "sleep"
            or item.get("category", "").lower().strip() == sleep_type)
        and item.get("temp_rating_f") is not None
    ]
    return min(temps) if temps else None


def _owns_req_category(user_gear: list[dict], req_category: str, gap_cat: str) -> bool:
    """Presence check preferring the functional gear_category (A+ model), with a
    fallback to the legacy item_type mapping so pre-existing catalog gear still
    counts."""
    if any(item.get("gear_category") == req_category for item in user_gear):
        return True
    return _user_owns_category(user_gear, gap_cat)


def _best_user_level(user_gear: list[dict], req_category: str):
    """Highest capability level the user owns in a level-bearing category, read
    from each item's resolved `level` (set by trip_chat._load_user_gear)."""
    best, best_idx = None, -1
    for item in user_gear:
        if item.get("gear_category") == req_category and item.get("level"):
            idx = level_index(req_category, item["level"])
            if idx > best_idx:
                best, best_idx = item["level"], idx
    return best


class GearGapAnalyzer:
    """
    Stateless.  Instantiate once (module-level singleton in trip_chat.py)
    and call analyze_for_hike() for each candidate hike.
    """
    
    def analyze_for_hike(
        self,
        user_gear: list[dict],
        hike,               # PyObjects.Hike instance
    ) -> list[GearGap]:
        """
        Returns a list of GearGap objects for this hike / gear combination.
        An empty list means the user's kit looks solid for this trail.

        Prefers the hike's per-trail required LEVELS (hike.gear_requirements,
        from GearInferenceEngine.infer_gear_levels) so gaps reflect what THIS
        trail actually demands and can flag inadequate gear, not just absent
        gear. Falls back to the legacy hardcoded checks for any hike that
        predates the backfill (empty gear_requirements).
        """
        reqs = getattr(hike, "gear_requirements", None) or {}
        if reqs:
            return self._analyze_from_requirements(user_gear, reqs)
        return self._legacy_analyze(user_gear, hike)

    # ── Requirement-driven analysis (preferred) ───────────────────────────────

    def _analyze_from_requirements(self, user_gear: list[dict], reqs: dict) -> list[GearGap]:
        """Walk the hike's required categories, emitting a gap for each one the
        user is missing or under-equipped for. Required items are surfaced
        before recommended ones."""
        def _order(kv):
            _cat, spec = kv
            return (0 if spec.get("importance") == "required" else 1, _cat)

        gaps: list[GearGap] = []
        for category, spec in sorted(reqs.items(), key=_order):
            gap = self._check_requirement(user_gear, category, spec)
            if gap:
                gaps.append(gap)
        return gaps

    def readiness_for_hike(self, user_gear: list[dict], hike) -> list[dict]:
        """
        Full per-trail readiness for the 'double-check before you go' checklist:
        EVERY required category with a status, not just the gaps. Reuses the same
        presence/adequacy logic as analyze_for_hike (via _check_requirement) so
        the checklist and the AI's gap discussion can never disagree.

        Row shape: {category, label, importance, required, status, note}
          status "ok"      → green ✓ (satisfied)
          status "missing" → red ✗   (required category the user lacks)
          status "flag"    → amber ⚠ (recommended-but-absent, or under-spec)
        """
        reqs = getattr(hike, "gear_requirements", None) or {}

        def _order(kv):
            _cat, spec = kv
            return (0 if spec.get("importance") == "required" else 1, _cat)

        rows: list[dict] = []
        for category, spec in sorted(reqs.items(), key=_order):
            gap = self._check_requirement(user_gear, category, spec)

            if "min_level" in spec:
                required = _display_level(spec["min_level"])
            elif "min_temp_f" in spec:
                required = f"{int(spec['min_temp_f'])}°F bag"
            else:
                required = None

            if gap is None:
                status, note = "ok", None
            elif gap.issue == "missing":
                status, note = "missing", gap.detail
            else:
                status, note = "flag", gap.detail

            rows.append({
                "category":   category,
                "label":      _REQ_LABEL.get(category, category),
                "importance": spec.get("importance", "required"),
                "required":   required,
                "status":     status,
                "note":       note,
            })
        return rows

    def _check_requirement(self, user_gear: list[dict], req_category: str, spec: dict):
        importance = spec.get("importance", "required")
        required   = importance == "required"
        gap_cat    = _REQ_TO_CAT.get(req_category, req_category)

        # ── Presence ─────────────────────────────────────────────────────────
        if req_category == "traction":
            have_level = self._user_level_for_category(user_gear, "traction")
            owns       = have_level is not None
        else:
            owns       = _owns_req_category(user_gear, req_category, gap_cat)
            have_level = self._user_level_for_category(user_gear, req_category)

        if not owns:
            return GearGap(
                category   = gap_cat,
                issue      = "missing" if required else "marginal",
                detail     = self._missing_detail(req_category, spec, required),
                suggestion = _REQ_SUGGESTION.get(req_category),
            )

        # ── Adequacy — sleep is numeric (temperature), not an ordinal level ──
        if req_category == "sleep":
            need_temp = spec.get("min_temp_f")
            have_temp = _user_min_sleep_temp(user_gear)
            if have_temp is None:
                return GearGap(
                    category = gap_cat, issue = "marginal",
                    detail   = ("Sleep system found but no temperature rating is stored — "
                                "confirm it's warm enough for the overnight low."),
                )
            if not sleep_meets(have_temp, need_temp):
                return GearGap(
                    category   = gap_cat, issue = "marginal",
                    detail     = (f"Your warmest bag is rated {int(have_temp)}°F, but this trip's "
                                  f"overnight low calls for about {int(need_temp)}°F."),
                    suggestion = _REQ_SUGGESTION.get("sleep"),
                )
            return None

        # ── Adequacy — ordinal capability level ──────────────────────────────
        # Live for traction now; the other level-bearing categories switch on
        # automatically once the user gear model captures a level (stage 2), via
        # _user_level_for_category().
        need_level = spec.get("min_level")
        if need_level and have_level is not None and not meets(req_category, have_level, need_level):
            return GearGap(
                category   = gap_cat, issue = "marginal",
                detail     = (f"You have {_display_level(have_level)}, but this trail calls for "
                              f"{_display_level(need_level)}."),
                suggestion = _REQ_SUGGESTION.get(req_category),
            )
        return None

    def _missing_detail(self, req_category: str, spec: dict, required: bool) -> str:
        need_level = spec.get("min_level")
        label      = _REQ_LABEL.get(req_category, req_category)
        # A meaningful minimum level makes a more specific message than the bare
        # category name ("calls for hiking boots" > "no footwear"). "map"/"carry"
        # are the baseline tiers, so they don't add anything to name them.
        if need_level and need_level not in ("map", "carry"):
            return f"This trail calls for {_display_level(need_level)} — none on record."
        return f"No {label} on record ({'required' if required else 'recommended'} for this trail)."

    def _user_level_for_category(self, user_gear: list[dict], req_category: str):
        """The user's capability level for a level-bearing category, or None if
        it can't be determined. Prefers the resolved `level` on the gear (from
        an explicit level or a derived legacy attribute); traction additionally
        falls back to name inference, since traction devices have no item_type."""
        level = _best_user_level(user_gear, req_category)
        if level is not None:
            return level
        if req_category == "traction":
            return _user_traction_level(user_gear)
        return None

    # ── Legacy hardcoded analysis (fallback for un-backfilled hikes) ──────────

    def _legacy_analyze(
        self,
        user_gear: list[dict],
        hike,               # PyObjects.Hike instance
    ) -> list[GearGap]:
        # Name lookup for sub-category checks (traction devices, etc.)
        owned_names: Set[str] = {
            item.get("name", "").lower()
            for item in user_gear
        }

        difficulty_name: str = (
            hike.difficulty.name.lower()
            if hasattr(hike.difficulty, "name")
            else str(hike.difficulty).lower()
        )
        tags: Set[str]  = set(hike.tags or [])
        is_overnight    = bool(hike.can_camp)
        is_hard_plus    = difficulty_name in _HARD_OR_ABOVE
        is_moderate_up  = difficulty_name in _MODERATE_OR_ABOVE

        gaps: list[GearGap] = []

        # ── Ten-essentials baseline (applies to every hike) ───────────────────

        if not _user_owns_category(user_gear, CAT_NAVIGATION):
            gaps.append(GearGap(
                category   = CAT_NAVIGATION,
                issue      = "missing",
                detail     = "No navigation gear on record. A downloaded offline map is the bare minimum.",
                suggestion = "Gaia GPS (free tier) or a paper topo + compass",
            ))

        if not _user_owns_category(user_gear, CAT_ILLUMINATION):
            gaps.append(GearGap(
                category   = CAT_ILLUMINATION,
                issue      = "missing",
                detail     = "No headlamp — required on any hike in case the day runs long.",
                suggestion = "Black Diamond Spot 400",
            ))

        if not _user_owns_category(user_gear, CAT_FIRST_AID):
            gaps.append(GearGap(
                category   = CAT_FIRST_AID,
                issue      = "missing",
                detail     = "No first-aid kit on record.",
                suggestion = "Adventure Medical Kits Ultralight .7",
            ))

        if not _user_owns_category(user_gear, CAT_HYDRATION):
            gaps.append(GearGap(
                category   = CAT_HYDRATION,
                issue      = "missing",
                detail     = "No water carry or filtration gear on record.",
                suggestion = "Sawyer Squeeze + two 1 L soft flasks",
            ))

        if not _user_owns_category(user_gear, CAT_INSULATION):
            gaps.append(GearGap(
                category   = CAT_INSULATION,
                issue      = "marginal",
                detail     = "No insulation layer on record — temperatures can drop fast on exposed trails.",
                suggestion = "Lightweight puffy or a fleece mid-layer",
            ))

        # ── Overnight / camping extras ────────────────────────────────────────

        if is_overnight:
            if not _user_owns_category(user_gear, CAT_SHELTER):
                gaps.append(GearGap(
                    category   = CAT_SHELTER,
                    issue      = "missing",
                    detail     = "Camping is available on this trail but no shelter is on record.",
                    suggestion = "Big Agnes Copper Spur HV UL2 or a bivy for solo use",
                ))

            if not _user_owns_category(user_gear, CAT_SLEEP_SYSTEM):
                gaps.append(GearGap(
                    category   = CAT_SLEEP_SYSTEM,
                    issue      = "missing",
                    detail     = "No sleeping bag or quilt on record for an overnight hike.",
                    suggestion = "Sleeping bag rated at least 10 °F below expected overnight low",
                ))
            else:
                # Sleep system exists — check whether it has a temperature rating stored
                sleep_item_type = CATEGORY_TO_ITEM_TYPE[CAT_SLEEP_SYSTEM]
                rated = [
                    item for item in user_gear
                    if item.get("category", "").lower().strip() == sleep_item_type
                    and item.get("temp_rating_f") is not None
                ]
                if not rated:
                    gaps.append(GearGap(
                        category = CAT_SLEEP_SYSTEM,
                        issue    = "marginal",
                        detail   = (
                            "Sleep system found but no temperature rating is stored — "
                            "worth confirming it is adequate for overnight conditions on this trail."
                        ),
                    ))

        # ── Difficulty-based extras ───────────────────────────────────────────

        if is_hard_plus and not _user_owns_category(user_gear, CAT_TREKKING_POLES):
            gain_str = f"{hike.elevation_gain_m:,.0f} m gain" if hike.elevation_gain_m else "significant gain"
            gaps.append(GearGap(
                category   = CAT_TREKKING_POLES,
                issue      = "marginal",
                detail     = (
                    f"{difficulty_name.title()} difficulty with {gain_str} — "
                    "poles significantly reduce knee stress on the descent."
                ),
                suggestion = "Black Diamond Trail Ergo Cork or any collapsible pole",
            ))

        if is_moderate_up and not _user_owns_category(user_gear, CAT_RAIN_GEAR):
            gaps.append(GearGap(
                category   = CAT_RAIN_GEAR,
                issue      = "marginal",
                detail     = "No rain shell on record for a moderate-or-harder hike. Mountain weather changes fast.",
                suggestion = "Patagonia Torrentshell 3L or any packable hardshell",
            ))

        # ── Tag / feature-based extras ────────────────────────────────────────

        if tags & {"scramble", "technical", "via_ferrata"}:
            if not _user_owns_category(user_gear, CAT_FOOTWEAR):
                gaps.append(GearGap(
                    category   = CAT_FOOTWEAR,
                    issue      = "marginal",
                    detail     = "Trail involves scrambling — approach shoes or stiff hiking boots are strongly recommended.",
                ))

        if tags & {"snow", "winter", "glacier"}:
            has_traction = any(
                kw in name
                for name in owned_names
                for kw in ("microspike", "crampon", "yaktrax", "yak trax", "traction")
            )
            if not has_traction:
                gaps.append(GearGap(
                    category   = CAT_FOOTWEAR,
                    issue      = "missing",
                    detail     = "Snow or winter conditions on this trail — traction devices are required.",
                    suggestion = "Kahtoola MICROspikes",
                ))

        if tags & {"water_crossing", "ford", "river"}:
            gaps.append(GearGap(
                category   = CAT_FOOTWEAR,
                issue      = "marginal",
                detail     = "Trail has water crossings — waterproof or quick-dry footwear is recommended.",
            ))

        return gaps