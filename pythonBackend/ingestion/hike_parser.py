"""
ingestion/parse_hike.py

Parses a single OSM relation dict into a (Hike, gear_reqs) tuple.
Used by relation-based ingestors as the per-item parsing step.

Returns None when the relation fails minimum hike criteria.
Returns (Hike, gear_reqs) on success — the caller is responsible for
persisting both:
    created = service.create_hike(hike)
    seed_gear(str(created.id), gear_reqs)
"""

from datetime import datetime
from uuid import uuid4

from PyObjects.Hike import Hike
from ingestion.characterizations import (
    calculate_difficulty,
    compute_metrics,
    find_data_quality_issues,
    infer_season,
    infer_region,
    is_valid_hike,
    derive_tags,
)
from ingestion.gear_inference import GearInferenceEngine
from ingestion.osm_geometry import altitude_stats, to_linestring


def parse_hike(osm_relation: dict) -> tuple[Hike, list[dict]] | None:
    tags   = osm_relation.get("tags", {})
    points = osm_relation.get("points")

    if not points or len(points) < 2:
        return None

    distance_m, gain_m = compute_metrics(points)
    if not is_valid_hike(distance_m, gain_m):
        return None

    # distance_m is the ONE-WAY path length; out-and-back doubling is NOT done
    # here. It is owned solely by ingestion/backfill_trail_distances.py, the final
    # pipeline step, which classifies + doubles off the merged geometry and stamps
    # trail_shape. See that module's header.
    length_km                = round(distance_m / 1000, 2)
    difficulty                = calculate_difficulty(length_km, gain_m, tags)
    season_start, season_end = infer_season(tags)
    geometry                 = to_linestring(points)
    min_alt, max_alt         = altitude_stats(points)
    first                    = points[0]
    region                   = infer_region(first["lat"], first["lon"])
    name                     = tags.get("name", "Unnamed Trail")
    permits                  = tags.get("access") == "permit"

    derived_tags = derive_tags(
        length_km          = length_km,
        elevation_gain_m   = gain_m,
        max_altitude_m     = max_alt or 0.0,
        season_start_month = season_start,
        season_end_month   = season_end,
        permits_required   = permits,
        name               = name,
    )
    if find_data_quality_issues(length_km, gain_m, difficulty, derived_tags):
        return None
    gear_reqs = GearInferenceEngine.infer_requirements(
        length_km  = length_km,
        gain_m     = gain_m,
        max_alt_m  = max_alt or 0.0,
        difficulty = difficulty,
        region     = region,
    )

    hike = Hike(
        id                 = uuid4(),
        source_id          = f"osm_relation_{osm_relation['id']}",
        name               = name,
        geometry           = geometry,
        difficulty         = difficulty,
        length_km          = length_km,
        elevation_gain_m   = round(gain_m, 1),
        min_altitude_m     = min_alt,
        max_altitude_m     = max_alt,
        region             = region,
        season_start_month = season_start,
        season_end_month   = season_end,
        permits_required   = permits,
        tags               = derived_tags,
        can_camp           = False,   # set by overpass_enrichment.py
        last_synced_at     = datetime.utcnow(),
        lat                = first["lat"],
        lng                = first["lon"],
        # trail_shape left NULL — set by backfill_trail_distances.py.
    )

    return hike, gear_reqs