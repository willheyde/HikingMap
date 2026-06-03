from osm_client     import fetch_hiking_routes
from osm_geometry   import build_points_from_relation
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from hike_parser    import parse_hike
from gear_inference import GearInferenceEngine
from seeder         import seed_hikes

# Bounding box: lat_min, lon_min, lat_max, lon_max
BBOX = "41.18, -71.91, 42.02, -71.08"

print(f"Fetching data for bbox: {BBOX} ...")
data     = fetch_hiking_routes(BBOX)
elements = data["elements"]
print(f"Received {len(elements)} elements from Overpass.\n")

hikes_with_gear = []   # list of (Hike, gear_reqs)
skipped_geo     = 0
skipped_filt    = 0
errors          = 0

relations = [el for el in elements if el["type"] == "relation"]
print(f"Processing {len(relations)} relation(s)...")

for el in relations:
    try:
        points = build_points_from_relation(el, elements)
        if not points:
            skipped_geo += 1
            continue

        el["points"] = points
        hike = parse_hike(el)

        if hike is None:
            skipped_filt += 1
            continue

        # Infer detailed gear requirements from this hike's physical stats
        gear_reqs = GearInferenceEngine.infer_requirements(
            length_km  = hike.length_km,
            gain_m     = hike.elevation_gain_m,
            max_alt_m  = hike.max_altitude_m or 0.0,
            difficulty = hike.difficulty,
            region     = hike.region,
        )

        hikes_with_gear.append((hike, gear_reqs))

    except Exception as e:
        name = el.get("tags", {}).get("name", f"id={el.get('id')}")
        print(f"  Error parsing '{name}': {e}")
        errors += 1

print(f"\nParsing summary:")
print(f"  Valid hikes:           {len(hikes_with_gear)}")
print(f"  Skipped (no geometry): {skipped_geo}")
print(f"  Skipped (too short):   {skipped_filt}")
print(f"  Parse errors:          {errors}")

if hikes_with_gear:
    print(f"\nSeeding {len(hikes_with_gear)} hike(s)...")
    seed_hikes(hikes_with_gear)
else:
    print("\nNo valid hikes to seed.")

print("Done.")