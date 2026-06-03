#!/usr/bin/env python3
"""
populate_items.py

Reads GEAR_TAG_TO_ITEM_SPEC from AllGear.py and POSTs each item to the
correct FastAPI endpoint based on its "type" field.

Endpoint map (matches ItemController routes):
  backpack      -> POST /items/backpacks
  footwear      -> POST /items/footwear
  shelter       -> POST /items/shelters
  sleeping_bag  -> POST /items/sleeping-bags
  sleeping_pad  -> POST /items/sleeping-pads
  clothing      -> POST /items/clothing
  water         -> POST /items/water
  kitchen       -> POST /items/kitchen
  navigation    -> POST /items/navigation
  lighting      -> POST /items/lighting
  safety        -> POST /items/safety
  technical     -> POST /items/technical
  trekking_poles-> POST /items/trekking-poles

Skips items whose name already exists on the server.
"""

import sys
import time
import traceback
from typing import Any

import requests

BASE_URL = "http://localhost:8000/items"

# ── Type → endpoint path ───────────────────────────────────────────────────────

ENDPOINT_MAP = {
    "backpack":       "backpacks",
    "footwear":       "footwear",
    "shelter":        "shelters",
    "sleeping_bag":   "sleeping-bags",
    "sleeping_pad":   "sleeping-pads",
    "clothing":       "clothing",
    "water":          "water",
    "kitchen":        "kitchen",
    "navigation":     "navigation",
    "lighting":       "lighting",
    "safety":         "safety",
    "technical":      "technical",
    "trekking_poles": "trekking-poles",
}

# ── Type-specific payload builders ─────────────────────────────────────────────
# Each function receives the full spec dict and returns the POST body.
# Only fields accepted by the matching CreateSchema are included.

def _base(spec: dict) -> dict:
    """Fields common to every create schema."""
    return {
        "name":   spec["name"],
        "weight": float(spec.get("weight", 0.0)),
        "cost":   float(spec.get("cost", 0.0)),
    }

def _build_backpack(spec: dict) -> dict:
    return {**_base(spec),
            "capacity_liters": float(spec.get("capacity_liters", 0.0)),
            "frame_type":      spec.get("frame_type", "internal")}

def _build_footwear(spec: dict) -> dict:
    return {**_base(spec),
            "waterproof":          bool(spec.get("waterproof", False)),
            "crampon_compatible":  bool(spec.get("crampon_compatible", False)),
            "ankle_support":       spec.get("ankle_support", "low")}

def _build_shelter(spec: dict) -> dict:
    return {**_base(spec),
            "capacity_persons": int(spec.get("capacity_persons", 1)),
            "season_rating":    spec.get("season_rating", "3_season"),
            "shelter_type":     spec.get("shelter_type", "tent")}

def _build_sleeping_bag(spec: dict) -> dict:
    return {**_base(spec),
            "temp_rating_f": int(spec.get("temp_rating_f", 32)),
            "fill_type":     spec.get("fill_type", "synthetic")}

def _build_sleeping_pad(spec: dict) -> dict:
    return {**_base(spec),
            "r_value":  float(spec.get("r_value", 2.0)),
            "pad_type": spec.get("pad_type", "foam")}

def _build_clothing(spec: dict) -> dict:
    return {**_base(spec),
            "layer_type": spec.get("layer_type", "mid"),
            "waterproof": bool(spec.get("waterproof", False)),
            "min_temp_f": int(spec.get("min_temp_f", 32))}

def _build_water(spec: dict) -> dict:
    return {**_base(spec),
            "system_type":   spec.get("system_type", "filter"),
            "flow_rate_lpm": float(spec.get("flow_rate_lpm", 1.0))}

def _build_kitchen(spec: dict) -> dict:
    return {**_base(spec),
            "stove_type":        spec.get("stove_type"),
            "cookware_included": bool(spec.get("cookware_included", False)),
            "boil_time_min":     float(spec.get("boil_time_min", 0.0))}

def _build_navigation(spec: dict) -> dict:
    return {**_base(spec),
            "nav_type": spec.get("nav_type", "map")}

def _build_lighting(spec: dict) -> dict:
    return {**_base(spec),
            "lumens":       int(spec.get("lumens", 0)),
            "lighting_type": spec.get("lighting_type", "headlamp")}

def _build_safety(spec: dict) -> dict:
    return {**_base(spec),
            "safety_type":     spec.get("safety_type", "first_aid"),
            "avalanche_rated": bool(spec.get("avalanche_rated", False))}

def _build_technical(spec: dict) -> dict:
    return {**_base(spec),
            "technical_type": spec.get("technical_type", "ice_axe")}

def _build_trekking_poles(spec: dict) -> dict:
    return {**_base(spec),
            "adjustable": bool(spec.get("adjustable", True)),
            "material":   spec.get("material", "aluminum")}

PAYLOAD_BUILDERS = {
    "backpack":       _build_backpack,
    "footwear":       _build_footwear,
    "shelter":        _build_shelter,
    "sleeping_bag":   _build_sleeping_bag,
    "sleeping_pad":   _build_sleeping_pad,
    "clothing":       _build_clothing,
    "water":          _build_water,
    "kitchen":        _build_kitchen,
    "navigation":     _build_navigation,
    "lighting":       _build_lighting,
    "safety":         _build_safety,
    "technical":      _build_technical,
    "trekking_poles": _build_trekking_poles,
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_existing_names() -> set:
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        resp.raise_for_status()
        return {it["name"] for it in resp.json()}
    except Exception as e:
        print(f"Warning: could not fetch existing items — duplicate check disabled. ({e})")
        return set()

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    try:
        import AllGear
    except ImportError:
        print("Could not import AllGear.py — make sure it's on sys.path.")
        raise

    gear = getattr(AllGear, "GEAR_TAG_TO_ITEM_SPEC", None)
    if gear is None:
        raise RuntimeError("AllGear.GEAR_TAG_TO_ITEM_SPEC not found")

    existing = fetch_existing_names()
    created, skipped, failed = [], [], []
    SLEEP = 0.05

    for tag, spec in gear.items():
        try:
            item_type = spec.get("type", "").lower()
            name      = spec.get("name")

            if not name:
                print(f"  [{tag}] Skipping — no name")
                skipped.append((tag, "no_name"))
                continue

            if name in existing:
                print(f"  [{tag}] Skipping '{name}' — already exists")
                skipped.append((tag, "exists"))
                continue

            # Route to correct endpoint
            endpoint_path = ENDPOINT_MAP.get(item_type)
            if not endpoint_path:
                print(f"  [{tag}] Unknown type '{item_type}' — skipping "
                      f"(valid types: {', '.join(ENDPOINT_MAP)})")
                failed.append((tag, "unknown_type", item_type))
                continue

            builder = PAYLOAD_BUILDERS[item_type]
            payload = builder(spec)
            url     = f"{BASE_URL}/{endpoint_path}"

            resp = requests.post(url, json=payload, timeout=10)

            if resp.ok:
                item_id = resp.json().get("id")
                print(f"  [{tag}] Created '{name}' ({item_type}) -> {item_id}")
                created.append((tag, item_id))
                existing.add(name)
            else:
                try:
                    err = resp.json()
                except Exception:
                    err = resp.text
                print(f"  [{tag}] Failed '{name}': {resp.status_code} {err}")
                failed.append((tag, resp.status_code, err))

            time.sleep(SLEEP)

        except Exception as ex:
            print(f"  [{tag}] Exception: {ex}")
            print(traceback.format_exc())
            failed.append((tag, "exception", str(ex)))

    print("\n=== POPULATION SUMMARY ===")
    print(f"  Total entries : {len(gear)}")
    print(f"  Created       : {len(created)}")
    print(f"  Skipped       : {len(skipped)}")
    print(f"  Failed        : {len(failed)}")

    if failed:
        print("\nFailed entries (first 10):")
        for f in failed[:10]:
            print(f"  {f}")

if __name__ == "__main__":
    main()