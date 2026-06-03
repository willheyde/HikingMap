# ingestion/gear_inference.py
"""
GearInferenceEngine

Returns structured gear requirements keyed to your actual items schema:
    [{"item_type": str, "filters": dict, "importance": str}, ...]

item_type values match items.item_type.
filter keys match attribute keys in items.attributes (jsonb).

Numeric filter values support operators:
    {"lte": 30}   →  (attributes->>'key')::float <= 30
    {"gte": 3.0}  →  (attributes->>'key')::float >= 3.0
Plain values are matched with equality. Booleans cast correctly.

Items with no DB equivalent (food, fuel, consumables) are intentionally
omitted — they don't exist in the items table.
"""

import math
from PyObjects.Hike import DifficultyLevel


BEAR_REGIONS = {
    "Alaska Range", "Yukon / Northern Rockies",
    "Rocky Mountains (Colorado)", "Rocky Mountains (Northern)",
    "Cascades",
}

BEAR_CANISTER_REGIONS = {
    "Sierra Nevada",
    "Rocky Mountains (Colorado)",
    "Rocky Mountains (Northern)",
    "Alaska Range",
    "Yukon / Northern Rockies",
}


class GearInferenceEngine:

    @staticmethod
    def infer_requirements(
        length_km:  float,
        gain_m:     float,
        max_alt_m:  float,
        difficulty: DifficultyLevel,
        region:     str,
    ) -> list[dict]:
        """
        Returns a list of {"item_type": str, "filters": dict, "importance": str}.
        Each entry resolves to one row in items via ItemResolver.
        """
        reqs: list[dict] = []

        def add(item_type: str, filters: dict, importance: str = "required") -> None:
            reqs.append({"item_type": item_type, "filters": filters, "importance": importance})

        # ── Derived flags ──────────────────────────────────────────────────────
        duration_h   = GearInferenceEngine._naismith(length_km, gain_m)
        is_multiday  = length_km > 20 or duration_h > 10
        is_alpine    = max_alt_m > 2000
        is_winter    = max_alt_m > 1500
        is_technical = max_alt_m > 2500
        diff_name    = difficulty.name          # EASY | MODERATE | DIFFICULT | EXPERT
        is_hard      = diff_name in {"DIFFICULT", "EXPERT"}

        # ── Backpack ───────────────────────────────────────────────────────────
        # size_class: "daypack" | "expedition"
        if is_multiday:
            add("backpack", {"size_class": "expedition"})
        else:
            add("backpack", {"size_class": "daypack"})

        # ── Navigation ────────────────────────────────────────────────────────
        # nav_type: "compass" | "gps"
        add("navigation", {"nav_type": "compass"})
        if is_hard or is_alpine:
            add("navigation", {"nav_type": "gps"}, "recommended")

        # ── Water treatment ───────────────────────────────────────────────────
        # system_type: "filter" | "purifier" | "tablets"
        # Note: water bottles/bladders are not in the items table.
        if is_multiday or length_km > 15:
            add("water", {"system_type": "filter"})
        elif length_km > 10:
            add("water", {"system_type": "tablets"}, "recommended")

        # ── Footwear ──────────────────────────────────────────────────────────
        # footwear_type: "mountaineering_boot" | "hiking_boot" | "trail_runner"
        # crampon_compatible: true | false
        if is_technical:
            add("footwear", {"crampon_compatible": True})
        elif gain_m > 300 or is_hard:
            add("footwear", {"footwear_type": "hiking_boot"})
        else:
            add("footwear", {"footwear_type": "trail_runner"})

        # ── Clothing — base layer ─────────────────────────────────────────────
        # layer_type: "base" | "mid" | "shell"
        # garment_type: "top" | "bottom"
        # waterproof: true | false
        add("clothing", {"layer_type": "base", "garment_type": "top"})

        # ── Clothing — insulation ─────────────────────────────────────────────
        if is_alpine or is_winter:
            add("clothing", {"layer_type": "mid", "garment_type": "top"})
            add("clothing", {"layer_type": "base", "min_temp_f": {"lte": 32}}, "recommended")
        elif max_alt_m > 1000 or length_km > 10:
            add("clothing", {"layer_type": "mid", "garment_type": "top"}, "recommended")

        # ── Weather protection ────────────────────────────────────────────────
        if is_hard:
            add("clothing", {"layer_type": "shell", "waterproof": True})
        else:
            add("clothing", {"layer_type": "shell", "waterproof": True}, "recommended")

        # ── Trekking poles ────────────────────────────────────────────────────
        # material: "carbon" | "aluminum" | adjustable: true
        if gain_m > 400:
            add("trekking_poles", {"adjustable": True})
        elif gain_m > 200:
            add("trekking_poles", {"adjustable": True}, "recommended")

        # ── Technical / alpine ────────────────────────────────────────────────
        # technical_type: "crampons" | "ice_axe" | "rope"
        if is_technical:
            add("technical", {"technical_type": "crampons"})
            add("technical", {"technical_type": "ice_axe"})
            add("technical", {"technical_type": "rope"}, "optional")
        elif is_winter:
            # Microspikes aren't in the DB — crampons are the closest match
            add("technical", {"technical_type": "crampons"}, "recommended")

        # ── Avalanche safety ──────────────────────────────────────────────────
        # safety_type: "probe" | "shovel" | "emergency_blanket"
        # avalanche_rated: true
        if max_alt_m > 2200 and gain_m > 500:
            add("safety", {"safety_type": "probe",  "avalanche_rated": True})
            add("safety", {"safety_type": "shovel", "avalanche_rated": True})

        # ── Emergency shelter ─────────────────────────────────────────────────
        # shelter_type: "bivy" | "tent" | "tarp"
        add("shelter", {"shelter_type": "bivy"}, "recommended" if is_hard else "optional")

        # ── Lighting ──────────────────────────────────────────────────────────
        # lighting_type: "headlamp"
        if duration_h > 6 or is_multiday:
            add("lighting", {"lighting_type": "headlamp"})

        # ── Sleep system ──────────────────────────────────────────────────────
        if is_multiday:
            # Shelter
            if is_alpine or is_technical:
                add("shelter", {"shelter_type": "tent", "season_rating": "4_season"})
            else:
                add("shelter", {"shelter_type": "tent", "season_rating": "3_season"})

            # Sleeping bag — temp_rating_f lte means "rated for at least this cold"
            if is_alpine or is_technical:
                add("sleeping_bag", {"temp_rating_f": {"lte": 0}})
            else:
                add("sleeping_bag", {"temp_rating_f": {"lte": 30}})

            # Sleeping pad
            add("sleeping_pad", {"pad_type": "inflatable"})
            add("sleeping_pad", {"pad_type": "foam"}, "optional")

            # Kitchen
            add("kitchen", {"stove_type": "canister"})

        return reqs

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _naismith(length_km: float, gain_m: float) -> float:
        return (length_km / 5.0) + (gain_m / 600.0)