from uuid import uuid4
from PyObjects.Hike import Hike

from ingestion.characterizations import (
    compute_metrics,
    infer_difficulty,
    infer_season,
    infer_required_gear,
    infer_region,
    is_valid_hike,          # FIX: was imported from ingestion.filters (didn't exist)
)
from ingestion.osm_geometry import to_linestring, altitude_stats


def parse_hike(osm_relation: dict) -> Hike | None:
    tags   = osm_relation.get("tags", {})
    points = osm_relation.get("points")

    if not points or len(points) < 2:
        return None

    distance_m, gain_m = compute_metrics(points)

    if not is_valid_hike(distance_m, gain_m):
        return None

    difficulty   = infer_difficulty(tags)
    season_start, season_end = infer_season(tags)
    gear         = infer_required_gear(tags, difficulty)
    geometry     = to_linestring(points)

    # FIX: altitude_stats now returns (None, None) when no elevation data
    # exists rather than (0, 0), so we pass those through honestly.
    min_alt, max_alt = altitude_stats(points)

    first  = points[0]
    region = infer_region(first["lat"], first["lon"])

    return Hike(
        id=uuid4(),
        source_id=f"osm_relation_{osm_relation['id']}",
        name=tags.get("name", "Unnamed Trail"),
        geometry=geometry,
        difficulty=difficulty,
        length_km=round(distance_m / 1000, 2),
        elevation_gain_m=round(gain_m, 1),
        min_altitude_m=min_alt,
        max_altitude_m=max_alt,
        region=region,
        season_start_month=season_start,
        season_end_month=season_end,
        required_gear_tags=gear,
        permits_required=tags.get("access") == "permit",
    )