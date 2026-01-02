from ingestion.osm_client import fetch_hiking_routes
from ingestion.osm_geometry import build_points_from_relation
from ingestion.hike_parser import parse_hike
from ingestion.seeder import seed_hikes

# 1. Define a bounding box (lat_min, lon_min, lat_max, lon_max)
# Example: Zermatt, Switzerland area
BBOX = "45.9, 7.6, 46.1, 7.9"

print("Fetching data...")
data = fetch_hiking_routes(BBOX)
elements = data["elements"]

hikes = []
print(f"Processing {len(elements)} elements...")

for el in elements:
    # We only care about relations (routes), not individual nodes/ways
    if el["type"] != "relation":
        continue

    points = build_points_from_relation(el, elements)
    if not points:
        continue

    # Inject points into the relation object so parser can use them
    el["points"] = points
    
    hike = parse_hike(el)
    if hike:
        hikes.append(hike)

print(f"Seeding {len(hikes)} hikes...")
seed_hikes(hikes)
print("Done.")