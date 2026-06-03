"""
GearGapAnalyzer.py

Compares a user's owned gear against what a given trip requires.
Returns a list of GearGap objects (missing or marginal items).

No LLM involved — this is pure rule-based logic so it's fast,
free, and deterministic. The results get injected into the
PromptBuilder so Grok can discuss them naturally.
"""

from typing import Optional
from models.TripPlan import GearGap

# ── Gear category registry ────────────────────────────────────────────────────
#
# Maps each step key (from GearOnboarding STEPS) to a human label
# and the trip types that require it.
#
# required_for: set of activity_types that need this category
# overnight_only: True means only needed for multi-night trips
# weight_budget_g: warn if user's item(s) in this category exceed this
# temp_sensitive: True means we check sleeping bag temp rating

CATEGORY_RULES = {
    "backpack": {
        "label":         "Backpack",
        "required_for":  {"day_hike", "overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": False,
        "note":          None,
    },
    "footwear": {
        "label":         "Footwear",
        "required_for":  {"day_hike", "overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": False,
        "note":          None,
    },
    "shelter": {
        "label":         "Shelter",
        "required_for":  {"overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": True,
        "note":          "Required for any multi-night trip.",
    },
    "sleeping_bag": {
        "label":         "Sleeping Bag",
        "required_for":  {"overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": True,
        "temp_sensitive": True,
        "note":          None,
    },
    "sleeping_pad": {
        "label":         "Sleeping Pad",
        "required_for":  {"overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": True,
        "note":          "Insulation from the ground matters as much as your bag.",
    },
    "clothing": {
        "label":         "Clothing Layers",
        "required_for":  {"day_hike", "overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": False,
        "note":          None,
    },
    "water": {
        "label":         "Water System",
        "required_for":  {"day_hike", "overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": False,
        "note":          "Filter, purification tabs, or UV pen required on any backcountry trip.",
    },
    "kitchen": {
        "label":         "Kitchen / Cooking",
        "required_for":  {"overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": True,
        "note":          None,
    },
    "navigation": {
        "label":         "Navigation",
        "required_for":  {"day_hike", "overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": False,
        "note":          "Map + compass minimum. GPS device or downloaded offline maps recommended.",
    },
    "safety": {
        "label":         "Safety / First Aid",
        "required_for":  {"day_hike", "overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": False,
        "note":          "First aid kit + emergency signaling device (whistle, PLB, or satellite communicator).",
    },
    "lighting": {
        "label":         "Lighting",
        "required_for":  {"overnight", "backpacking", "extended", "mountaineering"},
        "overnight_only": True,
        "note":          None,
    },
    "trekking_poles": {
        "label":         "Trekking Poles",
        "required_for":  set(),          # never hard-required; flagged as optional
        "overnight_only": False,
        "note":          "Recommended for trips with significant elevation gain or descent.",
        "optional":      True,
    },
    "technical": {
        "label":         "Technical Gear",
        "required_for":  {"mountaineering"},
        "overnight_only": False,
        "note":          "Ice axe, crampons, and rope required for glaciated or alpine routes.",
    },
}

# Difficulty multipliers — harder trips raise the bar slightly
DIFFICULTY_NOTES = {
    "hard": "Given the strenuous difficulty, ensure all gear is in good repair and weight is optimized.",
    "moderate": None,
    "easy":     None,
}


# ── Analyzer ──────────────────────────────────────────────────────────────────

class GearGapAnalyzer:
    """
    Usage:
        analyzer = GearGapAnalyzer()
        gaps = analyzer.analyze(
            owned_items   = user.gear_items,   # list of item dicts from your DB
            activity_type = intent.activity_type,
            duration_days = intent.duration_days,
            difficulty    = intent.difficulty_hint,
            overnight_low_f = 28,              # optional, for sleeping bag check
        )
    """

    def analyze(
        self,
        owned_items:    list[dict],
        activity_type:  str,
        duration_days:  int,
        difficulty:     Optional[str]  = None,
        overnight_low_f: Optional[int] = None,    # expected overnight low in °F
    ) -> list[GearGap]:

        gaps: list[GearGap] = []
        is_overnight = duration_days > 1 or activity_type in {
            "overnight", "backpacking", "extended", "mountaineering"
        }

        # Build a lookup of what categories the user actually has gear in
        owned_by_category = self._index_by_category(owned_items)

        for cat_key, rule in CATEGORY_RULES.items():
            # Skip optional categories entirely — just surface as notes later
            if rule.get("optional"):
                continue

            # Skip overnight-only categories for day hikes
            if rule["overnight_only"] and not is_overnight:
                continue

            # Skip categories not required for this activity
            if activity_type not in rule["required_for"]:
                continue

            owned = owned_by_category.get(cat_key, [])

            # ── Missing entirely ───────────────────────────────────────────
            if not owned:
                gaps.append(GearGap(
                    category   = cat_key,
                    issue      = "missing",
                    detail     = f"No {rule['label']} found in your gear locker."
                                 + (f" {rule['note']}" if rule.get("note") else ""),
                    suggestion = self._suggest(cat_key, activity_type, difficulty),
                ))
                continue

            # ── Temp sensitivity check (sleeping bag only) ─────────────────
            if rule.get("temp_sensitive") and overnight_low_f is not None:
                marginal = self._check_sleep_bag_temp(owned, overnight_low_f)
                if marginal:
                    gaps.append(marginal)

        # ── Difficulty-level note (not a gap, surfaced as a marginal) ──────
        if difficulty == "hard":
            gaps.append(GearGap(
                category   = "general",
                issue      = "marginal",
                detail     = DIFFICULTY_NOTES["hard"],
                suggestion = None,
            ))

        return gaps

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _index_by_category(self, items: list[dict]) -> dict[str, list[dict]]:
        """
        Group owned items by their category key.
        Expects each item dict to have a 'category' field matching CATEGORY_RULES keys.
        """
        index: dict[str, list[dict]] = {}
        for item in items:
            cat = item.get("category", "").lower().replace(" ", "_")
            index.setdefault(cat, []).append(item)
        return index

    def _check_sleep_bag_temp(
        self,
        sleeping_bags: list[dict],
        overnight_low_f: int,
    ) -> Optional[GearGap]:
        """
        Check if any owned sleeping bag is rated for the overnight low.
        Bags need a 5°F buffer below the expected low (conservative).
        Returns a GearGap if marginal, None if fine.
        """
        BUFFER = 5
        target = overnight_low_f - BUFFER   # e.g. low=28 → need rated ≤ 23°F

        # Look for a 'temp_rating_f' field on each bag item
        for bag in sleeping_bags:
            rating = bag.get("temp_rating_f")
            if rating is None:
                continue
            if int(rating) <= target:
                return None     # at least one bag is adequate

        # Either no rating data, or all bags are too warm
        best = min(
            (b.get("temp_rating_f") for b in sleeping_bags if b.get("temp_rating_f") is not None),
            default=None,
        )
        if best is not None:
            return GearGap(
                category   = "sleeping_bag",
                issue      = "marginal",
                detail     = (
                    f"Your sleeping bag is rated to {best}°F but overnight lows "
                    f"may reach {overnight_low_f}°F. A {BUFFER}°F safety buffer is recommended."
                ),
                suggestion = "Consider a bag rated to at least "
                             f"{overnight_low_f - BUFFER}°F, or add a liner for ~10°F warmth.",
            )
        # No rating data at all — surface as a warning
        return GearGap(
            category   = "sleeping_bag",
            issue      = "marginal",
            detail     = (
                f"Your sleeping bag's temperature rating is unknown. "
                f"Overnight lows may reach {overnight_low_f}°F — verify before you go."
            ),
            suggestion = None,
        )

    def _suggest(
        self,
        category:      str,
        activity_type: str,
        difficulty:    Optional[str],
    ) -> Optional[str]:
        """
        Return a short, opinionated suggestion string for a missing category.
        Lightweight — no LLM, just curated defaults.
        """
        suggestions = {
            "backpack": {
                "day_hike":      "Osprey Daylite Plus (20L) — lightweight, comfortable for day trips.",
                "overnight":     "Osprey Atmos AG 50 — great fit system for overnight hauls.",
                "backpacking":   "Osprey Atmos AG 65 or ULA Circuit for multi-day trips.",
                "extended":      "ULA Circuit or Hyperlite Mountain Gear 3400 for extended routes.",
                "mountaineering":"Black Diamond Cirque 45 — built for technical terrain.",
            },
            "shelter": {
                "overnight":     "Big Agnes Copper Spur HV UL2 — ultralight, easy setup.",
                "backpacking":   "Big Agnes Copper Spur HV UL2 or Tarptent Notch Li.",
                "extended":      "Tarptent Notch Li for weight savings on long routes.",
                "mountaineering":"Black Diamond Mega Light — handles alpine conditions.",
            },
            "sleeping_bag": {
                "overnight":     "Feathered Friends Flicker UL 20 — packable and warm.",
                "backpacking":   "Western Mountaineering Alpinlite 20°F.",
                "extended":      "Western Mountaineering Ultralite 28°F or Megalite 30°F.",
                "mountaineering":"Mountain Hardwear Phantom 15°F.",
            },
            "sleeping_pad": {
                "_default":      "Therm-a-Rest NeoAir XLite NXT — best warmth-to-weight ratio.",
            },
            "water": {
                "_default":      "Sawyer Squeeze (85g) + 2× 1L soft flasks. Add Aquatabs as backup.",
            },
            "kitchen": {
                "_default":      "BRS-3000T stove (25g) + 450ml titanium pot. Bring a lighter + matches.",
            },
            "navigation": {
                "_default":      "Gaia GPS app (offline maps) + printed topo map + baseplate compass.",
            },
            "safety": {
                "day_hike":      "Adventure Medical Kits Ultralight .7 first aid kit + whistle.",
                "_default":      "Adventure Medical Kits Ultralight .7 + ACR ResQLink PLB for remote trips.",
            },
            "lighting": {
                "_default":      "Black Diamond Spot 400 headlamp — reliable, 400 lumens.",
            },
            "clothing": {
                "_default":      "Base layer (Merino wool), mid layer (fleece), hardshell jacket.",
            },
            "technical": {
                "mountaineering":"Petzl Summit E ice axe + Black Diamond Sabretooth crampons.",
            },
            "footwear": {
                "day_hike":      "Altra Lone Peak 7 (trail runner) for light terrain.",
                "mountaineering":"La Sportiva Trango Tech GTX for technical approaches.",
                "_default":      "Salomon X Ultra 4 GTX — waterproof, supportive, versatile.",
            },
        }

        cat_suggestions = suggestions.get(category, {})
        return (
            cat_suggestions.get(activity_type)
            or cat_suggestions.get("_default")
        )