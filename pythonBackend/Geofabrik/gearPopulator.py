#!/usr/bin/env python3
"""
populate_items.py

Reads GEAR_TAG_TO_ITEM_SPEC from AllGear.py and posts each item to the
appropriate FastAPI endpoint:

 - /items/backpacks  -> BackpackCreateSchema
 - /items/clothing   -> ClothingCreateSchema
 - /items/shoes      -> ShoesCreateSchema

Skips items with the same name already present on the server.
"""

import sys
import time
import importlib
import traceback
from typing import Dict, Any

import requests

# Change this if your API runs elsewhere
BASE_URL = "http://localhost:8000/items"

# Try to import the AllGear module where your dict is defined.
# Adjust sys.path if needed (this assumes script is run from repo root).
try:
    # If AllGear.py is in a different directory, adjust sys.path before import.
    # Example: sys.path.append("path/to/where/AllGear/is")
    import AllGear
except Exception as e:
    print("Failed to import AllGear.py automatically. If AllGear.py is not on sys.path,")
    print("make sure to set PYTHONPATH or modify sys.path in this script.")
    raise

GEAR: Dict[str, Dict[str, Any]] = getattr(AllGear, "GEAR_TAG_TO_ITEM_SPEC", None)
if GEAR is None:
    raise RuntimeError("AllGear.GEAR_TAG_TO_ITEM_SPEC not found")

# Helper to convert WeatherConditions enum -> string name
def normalize_weather(w) -> str:
    """
    Accepts either:
     - an enum instance (e.g., WeatherConditions.FREEZING),
     - a string (e.g., 'FREEZING' or 'Freezing'),
     - or None.
    Returns a string accepted by the API (uppercase enum name).
    Default: 'FINE' if missing or unrecognized.
    """
    if w is None:
        return "FINE"
    # enum instances often have .name
    name = None
    if hasattr(w, "name"):
        name = w.name
    else:
        name = str(w)
    name = name.strip().upper()
    # Ensure valid fallback
    valid = {"FREEZING", "COLD", "FINE", "WARM", "HOT"}
    if name not in valid:
        return "FINE"
    return name

# Fetch existing items from server to avoid duplicates (by name)
def fetch_existing_names() -> set:
    try:
        resp = requests.get(f"{BASE_URL}/")
        resp.raise_for_status()
        items = resp.json()
        names = {it["name"] for it in items}
        return names
    except Exception as e:
        print("Warning: could not fetch existing items from server:", e)
        return set()

def create_backpack(payload: dict) -> requests.Response:
    return requests.post(f"{BASE_URL}/backpacks", json=payload)

def create_clothing(payload: dict) -> requests.Response:
    return requests.post(f"{BASE_URL}/clothing", json=payload)

def create_shoes(payload: dict) -> requests.Response:
    return requests.post(f"{BASE_URL}/shoes", json=payload)

# Main loop
def main():
    existing = fetch_existing_names()
    created = []
    skipped = []
    failed = []

    # small throttle so we don't spam server
    SLEEP_BETWEEN = 0.05

    for tag, spec in GEAR.items():
        try:
            t = spec.get("type", "").lower()
            name = spec.get("name")
            weight = spec.get("weight", 0.0)
            cost = spec.get("cost", 0.0)

            if not name:
                print(f"Skipping {tag}: no name provided")
                skipped.append((tag, "no_name"))
                continue

            if name in existing:
                skipped.append((tag, "exists"))
                print(f"Skipping '{name}' (already exists)")
                continue

            if t == "backpack":
                payload = {
                    "name": name,
                    "weight": float(weight),
                    "cost": float(cost),
                    # ensure capacity_liters present (BackpackCreateSchema requires it)
                    "capacity_liters": float(spec.get("capacity_liters", 0.0))
                }
                resp = create_backpack(payload)

            elif t == "clothing":
                payload = {
                    "name": name,
                    "weight": float(weight),
                    "cost": float(cost),
                    "weather_conditions": normalize_weather(spec.get("weather_conditions"))
                }
                resp = create_clothing(payload)

            elif t == "shoes":
                payload = {
                    "name": name,
                    "weight": float(weight),
                    "cost": float(cost),
                    "weather_conditions": normalize_weather(spec.get("weather_conditions")),
                    "crampons": bool(spec.get("crampons", False))
                }
                resp = create_shoes(payload)

            else:
                # unknown type -> treat as backpack (your design uses 'backpack' for generic gear)
                print(f"Unknown type '{t}' for {tag} — creating as backpack (generic)")
                payload = {
                    "name": name,
                    "weight": float(weight),
                    "cost": float(cost),
                    "capacity_liters": float(spec.get("capacity_liters", 0.0))
                }
                resp = create_backpack(payload)

            # handle response
            if resp.ok:
                data = resp.json()
                created.append((tag, data.get("id")))
                existing.add(name)
                print(f"Created '{name}' ({tag}) -> id {data.get('id')}")
            else:
                # server returned error
                try:
                    err = resp.json()
                except Exception:
                    err = resp.text
                failed.append((tag, resp.status_code, err))
                print(f"Failed to create '{name}' ({tag}): {resp.status_code} {err}")

            time.sleep(SLEEP_BETWEEN)

        except Exception as ex:
            tb = traceback.format_exc()
            failed.append((tag, "exception", str(ex)))
            print(f"Exception while processing {tag}: {ex}")
            print(tb)

    # summary
    print("\n=== POPULATION SUMMARY ===")
    print(f"Total gear entries processed: {len(GEAR)}")
    print(f"Created: {len(created)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed details (first 10):")
        for f in failed[:10]:
            print(f)

if __name__ == "__main__":
    main()
