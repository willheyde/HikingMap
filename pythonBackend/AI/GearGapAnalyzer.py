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

        user_gear items need at minimum:
            category (str)           — item_type of the owned item
            name     (str)
        Optional fields consumed:
            temp_rating_f (float)    — used for sleeping-bag adequacy check
            waterproof    (bool)     — distinguishes rain gear from
                                       insulating layers (both "clothing")
        """
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