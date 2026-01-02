from uuid import uuid4
from PyObjects.Hike import Hike

# 1. Imports from your 'matches below' file (characterizations.py)
from ingestion.characterizations import (
    compute_metrics,
    infer_difficulty,
    infer_season,
    infer_required_gear,
    infer_region
)

# 2. Imports from osm_geometry (where we put the geometry logic in the previous step)
from ingestion.osm_geometry import to_linestring, altitude_stats

# 3. Import from filters (assuming you kept filters.py separate)
from ingestion.filters import is_valid_hike 

def parse_hike(osm_relation):
    tags = osm_relation.get("tags", {})
    points = osm_relation.get("points")

    # Basic data validation
    if not points or len(points) < 2:
        return None

    # Calculate metrics using the logic from characterizations.py
    distance_m, gain_m = compute_metrics(points)

    # Filter out hikes that are too short/flat
    if not is_valid_hike(distance_m, gain_m):
        return None

    # Apply heuristics
    difficulty = infer_difficulty(tags)
    season_start, season_end = infer_season(tags)
    gear = infer_required_gear(tags, difficulty)
    
    # Calculate geometry stats
    min_alt, max_alt = altitude_stats(points)
    geometry = to_linestring(points)

    # Infer region based on the start point
    first = points[0]
    region = infer_region(first["lat"], first["lon"])

    return Hike(
        id=uuid4(),
        source_id=f"osm_relation_{osm_relation['id']}",
        name=tags.get("name", "Unnamed Trail"),
        geometry=geometry,
        difficulty=difficulty,
        length_km=distance_m / 1000,
        elevation_gain_m=gain_m,
        min_altitude_m=min_alt,
        max_altitude_m=max_alt,
        region=region,
        season_start_month=season_start,
        season_end_month=season_end,
        required_gear_tags=gear,
        permits_required=tags.get("access") == "permit"
    )