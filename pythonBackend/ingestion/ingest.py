"""
ingest.py

Usage (from project root):
    python ingestion/ingest.py

Reads a .osm.pbf file, extracts named hiking paths,
computes elevation / difficulty / gear, and seeds the database.

Requirements:
    pip install osmium srtm.py geopy python-dotenv
"""

import sys
import uuid
import logging
from datetime import datetime
from pathlib import Path

import osmium
import srtm
from geopy.distance import geodesic

sys.path.append(str(Path(__file__).parent.parent))

from DBConnection import get_connection
from PyObjects.Hike import Hike, DifficultyLevel
from Repos.HikeRepo import HikeRepository
from Services.HikeService import HikeService
from ingestion.gear_inference import GearInferenceEngine
from ingestion.characterizations import (
    calculate_difficulty,
    derive_tags,
    estimate_season,
    infer_permits_required,
    infer_region,
    is_valid_hike,
    is_noise,
)
from ingestion.seeder import seed_gear

# ── Config ─────────────────────────────────────────────────────────────────────

PBF_FILE = "rhode-island-260101.osm.pbf"

VALID_HIGHWAY_TAGS = {"path", "track", "footway"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Services ───────────────────────────────────────────────────────────────────

repo    = HikeRepository()
service = HikeService(repo)

# ── Elevation ──────────────────────────────────────────────────────────────────

elevation_data = srtm.get_data()


def get_elevation(lat: float, lon: float) -> float:
    try:
        ele = elevation_data.get_elevation(lat, lon)
        return float(ele) if ele is not None else 0.0
    except Exception:
        return 0.0


# ── Geometry helpers ───────────────────────────────────────────────────────────

def compute_distance_km(nodes: list[tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(nodes) - 1):
        total += geodesic(nodes[i], nodes[i + 1]).km
    return total


def compute_elevation_stats(
    nodes: list[tuple[float, float]],
) -> tuple[float, float, float, list]:
    """Returns (gain_m, min_ele_m, max_ele_m, geojson_coords)."""
    elevations = [get_elevation(lat, lon) for lat, lon in nodes]
    gain = sum(
        max(0.0, elevations[i] - elevations[i - 1])
        for i in range(1, len(elevations))
    )
    coords_3d = [[lon, lat, ele] for (lat, lon), ele in zip(nodes, elevations)]
    return gain, min(elevations), max(elevations), coords_3d


# ── OSM handler ────────────────────────────────────────────────────────────────

class HikeHandler(osmium.SimpleHandler):

    def __init__(self):
        super().__init__()
        self.saved   = 0
        self.skipped = 0
        self.errors  = 0

    def way(self, w):
        # 1. Cheap tag filters first — no variable allocation needed
        if w.tags.get("highway") not in VALID_HIGHWAY_TAGS:
            return
        name = w.tags.get("name")
        if not name:
            return
        if is_noise(name, dict(w.tags)):
            self.skipped += 1
            return

        # 2. Nodes — can raise on missing location data
        try:
            nodes = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(nodes) < 2:
            return

        # 3. Distance + elevation — skip early if too short/flat
        length_km = compute_distance_km(nodes)
        gain_m, min_ele, max_ele, coords_3d = compute_elevation_stats(nodes)

        if not is_valid_hike(length_km * 1000, gain_m):
            self.skipped += 1
            return

        # 4. Metadata
        difficulty               = calculate_difficulty(length_km, gain_m)
        season_start, season_end = estimate_season(max_ele)
        region                   = infer_region(nodes[0][0], nodes[0][1])
        permits                  = infer_permits_required(dict(w.tags))
        source_id                = f"osm_way_{w.id}"

        # 5. Skip if already in DB
        if service.get_by_source_id(source_id):
            self.skipped += 1
            return

        # 6. Derive searchable tags from computed metrics.
        #    Feature tags (waterfall, lake, summit, can_camp, etc.) are added
        #    later by the Overpass enrichment script — not available here.
        tags = derive_tags(
            length_km          = length_km,
            elevation_gain_m   = gain_m,
            max_altitude_m     = max_ele,
            season_start_month = season_start,
            season_end_month   = season_end,
            permits_required   = permits,
        )

        # 7. Gear requirements
        gear_reqs = GearInferenceEngine.infer_requirements(
            length_km  = length_km,
            gain_m     = gain_m,
            max_alt_m  = max_ele,
            difficulty = difficulty,
            region     = region,
        )

        # 8. Save hike + gear
        try:
            hike = Hike(
                id                 = uuid.uuid4(),
                source_id          = source_id,
                name               = name,
                geometry           = {"type": "LineString", "coordinates": coords_3d},
                difficulty         = difficulty,
                length_km          = round(length_km, 2),
                elevation_gain_m   = round(gain_m, 1),
                min_altitude_m     = round(min_ele, 1),
                max_altitude_m     = round(max_ele, 1),
                region             = region,
                season_start_month = season_start,
                season_end_month   = season_end,
                permits_required   = permits,
                tags               = tags,
                can_camp           = False,   # set by Overpass enrichment script
                last_synced_at     = datetime.utcnow(),
            )
            created = service.create_hike(hike)
            seed_gear(str(created.id), gear_reqs)

            self.saved += 1
            if self.saved % 25 == 0:
                log.info(f"Saved {self.saved} hikes so far...")

        except Exception as e:
            log.error(f"Failed to save '{name}': {e}")
            self.errors += 1


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    log.info(f"Reading {PBF_FILE} ...")
    handler = HikeHandler()
    handler.apply_file(PBF_FILE, locations=True)

    log.info("─" * 40)
    log.info(f"Saved   : {handler.saved}")
    log.info(f"Skipped : {handler.skipped}")
    log.info(f"Errors  : {handler.errors}")


if __name__ == "__main__":
    main()