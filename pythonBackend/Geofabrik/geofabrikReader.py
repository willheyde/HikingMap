# geofabrikReader.py
import osmium
import srtm
import math
import uuid
import json
import logging
import sys
from datetime import datetime
from geopy.distance import geodesic
from typing import Tuple, List

sys.path.append('..')

from PyObjects.Hike import Hike, DifficultyLevel
from PyObjects.Items import Backpack, Clothing, Shoes, WeatherConditions
from Repos.HikeRepo import HikeRepository
from Repos.ItemRepo import ItemRepository
from Services.HikeService import HikeService
from Services.ItemService import ItemService

# --- IMPORT ALL GEAR SPECS ---
from AllGear import GEAR_TAG_TO_ITEM_SPEC

# --- CONFIGURATION ---
PBF_FILE = "rhode-island-260101.osm.pbf"
MIN_LENGTH_KM = 3.2

# Initialize Services
hike_repo = HikeRepository()
hike_service = HikeService(hike_repo)
item_repo = ItemRepository()
item_service = ItemService(item_repo)

# Initialize Elevation Data
elevation_data = srtm.get_data()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== GEAR INFERENCE LOGIC ====================

class GearInferenceEngine:
    """Analyzes hike statistics to determine required gear"""
    
    @staticmethod
    def calculate_water(length_km: float, temp_f: float = 70) -> str:
        liters_needed = (length_km / 3.0) * 0.5
        if liters_needed <= 0.5: return "water-bottle-500ml"
        if liters_needed <= 1.0: return "water-bottle-1l"
        if liters_needed <= 2.0: return "hydration-bladder-2l"
        return "hydration-bladder-3l"

    @staticmethod
    def determine_footwear(length_km: float, gain_m: float, difficulty: str) -> str:
        if gain_m > 300 or difficulty in ["DIFFICULT", "EXPERT"]:
            return "hiking-boots"
        if length_km > 15:
            return "hiking-shoes"
        return "trail-runners"

    @staticmethod
    def infer_requirements(hike_id: str, length_km: float, gain_m: float, 
                           max_alt_m: float, difficulty: str, region: str):
        """Returns list of dicts for hike_gear_requirements table"""
        reqs = []

        def add_item(tag, importance="required"):
            reqs.append({
                "gear_tag": tag,
                "importance": importance
            })

        # Essentials (conservative)
        add_item("navigation-map-compass", "required")
        add_item("first-aid-kit-basic", "optional")

        # Water
        water_tag = GearInferenceEngine.calculate_water(length_km)
        add_item(water_tag, "required")

        # Footwear
        footwear_tag = GearInferenceEngine.determine_footwear(length_km, gain_m, difficulty)
        add_item(footwear_tag, "required")

        # Clothing
        add_item("rain-shell", "optional")
        
        if max_alt_m > 1500:
            add_item("puffer-jacket", "required")
            add_item("thermal-base-layer", "required")
        elif region == "Rhode Island" and length_km > 5:
            add_item("bug-spray", "recommended")

        # Technical Gear
        if gain_m > 450:
            add_item("trekking-poles", "recommended")
        
        if max_alt_m > 2500:
            add_item("crampons", "required")
            add_item("ice-axe", "required")

        # Duration-based nutrition & lights
        if length_km > 12:
            add_item("headlamp", "required")
            add_item("power-bank", "optional")
            add_item("food-meal", "required")
        elif length_km > 5:
            add_item("food-snacks", "required")

        return reqs

# ==================== ITEM CREATION & LOOKUP ====================

def ensure_item_exists(gear_tag: str) -> bool:
    """
    Ensures an item exists for the gear tag.
    Creates it if missing, returns True if successful.
    Uses AllGear.GEAR_TAG_TO_ITEM_SPEC as canonical spec.
    """
    if gear_tag not in GEAR_TAG_TO_ITEM_SPEC:
        logger.warning(f"No item spec for gear tag: {gear_tag}")
        return False

    spec = GEAR_TAG_TO_ITEM_SPEC[gear_tag]

    # Check if item already exists (by name)
    try:
        existing = item_service.get_item_by_name(spec["name"])
        if existing:
            return True
    except Exception as e:
        logger.debug(f"ItemRepo lookup failed for {spec['name']}: {e}")
        # Continue and attempt creation — repository may be down; creation will fail cleanly.

    # Create new item conservatively using spec
    try:
        item_id = uuid.uuid4()
        item_type = spec.get("type", "backpack").lower()

        # convert WeatherConditions enum -> value if necessary
        wc = spec.get("weather_conditions", None)
        if hasattr(wc, "name"):
            wc_val = wc
        else:
            wc_val = wc

        if item_type == "backpack":
            item = Backpack(
                id=item_id,
                name=spec["name"],
                weight=spec.get("weight", 0.1),
                cost=spec.get("cost", 0.0),
                capacity_liters=spec.get("capacity_liters", 0.0)
            )
        elif item_type == "shoes":
            # shoes subclass of clothing
            item = Shoes(
                id=item_id,
                name=spec["name"],
                weight=spec.get("weight", 0.1),
                cost=spec.get("cost", 0.0),
                weather_conditions=wc_val,
                crampons=spec.get("crampons", False)
            )
        elif item_type == "clothing":
            item = Clothing(
                id=item_id,
                name=spec["name"],
                weight=spec.get("weight", 0.1),
                cost=spec.get("cost", 0.0),
                weather_conditions=wc_val
            )
        else:
            logger.error(f"Unknown item type: {item_type} for tag {gear_tag}")
            return False

        item_service.create_item(item)
        logger.info(f"Created item: {spec['name']}")
        return True

    except Exception as e:
        logger.error(f"Failed to create item for {gear_tag}: {e}")
        return False

def weight_for_tag(gear_tag: str) -> float:
    """
    Returns weight in kg for a gear tag.
    Priority:
      1) Use AllGear spec weight if present
      2) Attempt to fetch item from DB by name and read its weight
      3) Fallback conservative default (0.1 kg)
    """
    default = 0.1
    spec = GEAR_TAG_TO_ITEM_SPEC.get(gear_tag)
    if spec:
        w = spec.get("weight")
        if isinstance(w, (int, float)) and w >= 0:
            return float(w)
    # Try DB lookup by name
    try:
        if spec and "name" in spec:
            it = item_service.get_item_by_name(spec["name"])
            if it and getattr(it, "weight", None) is not None:
                return float(it.weight)
    except Exception:
        logger.debug(f"DB weight lookup failed for tag {gear_tag}")
    return default

# ==================== HELPERS ====================

def calculate_difficulty(length_km, gain_m):
    miles = length_km * 0.621371
    feet_gain = gain_m * 3.28084
    # simple combined metric used previously
    rating = math.sqrt(2 * miles * feet_gain) if (miles > 0 and feet_gain > 0) else 0
    if rating < 50: return "EASY"
    if rating < 100: return "MODERATE"
    if rating < 150: return "DIFFICULT"
    return "EXPERT"

def estimate_season(max_alt_m):
    if max_alt_m > 2000: return (6, 10)
    return (1, 12)

def get_elevation_stats(coords):
    if not coords: return 0, 0, 0, []
    
    points_with_ele = []
    min_ele = 99999
    max_ele = -99999
    gain = 0
    prev_ele = None

    for lat, lon in coords:
        ele = elevation_data.get_elevation(lat, lon)
        if ele is None:
            ele = 0
            
        points_with_ele.append([lon, lat, ele])
        
        if ele < min_ele: min_ele = ele
        if ele > max_ele: max_ele = ele
        
        if prev_ele is not None:
            diff = ele - prev_ele
            if diff > 0: gain += diff
        prev_ele = ele

    return gain, min_ele, max_ele, points_with_ele

def compute_gear_weight_summary(gear_reqs: List[dict]) -> Tuple[float, float, float]:
    """
    Returns (required_weight, recommended_weight, all_weight) in kg,
    computed conservatively using weight_for_tag().
    Only gear tags that are present in GEAR_TAG_TO_ITEM_SPEC are considered;
    missing tags are logged and given a conservative default weight.
    """
    required = 0.0
    recommended = 0.0
    all_w = 0.0

    for req in gear_reqs:
        tag = req["gear_tag"]
        importance = (req.get("importance") or "required").lower()
        w = weight_for_tag(tag)
        all_w += w
        if importance == "required":
            required += w
        elif importance in ("recommended", "recommended"):
            recommended += w
        else:
            # optional counted in all but not in required/recommended totals
            pass

    return (round(required, 3), round(recommended, 3), round(all_w, 3))

# ==================== THE PROCESSOR ====================

class SimpleTrailHandler(osmium.SimpleHandler):
    def __init__(self):
        super(SimpleTrailHandler, self).__init__()
        self.count = 0
        self.dropped_count = 0
        self.created_gear_tags = set()
    
    def way(self, w):
        # 1. Basic Filter
        if w.tags.get('highway') not in ['path', 'track', 'footway']:
            return
        name = w.tags.get('name')
        if not name:
            return

        # 2. Geometry
        try:
            nodes = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(nodes) < 2:
            return

        # 3. Distance
        total_dist_km = 0.0
        for i in range(len(nodes)-1):
            total_dist_km += geodesic(nodes[i], nodes[i+1]).km

        if total_dist_km < 0.5:
            return

        # 4. Elevation
        gain, min_ele, max_ele, points_3d = get_elevation_stats(nodes)

        # 5. Filtering Logic
        IS_FLAT = gain < 50
        keep_because_long_flat = (IS_FLAT and total_dist_km >= 4)
        keep_because_steep = (gain >= 250)
        keep_because_ri_standard = (total_dist_km > 2.5)

        if not (keep_because_long_flat or keep_because_steep or keep_because_ri_standard):
            self.dropped_count += 1
            return

        # 6. Stats
        difficulty = calculate_difficulty(total_dist_km, gain)
        season_start, season_end = estimate_season(max_ele)
        hike_id = str(uuid.uuid4())
        
        # 7. INFER GEAR REQUIREMENTS
        gear_reqs = GearInferenceEngine.infer_requirements(
            hike_id, total_dist_km, gain, max_ele, difficulty, "Rhode Island"
        )
        
        # 8. ENSURE ALL ITEMS EXIST (uses AllGear spec)
        for req in gear_reqs:
            tag = req['gear_tag']
            if tag not in self.created_gear_tags:
                if ensure_item_exists(tag):
                    self.created_gear_tags.add(tag)

        # 9. COMPUTE GEAR WEIGHT SUMMARY (in kg)
        req_w, rec_w, all_w = compute_gear_weight_summary(gear_reqs)
        logger.info(f"Hike '{name}': required_gear_weight={req_w}kg, recommended={rec_w}kg, total_if_all={all_w}kg")

        # 10. CREATE HIKE VIA SERVICE (attempt to include estimated weight)
        geojson = {"type": "LineString", "coordinates": points_3d}
        
        try:
            # conservative attempt to pass estimated weight into Hike
            hike_kwargs = dict(
                id=uuid.UUID(hike_id),
                source_id=str(w.id),
                name=name,
                geometry=geojson,
                difficulty=DifficultyLevel[difficulty],
                length_km=total_dist_km,
                elevation_gain_m=gain,
                min_altitude_m=min_ele,
                max_altitude_m=max_ele,
                region="Rhode Island",
                season_start_month=season_start,
                season_end_month=season_end,
                permits_required=False,
                required_gear_tags=[r['gear_tag'] for r in gear_reqs],
                last_synced_at=datetime.utcnow()
            )

            # Append estimated weight as an extra kwarg if possible (conservative)
            hike_kwargs['estimated_gear_weight_kg'] = req_w

            # Try to construct Hike with the new field — if dataclass rejects it, fall back.
            try:
                hike = Hike(**hike_kwargs)
            except TypeError:
                # Hike doesn't accept estimated_gear_weight_kg in constructor.
                # Remove it and construct normally; we'll persist the weight separately.
                hike_kwargs.pop('estimated_gear_weight_kg', None)
                hike = Hike(**hike_kwargs)

            # Use service to create hike
            created_hike = hike_service.create_hike(hike)

            # After creation, try to persist estimated weight to the hike record if possible.
            # 1) try service method
            try:
                if hasattr(hike_service, "set_estimated_gear_weight"):
                    hike_service.set_estimated_gear_weight(created_hike.id, req_w)
                else:
                    # 2) Try DB UPDATE (harmless if column doesn't exist)
                    from DBConnection import get_connection
                    with get_connection() as conn:
                        with conn.cursor() as cur:
                            try:
                                cur.execute(
                                    """
                                    UPDATE hikes
                                    SET estimated_gear_weight_kg = %s
                                    WHERE id = %s
                                    """,
                                    (req_w, created_hike.id)
                                )
                                # commit is done by context manager or connection autocommit; adjust as needed
                            except Exception as e:
                                # Column may not exist — that's fine, log and continue.
                                logger.debug(f"Could not update hikes table with estimated weight: {e}")
            except Exception as e:
                logger.debug(f"Failed to persist estimated weight via service or DB: {e}")

            # 11. Create gear requirements in junction table
            from DBConnection import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    for req in gear_reqs:
                        cur.execute(
                            """
                            INSERT INTO hike_gear_requirements (id, hike_id, gear_tag, importance)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (uuid.uuid4(), created_hike.id, req['gear_tag'], req['importance'])
                        )
            
            self.count += 1
            if self.count % 10 == 0:
                logger.info(f"Saved {self.count} hikes...")
                
        except Exception as e:
            logger.error(f"Error saving hike {name}: {e}")

# ==================== MAIN ====================

def main():
    logger.info("Starting ingestion via proper service layer...")
    handler = SimpleTrailHandler()
    handler.apply_file(PBF_FILE, locations=True)
    logger.info(f"Done! Total Hikes Ingested: {handler.count}")
    logger.info(f"Dropped (too short/flat): {handler.dropped_count}")

if __name__ == "__main__":
    main()
