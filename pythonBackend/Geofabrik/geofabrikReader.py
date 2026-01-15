import osmium
import srtm
import math
import uuid
import json
import logging
import sys
from datetime import datetime
from geopy.distance import geodesic
from typing import Tuple, List, Optional

sys.path.append('..')


from PyObjects.Hike import Hike, DifficultyLevel
from PyObjects.Items import Backpack, Clothing, Shoes, WeatherConditions
from Repos.HikeRepo import HikeRepository
from Repos.ItemRepo import ItemRepository
from Services.HikeService import HikeService
from Services.ItemService import ItemService

# --- IMPORT ALL GEAR SPECS (Used for weight lookup only) ---
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

# ==================== COMPLEX GEAR INFERENCE ENGINE ====================

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
    def estimate_duration_hours(length_km: float, gain_m: float) -> float:
        """Naismith's rule approximation"""
        flat_time = length_km / 5.0  # 5 km/hr on flat
        climb_time = gain_m / 600.0  # 600m gain per hour
        return flat_time + climb_time

    @staticmethod
    def is_multiday(length_km: float, duration_hours: float) -> bool:
        """Determine if this is likely a multi-day hike"""
        return length_km > 20 or duration_hours > 10

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

        # Calculate key metrics
        duration_hours = GearInferenceEngine.estimate_duration_hours(length_km, gain_m)
        is_multiday = GearInferenceEngine.is_multiday(length_km, duration_hours)
        is_alpine = max_alt_m > 2000
        is_winter_terrain = max_alt_m > 1500
        is_technical = max_alt_m > 2500
        
        # ==================== BACKPACK ====================
        if is_multiday:
            if length_km > 40 or is_alpine:
                add_item("backpack-expedition-75l", "required")
            else:
                add_item("backpack-multi-50l", "required")
        else:
            add_item("backpack-day-20l", "required")
        
        # ==================== NAVIGATION ====================
        add_item("navigation-map-compass", "required")
        if difficulty in ["DIFFICULT", "EXPERT"]:
            add_item("gps-handheld", "recommended")
        if is_alpine or is_multiday:
            add_item("altimeter-watch", "recommended")
        
        # ==================== HYDRATION ====================
        water_tag = GearInferenceEngine.calculate_water(length_km)
        add_item(water_tag, "required")
        
        if is_multiday:
            add_item("water-filter-squeeze", "required")
            add_item("collapsible-bottle-1l", "recommended")
        elif length_km > 15:
            add_item("purification-tablets", "recommended")
        
        # ==================== FOOTWEAR ====================
        footwear_tag = GearInferenceEngine.determine_footwear(length_km, gain_m, difficulty)
        add_item(footwear_tag, "required")
        
        if is_multiday:
            add_item("camp-slippers", "optional")
        
        # ==================== CLOTHING - BASE & CORE ====================
        add_item("tshirt-synthetic", "required")
        add_item("hiking-pants-convertible", "required")
        add_item("synthetic-underwear", "required")
        
        if length_km > 3:
            add_item("sun-hat", "recommended")
            add_item("sun-hoodie", "optional")
        
        # ==================== CLOTHING - INSULATION ====================
        if is_alpine or is_winter_terrain:
            add_item("thermal-base-layer", "required")
            add_item("puffer-jacket", "required")
            add_item("fleece-midlayer", "recommended")
            add_item("beanie-wool", "required")
            add_item("gloves-insulated", "required")
        elif max_alt_m > 1000 or length_km > 10:
            add_item("fleece-midlayer", "recommended")
            add_item("down-vest", "optional")
            add_item("gloves-liner", "optional")
        
        # ==================== WEATHER PROTECTION ====================
        add_item("rain-shell", "required" if difficulty in ["DIFFICULT", "EXPERT"] else "recommended")
        
        if is_alpine or gain_m > 400:
            add_item("rain-pants", "recommended")
            add_item("hard-shell-alpine", "optional")
        
        if is_winter_terrain:
            add_item("gaiters-tall", "recommended")
        elif gain_m > 200:
            add_item("gaiters-low", "optional")
        
        # ==================== TREKKING SUPPORT ====================
        if gain_m > 400:
            add_item("trekking-poles", "required")
        elif gain_m > 200:
            add_item("trekking-poles", "recommended")
        
        # ==================== TECHNICAL GEAR ====================
        if is_technical:
            add_item("crampons", "required")
            add_item("ice-axe", "required")
            add_item("helmet-climbing", "required")
            add_item("harness", "optional")
            add_item("rope-60m", "optional")
            add_item("carabiner-locking", "recommended")
        elif is_winter_terrain:
            add_item("microspikes", "required")
        
        # Avalanche terrain (high altitude + steep)
        if max_alt_m > 2200 and gain_m > 500:
            add_item("avalanche-beacon", "required")
            add_item("avalanche-probe", "required")
            add_item("avalanche-shovel", "required")
        
        # ==================== LIGHTING ====================
        if duration_hours > 6 or is_multiday:
            add_item("headlamp", "required")
            add_item("extra-batteries-headlamp", "recommended")
        
        # ==================== NUTRITION ====================
        if is_multiday:
            add_item("food-meal", "required")
            add_item("food-snacks", "required")
        elif length_km > 12:
            add_item("food-meal", "required")
            add_item("food-snacks", "required")
        elif length_km > 5:
            add_item("food-snacks", "required")
        
        # ==================== KITCHEN (Multi-day) ====================
        if is_multiday:
            add_item("stove-canister", "required")
            add_item("fuel-canister", "required")
            add_item("cook-pot-titanium", "required")
            add_item("spork", "required")
            add_item("lighter", "required")
            add_item("matches-waterproof", "recommended")
            add_item("pot-lid-press", "optional")
        
        # ==================== SLEEP SYSTEM (Multi-day) ====================
        if is_multiday:
            if is_alpine or is_technical:
                add_item("tent-4season", "required")
                add_item("sleeping-bag-0f", "required")
            else:
                add_item("tent-2p-3season", "required")
                add_item("sleeping-bag-30f", "required")
            
            add_item("sleeping-pad-inflatable", "required")
            add_item("sleeping-pad-foam", "optional")
            add_item("sleeping-bag-liner", "optional")
        
        # ==================== STORAGE & ORGANIZATION ====================
        if is_multiday:
            add_item("stuff-sack-10l", "recommended")
            add_item("dry-bag-20l", "recommended")
            
            if region in ["California", "Colorado", "Wyoming"]:  # Bear country
                add_item("bear-canister", "required")
        
        # ==================== SAFETY & FIRST AID ====================
        if is_alpine or is_multiday or difficulty == "EXPERT":
            add_item("first-aid-kit-mountain", "required")
        else:
            add_item("first-aid-kit-basic", "required")
        
        add_item("whistle", "required")
        add_item("emergency-bivy", "recommended" if difficulty in ["DIFFICULT", "EXPERT"] else "optional")
        
        if is_multiday or is_alpine:
            add_item("satellite-messenger", "recommended")
            add_item("personal-locator-beacon", "optional")
        
        # ==================== TOOLS & REPAIR ====================
        add_item("multi-tool", "recommended" if is_multiday else "optional")
        
        if is_multiday:
            add_item("repair-kit", "recommended")
            add_item("sewing-kit", "optional")
            add_item("trowel", "required")
        
        # ==================== POWER ====================
        if is_multiday:
            add_item("power-bank", "required")
            if length_km > 40:
                add_item("solar-panel-10w", "optional")
        elif duration_hours > 8:
            add_item("power-bank", "recommended")
        
        # ==================== REGION-SPECIFIC ====================
        if region == "Rhode Island":
            if length_km > 3:
                add_item("bug-spray", "recommended")
        
        # Bear spray for known bear regions
        if region in ["Montana", "Wyoming", "Alaska", "Colorado"]:
            add_item("bear-spray", "required")
        
        # ==================== MISCELLANEOUS ====================
        if is_alpine:
            add_item("neck-gaiter-buff", "recommended")
        
        return reqs

# ==================== UTILS AND LOOKUPS ====================

def _normalize_name_for_compare(name: Optional[str]) -> str:
    """Lowercase, trim, and collapse all whitespace for robust comparisons."""
    if not name:
        return ""
    return " ".join(name.lower().strip().split())

def weight_for_tag(gear_tag: str) -> float:
    """
    Returns weight in kg for a gear tag.
    1) Checks AllGear spec (fastest)
    2) Checks DB by Name (slower)
    3) Default 0.1
    """
    default = 0.1
    spec = GEAR_TAG_TO_ITEM_SPEC.get(gear_tag)
    
    # 1) Spec weight
    if spec:
        w = spec.get("weight")
        if isinstance(w, (int, float)) and w >= 0:
            return float(w)

    # 2) Try DB lookup by name (ONLY if it exists, do not create)
    if spec and "name" in spec:
        try:
            it = item_service.get_item_by_name(spec["name"])
            if it and getattr(it, "weight", None) is not None:
                return float(it.weight)
        except Exception:
            pass

    return default

def compute_gear_weight_summary(gear_reqs: List[dict]) -> Tuple[float, float, float]:
    """
    Returns (required_weight, recommended_weight, all_weight) in kg.
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
        elif importance == "recommended":
            recommended += w
        else:
            pass

    return (round(required, 3), round(recommended, 3), round(all_w, 3))

# ==================== GEO SPATIAL UTILS ====================

def get_elevation_stats(coords: List[Tuple[float, float]]) -> Tuple[float, float, float, List[List[float]]]:
    if not coords:
        return 0.0, 0.0, 0.0, []

    points_with_ele = []
    min_ele = float("inf")
    max_ele = float("-inf")
    gain = 0.0
    prev_ele = None

    for lat, lon in coords:
        try:
            ele = elevation_data.get_elevation(lat, lon)
        except Exception:
            ele = None
        if ele is None:
            ele = 0.0

        points_with_ele.append([lon, lat, ele])

        if ele < min_ele: min_ele = ele
        if ele > max_ele: max_ele = ele

        if prev_ele is not None:
            diff = ele - prev_ele
            if diff > 0:
                gain += diff
        prev_ele = ele

    if min_ele == float("inf"): min_ele = 0.0
    if max_ele == float("-inf"): max_ele = 0.0

    return gain, min_ele, max_ele, points_with_ele

def calculate_difficulty(length_km: float, gain_m: float) -> str:
    """
    Returns difficulty label based on a simple combined metric.
    """
    miles = length_km * 0.621371
    feet_gain = gain_m * 3.28084
    rating = math.sqrt(2 * miles * feet_gain) if (miles > 0 and feet_gain > 0) else 0.0
    if rating < 50:
        return "EASY"
    if rating < 100:
        return "MODERATE"
    if rating < 150:
        return "DIFFICULT"
    return "EXPERT"

def estimate_season(max_alt_m: float) -> Tuple[int, int]:
    if max_alt_m > 2000:
        return (6, 10)
    return (1, 12)

# ==================== THE PROCESSOR ====================

class SimpleTrailHandler(osmium.SimpleHandler):
    def __init__(self):
        super(SimpleTrailHandler, self).__init__()
        self.count = 0
        self.dropped_count = 0
    
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

        # 6. Stats & ID
        difficulty = calculate_difficulty(total_dist_km, gain)
        season_start, season_end = estimate_season(max_ele)
        hike_id = str(uuid.uuid4())
        
        # 7. INFER GEAR REQUIREMENTS (Using new logic)
        # Note: We pass "Rhode Island" as the region based on the file name context.
        gear_reqs = GearInferenceEngine.infer_requirements(
            hike_id, total_dist_km, gain, max_ele, difficulty, "Rhode Island"
        )
        
        # NOTE: Creation of items removed. We assume items exist in DB matching the gear_tags.

        # 8. COMPUTE GEAR WEIGHT SUMMARY (in kg)
        req_w, rec_w, all_w = compute_gear_weight_summary(gear_reqs)
        logger.info(f"Hike '{name}' ({difficulty}): dist={round(total_dist_km,1)}km, gain={int(gain)}m, gear_weight={req_w}kg")

        # 9. CREATE HIKE VIA SERVICE
        geojson = {"type": "LineString", "coordinates": points_3d}
        
        try:
            # helper to resolve a gear tag (like "water-bottle-500ml") → item id when possible
            def resolve_gear_tag_to_id(tag: str) -> str:
                # Preferred: use AllGear mapping if present
                spec = GEAR_TAG_TO_ITEM_SPEC.get(tag)
                if spec and spec.get("id"):
                    return spec["id"]
                # Fallback 1: try DB lookup using the tag as a name
                try:
                    it = item_service.get_item_by_name(tag)
                    if it and getattr(it, "id", None):
                        return str(it.id)
                except Exception:
                    pass
                # Fallback 2: if spec exists and has a 'name', try DB lookup by that name
                if spec and "name" in spec:
                    try:
                        it = item_service.get_item_by_name(spec["name"])
                        if it and getattr(it, "id", None):
                            return str(it.id)
                    except Exception:
                        pass
                # Last resort: return the original tag string
                return tag

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
                # Pass the inferred tags here as item IDs (when resolvable) so the Hike object is aware of them
                required_gear_tags=[resolve_gear_tag_to_id(r['gear_tag']) for r in gear_reqs],
                last_synced_at=datetime.utcnow()
            )

            # Try to construct Hike. If 'estimated_gear_weight_kg' is supported, add it.
            hike_kwargs['estimated_gear_weight_kg'] = req_w
            try:
                hike = Hike(**hike_kwargs)
            except TypeError:
                hike_kwargs.pop('estimated_gear_weight_kg', None)
                hike = Hike(**hike_kwargs)

            # Use service to create hike
            created_hike = hike_service.create_hike(hike)

            # Persist estimated weight if the column exists (Update)
            try:
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
                        except Exception as e:
                            logger.debug(f"Could not update hikes table with estimated weight: {e}")
            except Exception as e:
                logger.debug(f"Failed to persist estimated weight DB: {e}")

            # 10. LINK HIKE TO GEAR (Junction Table)
            # We are inserting into the junction table, NOT creating new gear items.
            from DBConnection import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    for req in gear_reqs:
                        try:
                            cur.execute(
                                """
                                INSERT INTO hike_gear_requirements (id, hike_id, gear_tag, importance)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                                """,
                                (uuid.uuid4(), created_hike.id, req['gear_tag'], req['importance'])
                            )
                        except Exception as e:
                            logger.debug(f"Failed to insert gear link for hike {created_hike.id}: {e}")
            
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
