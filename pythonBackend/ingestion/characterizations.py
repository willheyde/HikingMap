import math
from PyObjects.Hike import DifficultyLevel

# ── SAC scale → difficulty ─────────────────────────────────────────────────────

SAC_SCALE_MAP = {
    "hiking":                    DifficultyLevel.EASY,
    "mountain_hiking":           DifficultyLevel.MODERATE,
    "demanding_mountain_hiking": DifficultyLevel.DIFFICULT,
    "alpine_hiking":             DifficultyLevel.EXPERT,
    "demanding_alpine_hiking":   DifficultyLevel.EXPERT,
}

# ── Noise fragments ────────────────────────────────────────────────────────────

SKIP_NAME_FRAGMENTS = {
    "sidewalk", "crosswalk", "connector", "access", "service",
    "driveway", "parking", "road", "street", "avenue", "boulevard",
}

# ── Difficulty ─────────────────────────────────────────────────────────────────

def infer_difficulty(tags: dict) -> DifficultyLevel:
    """Tag-based difficulty — used when OSM sac_scale is present."""
    sac = tags.get("sac_scale")
    return SAC_SCALE_MAP.get(sac, DifficultyLevel.MODERATE)


def calculate_difficulty(length_km: float, gain_m: float) -> DifficultyLevel:
    """
    Shenandoah formula — used for way-based hikes that lack sac_scale tags.
    rating = sqrt(2 * miles * feet_gain)
    """
    miles     = length_km * 0.621371
    feet_gain = gain_m    * 3.28084
    rating    = math.sqrt(2 * miles * feet_gain) if (miles > 0 and feet_gain > 0) else 0.0

    if rating < 50:  return DifficultyLevel.EASY
    if rating < 100: return DifficultyLevel.MODERATE
    if rating < 150: return DifficultyLevel.DIFFICULT
    return DifficultyLevel.EXPERT


# ── Distance / Elevation ───────────────────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R    = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    a    = (math.sin((lat2 - lat1) * math.pi / 360) ** 2
            + math.cos(phi1) * math.cos(phi2)
            * math.sin((lon2 - lon1) * math.pi / 360) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_metrics(points: list) -> tuple[float, float]:
    """
    Returns (distance_m, elevation_gain_m) for relation-based points.
    ele=None is treated as missing data, not sea level.
    """
    distance = 0.0
    gain     = 0.0
    for i in range(1, len(points)):
        p1, p2 = points[i - 1], points[i]
        distance += haversine(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
        if p1["ele"] is not None and p2["ele"] is not None:
            delta = p2["ele"] - p1["ele"]
            if delta > 0:
                gain += delta
    return distance, gain


# ── Season ─────────────────────────────────────────────────────────────────────

def infer_season(tags: dict) -> tuple[int, int]:
    """Tag-based season — used when OSM seasonal tags are present."""
    if tags.get("seasonal") == "yes":
        return 5, 9
    if tags.get("winter_service") == "yes":
        return 1, 12
    return 4, 10


def estimate_season(max_alt_m: float) -> tuple[int, int]:
    """Altitude-based season — used for way-based hikes without seasonal tags."""
    if max_alt_m > 2000:
        return 6, 10
    return 1, 12    # Rhode Island — year-round


# ── Permits ────────────────────────────────────────────────────────────────────

def infer_permits_required(tags: dict) -> bool:
    """
    Best-effort permit detection from OSM tags.
    OSM permit data is sparse — this catches explicit tagging only.
    False negatives are expected. Recreation.gov API cross-reference
    is the long-term fix for US federal trails.
    """
    access = tags.get("access", "")
    return (
        access in {"permit", "private"}
        or tags.get("fee")    in {"yes", "required"}
        or tags.get("permit") in {"yes", "required"}
    )


# ── Tags ───────────────────────────────────────────────────────────────────────

def derive_tags(
    length_km:          float,
    elevation_gain_m:   float,
    max_altitude_m:     float,
    season_start_month: int,
    season_end_month:   int,
    permits_required:   bool,
) -> list[str]:
    """
    Deterministic tags derived entirely from computed hike metrics.
    Stored in tags[] for fast GIN-indexed filtering by HikeSearchService.

    Not included here (have dedicated columns, query those directly):
        - difficulty  → hikes.difficulty
        - region      → hikes.region

    Not included here (require Overpass enrichment, added post-ingest):
        - waterfall, lake, summit, canyon, ridge, etc.
        - can_camp  → hikes.can_camp (separate boolean column)
    """
    tags: set[str] = set()

    # ── Duration bucket ────────────────────────────────────────────────────────
    # Thresholds tuned for typical day-use hiking, not trail running.
    if length_km < 5:
        tags.add("short")        # < 5 km  — under 2 hrs
    elif length_km < 10:
        tags.add("half_day")     # 5–10 km — 2–4 hrs
    elif length_km <= 25:
        tags.add("full_day")     # 10–25 km — most day hikes
    elif length_km <= 50:
        tags.add("overnight")    # 25–50 km — one camp stop
    else:
        tags.add("multi_day")    # 50+ km   — multiple nights

    # ── Elevation gain tier ────────────────────────────────────────────────────
    if elevation_gain_m < 100:
        tags.add("flat")
    elif elevation_gain_m < 400:
        tags.add("gentle_gain")
    elif elevation_gain_m < 800:
        tags.add("moderate_gain")
    elif elevation_gain_m < 1500:
        tags.add("high_gain")
    else:
        tags.add("very_high_gain")

    # ── Altitude / terrain tier ────────────────────────────────────────────────
    # Useful for prompt matching: "alpine hike", "high altitude route", etc.
    if max_altitude_m < 500:
        tags.add("lowland")
    elif max_altitude_m < 1500:
        tags.add("montane")
    elif max_altitude_m < 2500:
        tags.add("subalpine")
    else:
        tags.add("alpine")

    # ── Season type ────────────────────────────────────────────────────────────
    span = season_end_month - season_start_month
    if span >= 11:
        tags.add("year_round")
    elif season_start_month >= 6 and season_end_month <= 9:
        tags.add("summer_only")
    elif season_start_month <= 4 and season_end_month >= 10:
        tags.add("spring_fall")
    else:
        tags.add("seasonal")

    # ── Permits ────────────────────────────────────────────────────────────────
    if permits_required:
        tags.add("permits_required")

    return sorted(tags)


# ── Required gear (category level) ────────────────────────────────────────────
# Returns category keys matching REQUIRED_GEAR in TripInputParser.
# Used by trip planner gap analysis.

def infer_required_gear(tags: dict, difficulty: DifficultyLevel) -> list[str]:
    gear: set[str] = set()
    surface = tags.get("surface", "")
    sac     = tags.get("sac_scale", "")

    if surface in {"rock", "scree", "gravel"} or sac in {
        "mountain_hiking", "demanding_mountain_hiking",
        "alpine_hiking", "demanding_alpine_hiking",
    }:
        gear.add("footwear")

    if sac in {"alpine_hiking", "demanding_alpine_hiking"}:
        gear.add("technical")
        gear.add("navigation")
        gear.add("safety")

    if difficulty in {DifficultyLevel.DIFFICULT, DifficultyLevel.EXPERT}:
        gear.add("navigation")
        gear.add("safety")

    if sac in {"demanding_mountain_hiking", "alpine_hiking", "demanding_alpine_hiking"}:
        gear.add("trekking_poles")

    if tags.get("winter_service") == "no":
        gear.add("clothing")

    return sorted(gear)


# ── Region ─────────────────────────────────────────────────────────────────────

REGIONS = [
    # North America
    ((35, 43),   (-84, -67),    "Appalachian Mountains"),
    ((36, 42),   (-107, -103),  "Rocky Mountains (Colorado)"),
    ((43, 49),   (-117, -113),  "Rocky Mountains (Northern)"),
    ((36, 42),   (-122, -118),  "Sierra Nevada"),
    ((44, 49),   (-124, -121),  "Cascade Range"),
    ((33, 37),   (-118, -115),  "Southern California Mountains"),
    ((35, 37),   (-113, -111),  "Colorado Plateau"),
    ((58, 65),   (-152, -148),  "Alaska Range"),
    ((60, 70),   (-141, -130),  "Yukon / Northern Rockies"),
    ((45, 49),   (-80, -74),    "Adirondacks / Laurentians"),
    # Europe
    ((43, 48),   (6, 16),       "Alps"),
    ((42, 43.5), (-2, 3),       "Pyrenees"),
    ((46, 47),   (11, 12.5),    "Dolomites"),
    ((56, 59),   (-6, -1),      "Scottish Highlands"),
    ((60, 71),   (5, 30),       "Scandinavian Mountains"),
    ((37, 41),   (28, 45),      "Anatolian Highlands"),
    ((42, 44),   (42, 47),      "Caucasus"),
    ((40, 43),   (20, 28),      "Balkans"),
    # South America
    ((-55, -40), (-76, -68),    "Patagonia"),
    ((-18, -8),  (-78, -68),    "Andes (Central)"),
    ((-5, 5),    (-78, -72),    "Andes (Northern)"),
    # Asia
    ((26, 36),   (70, 96),      "Himalayas"),
    ((25, 35),   (99, 105),     "Yunnan Highlands"),
    ((37, 42),   (67, 80),      "Tian Shan"),
    # Africa
    ((-4, 5),    (28, 40),      "East African Rift"),
    ((-35, -30), (18, 26),      "Drakensberg"),
    # Oceania
    ((-44, -41), (167, 172),    "New Zealand Southern Alps"),
    ((-37, -36), (148, 148.5),  "Australian Alps"),
]


def infer_region(lat: float, lon: float) -> str:
    for (lat_min, lat_max), (lon_min, lon_max), name in REGIONS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return "Unknown Region"


# ── Validation ─────────────────────────────────────────────────────────────────

MIN_DISTANCE_M = 2000   # 1 mile
MIN_GAIN_M     = 10


def is_valid_hike(distance_m: float, elevation_gain_m: float) -> bool:
    return distance_m >= MIN_DISTANCE_M and elevation_gain_m >= MIN_GAIN_M


def is_noise(name: str, tags: dict) -> bool:
    lower = name.lower()
    if any(frag in lower for frag in SKIP_NAME_FRAGMENTS):
        return True
    if tags.get("highway") in {"residential", "unclassified", "tertiary"}:
        return True
    return False