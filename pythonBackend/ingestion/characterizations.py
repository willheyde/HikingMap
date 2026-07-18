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

# "connector" and "access" were removed — they match legitimate trail names
# (greenway connectors, access spurs) and were dropping real hikes. What remains
# is unambiguous road/pavement noise.
SKIP_NAME_FRAGMENTS = {
    "sidewalk", "crosswalk", "service",
    "driveway", "parking", "road", "street", "avenue", "boulevard",
}

# Planned / unbuilt trails: OSM mappers label these "Future - <name>",
# "Proposed <name>", "Construction <name>". They aren't walkable and were leaking
# into results verbatim (e.g. "Future - High Knob Trail"). Matched as a name
# PREFIX (not substring) so a legitimately-named trail isn't dropped.
SKIP_NAME_PREFIXES = ("future ", "future-", "future -", "proposed ", "construction ")

# ── Difficulty ─────────────────────────────────────────────────────────────────

def infer_difficulty(tags: dict) -> DifficultyLevel:
    """Tag-based difficulty — used when OSM sac_scale is present."""
    sac = tags.get("sac_scale")
    return SAC_SCALE_MAP.get(sac, DifficultyLevel.MODERATE)


# Shenandoah rating tier cutoffs. Retuned looser than canonical (50/100/150) to
# remove the systematic over-rating QA found. SINGLE SOURCE OF TRUTH — imported
# by backfill_difficulty.py as its CLI defaults so ingest and the backfill agree.
RATING_EASY_MAX      = 50.0
RATING_MODERATE_MAX  = 110.0
RATING_DIFFICULT_MAX = 210.0

# Grade (metres of gain per km) thresholds for the average-person "feel"
# adjustment that the length×gain rating can't see:
#   * A genuinely FLAT trail is an endurance walk, not a hard hike, so it's
#     capped at Moderate however long it is — a 71 km / 400 m rail-trail (grade
#     ~6) is NOT "Expert".
#   * A short, STEEP grind feels harder than its modest length×gain rating (a
#     300 m wall in 2 km rates "Easy"), so it's bumped one tier.
FLAT_GRADE_M_PER_KM  = 25.0
STEEP_GRADE_M_PER_KM = 80.0


def apply_grade_feel(
    diff: DifficultyLevel,
    length_km: float,
    gain_m: float,
    flat_grade: float = FLAT_GRADE_M_PER_KM,
    steep_grade: float = STEEP_GRADE_M_PER_KM,
) -> DifficultyLevel:
    """Adjust a length×gain difficulty for GRADE (steepness) so it matches how a
    hike actually feels. Flat → cap at Moderate; steep → bump one tier. Leaves
    mid-grade trails (where distance and gain correlate) untouched."""
    if length_km <= 0 or gain_m <= 0:
        return diff
    grade = gain_m / length_km
    if grade < flat_grade and diff.value > DifficultyLevel.MODERATE.value:
        return DifficultyLevel.MODERATE
    if grade >= steep_grade and diff.value < DifficultyLevel.EXPERT.value:
        return DifficultyLevel(diff.value + 1)
    return diff


# new
def calculate_difficulty(
    length_km: float,
    gain_m: float,
    tags: dict | None = None,
) -> DifficultyLevel:
    """
    Assigns difficulty. Precedence:
      1. OSM sac_scale tag, when present and recognized — most authoritative,
         since it captures technical difficulty (exposure, scrambling,
         rooty/rocky terrain) that gain/distance alone can't see.
      2. Otherwise, the Shenandoah formula: rating = sqrt(2 * miles * feet_gain)
    """
    sac = (tags or {}).get("sac_scale")
    if sac in SAC_SCALE_MAP:
        return SAC_SCALE_MAP[sac]

    miles     = length_km * 0.621371
    feet_gain = gain_m    * 3.28084
    rating    = math.sqrt(2 * miles * feet_gain) if (miles > 0 and feet_gain > 0) else 0.0

    if   rating < RATING_EASY_MAX:      base = DifficultyLevel.EASY
    elif rating < RATING_MODERATE_MAX:  base = DifficultyLevel.MODERATE
    elif rating < RATING_DIFFICULT_MAX: base = DifficultyLevel.DIFFICULT
    else:                               base = DifficultyLevel.EXPERT
    # Grade-feel correction (flat→cap Moderate, steep→bump) so a flat rail-trail
    # isn't "Expert" and a short wall isn't "Easy". sac_scale (returned above)
    # is authoritative and deliberately NOT adjusted.
    return apply_grade_feel(base, length_km, gain_m)


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


# ── Trail shape / out-and-back correction ───────────────────────────────────────

# Endpoints closer together than this (great-circle metres) are treated as the
# same point, so the trail is a closed LOOP whose stored geometry already spans
# the full walk. Farther apart, the trail is OPEN and — in a regional day-hike
# dataset whose OSM relations carry no `roundtrip`/`distance` tags — is
# overwhelmingly an out-and-back, whose geometry OSM stores ONCE (trailhead →
# turnaround) and which therefore reads at ~half its real round-trip length.
LOOP_CLOSE_M = 50.0

TRAIL_SHAPE_LOOP         = "loop"
TRAIL_SHAPE_OUT_AND_BACK = "out_and_back"
# Assigned by the distance backfill (not by ingest) to a row it can't classify
# from geometry — a degenerate/empty coordinate list. Stamped rather than left
# NULL so the row is not re-scanned on every future run; length is left as-is.
TRAIL_SHAPE_UNKNOWN      = "unknown"
# A long OPEN trail whose stored one-way length already exceeds
# MAX_OUT_AND_BACK_ONEWAY_KM. Doubling it (endpoint gap can't tell an
# out-and-back from a thru-trail, so open defaults to out-and-back) would turn a
# genuine linear thru-trail segment (AT / MST / PCT — the MST already reads
# 49 km) into an absurd ~2× figure. Above the threshold a real out-and-back
# (>50 km round trip) is far rarer than a linear corridor, so we DON'T double:
# stamp this, leave length as-is, and let a human confirm if needed.
TRAIL_SHAPE_POINT_TO_POINT = "point_to_point"
# Stored one-way km above which an OPEN trail is treated as linear, not doubled.
MAX_OUT_AND_BACK_ONEWAY_KM = 25.0


def classify_trail_shape(
    first_lat: float, first_lon: float,
    last_lat:  float, last_lon:  float,
) -> str:
    """
    Loop vs. out-and-back from the geometry's endpoints alone. Returns
    TRAIL_SHAPE_LOOP when start ≈ end (within LOOP_CLOSE_M), else
    TRAIL_SHAPE_OUT_AND_BACK.

    Deliberately no 'point_to_point' class: telling a genuine thru/shuttle hike
    apart from an out-and-back needs OSM `roundtrip`/`distance` tags the RI/NC
    relations don't carry. Defaulting every open trail to out-and-back only
    over-doubles the rare point-to-point — the accepted trade (an easy loop is
    never overshot; long out-and-backs get fixed).
    """
    gap_m = haversine(first_lat, first_lon, last_lat, last_lon)
    return TRAIL_SHAPE_LOOP if gap_m <= LOOP_CLOSE_M else TRAIL_SHAPE_OUT_AND_BACK


# ── Length-bucket tag ────────────────────────────────────────────────────────────

# The single duration tag derive_tags() assigns from length. Isolated here so the
# distance backfill can swap ONLY this tag when it doubles an out-and-back —
# without regenerating (and thereby clobbering) the Overpass-enrichment feature
# tags (waterfall, lake, summit, …) that land on the row post-ingest.
LENGTH_BUCKET_TAGS = ("short", "half_day", "full_day", "overnight", "multi_day")


def length_bucket_tag(length_km: float) -> str:
    if length_km < 5:    return "short"        # < 5 km   — under 2 hrs
    if length_km < 10:   return "half_day"     # 5–10 km  — 2–4 hrs
    if length_km <= 25:  return "full_day"     # 10–25 km — most day hikes
    if length_km <= 50:  return "overnight"    # 25–50 km — one camp stop
    return "multi_day"                         # 50+ km   — multiple nights


# ── Elevation-gain-tier tag ───────────────────────────────────────────────────

# The single gain-tier tag derive_tags() assigns from elevation gain. Isolated
# here (like LENGTH_BUCKET_TAGS) so the elevation/difficulty backfills can swap
# ONLY this tag when gain is corrected — without regenerating and thereby
# clobbering the Overpass-enrichment feature tags (waterfall, lake, summit, …)
# or provenance markers (overpass_enriched, dem_elevation) on the row.
GAIN_TIER_TAGS = ("flat", "gentle_gain", "moderate_gain", "high_gain", "very_high_gain")


def gain_tier_tag(elevation_gain_m: float) -> str:
    if elevation_gain_m < 100:   return "flat"
    if elevation_gain_m < 400:   return "gentle_gain"
    if elevation_gain_m < 800:   return "moderate_gain"
    if elevation_gain_m < 1500:  return "high_gain"
    return "very_high_gain"


# ── Season ─────────────────────────────────────────────────────────────────────

def infer_season(tags: dict) -> tuple[int, int]:
    """Tag-based season — used when OSM seasonal tags are present."""
    if tags.get("seasonal") == "yes":
        return 5, 9
    if tags.get("winter_service") == "yes":
        return 1, 12
    return 4, 10


# ── Season ─────────────────────────────────────────────────────────────────────

def estimate_season(max_alt_m: float) -> tuple[int, int]:
    """
    NC-tuned altitude-based season estimation.

    > 1,800 m  — High peaks (Mt. Mitchell, Black Mountains):
                 significant snow Nov–Apr, accessible May–Oct only.
    900–1,800 m — Blue Ridge mid-elevation (Roan Highlands, Max Patch area):
                 passable March–November, occasional winter closures.
    < 900 m    — Piedmont, foothills, Uwharries, coastal plain:
                 year-round accessible.
    """
    if max_alt_m > 1800:
        return 5, 10    # High peaks
    if max_alt_m > 900:
        return 3, 11    # Mid-elevation Blue Ridge
    return 1, 12        # Piedmont / foothills / coast


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

# FIX: removed `from distro import name` which shadowed the `name` parameter.
# FIX: added `name: str = ""` to the signature — ingest.py already passes it.

NAME_TAG_MAP: dict[str, list[str]] = {
    "ridge": ["ridge", "ledge", "bluff"],
}


def derive_tags(
    length_km:          float,
    elevation_gain_m:   float,
    max_altitude_m:     float,
    season_start_month: int,
    season_end_month:   int,
    permits_required:   bool,
    name:               str = "",   # ← FIX: was missing; `name` usage below was
                                    #   silently reading the `distro` module import
) -> list[str]:
    """
    Deterministic tags derived from computed hike metrics + trail name.
    Stored in tags[] for fast GIN-indexed filtering by HikeSearchService.

    Not included here (have dedicated columns):
        difficulty  → hikes.difficulty
        region      → hikes.region

    NNot included here (added by overpass_enrichment.py post-ingest, and
    superseded there if a later Overpass query disagrees — see
    VERIFIABLE_TAGS): waterfall, lake, summit, river, viewpoint, meadow,
    cave, historic.
        can_camp  → hikes.can_camp (separate boolean column)
    "ridge" and "canyon" have no Overpass detector yet, so they're not
    covered by either mechanism — ridge still comes from name inference
    below; canyon isn't detected at all currently.
    """
    tags: set[str] = set()

    # ── Duration bucket ────────────────────────────────────────────────────────
    tags.add(length_bucket_tag(length_km))

    # ── Elevation gain tier ────────────────────────────────────────────────────
    tags.add(gain_tier_tag(elevation_gain_m))

    # ── Altitude / terrain tier ────────────────────────────────────────────────
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

    # ── Name inference ─────────────────────────────────────────────────────────
    # Only "ridge" is inferred from the name — everything else that used to
    # be here is now Overpass-only (see NAME_TAG_MAP comment above).
    name_lower = name.lower()
    for tag, keywords in NAME_TAG_MAP.items():
        if any(kw in name_lower for kw in keywords):
            tags.add(tag)

    return sorted(tags)


# ── Required gear (category level) ────────────────────────────────────────────

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
    ((41.0, 42.1), (-72.0, -71.0),  "Southern New England"),
    ((42.0, 43.5), (-73.5, -69.8),  "New England Coast"),
    ((43.5, 47.5), (-71.5, -67.0),  "Northern New England"),
    ((35, 43),     (-84, -67),       "Appalachian Mountains"),
    ((36, 42),     (-107, -103),     "Rocky Mountains (Colorado)"),
    ((43, 49),     (-117, -113),     "Rocky Mountains (Northern)"),
    ((36, 42),     (-122, -118),     "Sierra Nevada"),
    ((44, 49),     (-124, -121),     "Cascade Range"),
    ((33, 37),     (-118, -115),     "Southern California Mountains"),
    ((35, 37),     (-113, -111),     "Colorado Plateau"),
    ((58, 65),     (-152, -148),     "Alaska Range"),
    ((60, 70),     (-141, -130),     "Yukon / Northern Rockies"),
    ((45, 49),     (-80, -74),       "Adirondacks / Laurentians"),
    # Europe
    ((43, 48),     (6, 16),          "Alps"),
    ((42, 43.5),   (-2, 3),          "Pyrenees"),
    ((46, 47),     (11, 12.5),       "Dolomites"),
    ((56, 59),     (-6, -1),         "Scottish Highlands"),
    ((60, 71),     (5, 30),          "Scandinavian Mountains"),
    ((37, 41),     (28, 45),         "Anatolian Highlands"),
    ((42, 44),     (42, 47),         "Caucasus"),
    ((40, 43),     (20, 28),         "Balkans"),
    # South America
    ((-55, -40),   (-76, -68),       "Patagonia"),
    ((-18, -8),    (-78, -68),       "Andes (Central)"),
    ((-5, 5),      (-78, -72),       "Andes (Northern)"),
    # Asia
    ((26, 36),     (70, 96),         "Himalayas"),
    ((25, 35),     (99, 105),        "Yunnan Highlands"),
    ((37, 42),     (67, 80),         "Tian Shan"),
    # Africa
    ((-4, 5),      (28, 40),         "East African Rift"),
    ((-35, -30),   (18, 26),         "Drakensberg"),
    # Oceania
    ((-44, -41),   (167, 172),       "New Zealand Southern Alps"),
    ((-37, -36),   (148, 148.5),     "Australian Alps"),
]


def infer_region(lat: float, lon: float) -> str:
    for (lat_min, lat_max), (lon_min, lon_max), region_name in REGIONS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return region_name
    return "Unknown Region"
# ── State (US) ─────────────────────────────────────────────────────────────────

# Approximate bounding boxes for US state assignment.
# Ordered smallest-area first so tighter boxes win on border ambiguities.
US_STATE_BOUNDS: list[tuple[float, float, float, float, str]] = [
    (41.15, 42.02, -71.89, -71.12, "RI"),
    (38.45, 39.84, -75.79, -75.05, "DE"),
    (38.93, 41.36, -75.56, -73.89, "NJ"),
    (40.98, 42.05, -73.73, -71.79, "CT"),
    (42.70, 45.31, -72.56, -70.60, "NH"),
    (42.73, 45.02, -73.43, -71.50, "VT"),
    (37.20, 40.64, -82.64, -77.72, "WV"),
    (37.91, 39.72, -79.49, -75.05, "MD"),
    (36.54, 39.46, -83.68, -75.24, "VA"),
    (39.72, 42.27, -80.52, -74.69, "PA"),
    (38.40, 41.98, -84.82, -80.52, "OH"),
    (37.77, 41.76, -88.10, -84.79, "IN"),
    (33.84, 36.59, -84.32, -75.46, "NC"),
    (32.05, 35.22, -83.35, -78.54, "SC"),
    (34.98, 36.68, -90.31, -81.65, "TN"),
    (36.49, 39.15, -89.57, -81.97, "KY"),
    (30.36, 35.00, -85.61, -80.84, "GA"),
    (30.14, 35.00, -88.47, -84.89, "AL"),
    (24.52, 31.00, -87.63, -80.03, "FL"),
    (28.93, 33.02, -94.04, -88.82, "LA"),
    (30.17, 35.01, -91.66, -88.10, "MS"),
    (36.97, 42.51, -91.51, -87.02, "IL"),
    (40.38, 43.50, -96.64, -90.14, "IA"),
    (33.00, 36.50, -94.62, -89.64, "AR"),
    (35.99, 40.61, -95.77, -89.10, "MO"),
    (42.49, 47.31, -92.89, -86.25, "WI"),
    (41.70, 48.30, -90.42, -82.41, "MI"),
    (43.50, 49.38, -97.24, -89.49, "MN"),
    (36.97, 40.00, -102.05, -94.59, "KS"),
    (33.62, 37.00, -103.00, -94.43, "OK"),
    (25.84, 36.50, -106.65, -93.51, "TX"),
    (39.99, 43.00, -104.05, -95.31, "NE"),
    (42.48, 45.94, -104.06, -96.44, "SD"),
    (45.94, 49.00, -104.05, -96.55, "ND"),
    (40.99, 45.01, -111.05, -104.05, "WY"),
    (36.99, 41.00, -109.05, -102.04, "CO"),
    (44.36, 49.00, -116.05, -104.04, "MT"),
    (41.99, 49.00, -117.24, -111.04, "ID"),
    (41.24, 42.89, -73.50, -69.93, "MA"),
    (40.50, 45.01, -79.76, -71.86, "NY"),
    (43.06, 47.46, -71.08, -66.97, "ME"),
    (36.99, 42.00, -120.01, -114.04, "NV"),
    (36.99, 42.00, -114.05, -109.04, "UT"),
    (31.33, 37.00, -114.82, -109.04, "AZ"),
    (31.33, 37.00, -109.05, -103.00, "NM"),
    (41.99, 49.00, -124.73, -116.92, "WA"),
    (41.99, 46.24, -124.57, -116.46, "OR"),
    (32.53, 42.01, -124.41, -114.13, "CA"),
]


def infer_state(lat: float, lon: float) -> str:
    """
    Returns the US state name for a trailhead coordinate using bounding boxes.
    Falls back to 'Unknown' for non-US locations or unmatched coordinates.
    Border ambiguity is rare in practice — trailheads are almost always
    well within a single state's bounds.
    """
    for lat_min, lat_max, lon_min, lon_max, state in US_STATE_BOUNDS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return state
    return "Unknown"

# ── Data-quality sanity checks ──────────────────────────────────────────────

# A generous ceiling for *sustained* average grade — real trails can hit
# this on short, brutal sections, but not averaged over multiple miles.
# This catches the "duplicated/summed segments" failure mode on a per-record
# basis regardless of what caused it.
MAX_PLAUSIBLE_GRADE_FT_PER_MI = 1500

# Tags describing unambiguously flat/gentle terrain — should never coexist
# with a Difficult/Expert difficulty or a high-gain tag on the same record.
FLAT_TAGS = {"flat", "gentle_gain"}
HIGH_GAIN_TAGS    = {"high_gain", "very_high_gain"}
HARD_DIFFICULTIES = {DifficultyLevel.DIFFICULT, DifficultyLevel.EXPERT}


def find_data_quality_issues(
    length_km:        float,
    elevation_gain_m: float,
    difficulty:       DifficultyLevel,
    tags:             list[str] | None,
) -> list[str]:
    """
    Same-record consistency / plausibility checks. Run at ingest time and
    post-merge so bad records get caught before they land in prod instead
    of waiting on the next manual QA pass.

    Note: the grade check alone won't catch every implausible record (e.g.
    a trail averaging ~170 ft/mi over 40+ miles isn't extreme in isolation)
    — that's what the tag-consistency check is for: it catches gain figures
    that are impossible GIVEN the record's own terrain classification, even
    when the raw grade looks unremarkable.

    Returns a list of human-readable issues; empty = looks consistent.
    Callers decide whether to reject, auto-correct, or just log.
    """
    issues: list[str] = []
    tagset = set(tags or [])

    miles = length_km * 0.621371
    if miles > 0:
        grade_ft_mi = (elevation_gain_m * 3.28084) / miles
        if grade_ft_mi > MAX_PLAUSIBLE_GRADE_FT_PER_MI:
            issues.append(
                f"implausible grade: {grade_ft_mi:.0f} ft/mi over {miles:.1f} mi "
                f"(max plausible ~{MAX_PLAUSIBLE_GRADE_FT_PER_MI} ft/mi)"
            )

    flat_hit = tagset & FLAT_TAGS
    if flat_hit and difficulty in HARD_DIFFICULTIES:
        issues.append(f"tag/difficulty contradiction: {sorted(flat_hit)} + {difficulty}")
    if flat_hit and (tagset & HIGH_GAIN_TAGS):
        issues.append(f"tag/tag contradiction: {sorted(flat_hit)} + {sorted(tagset & HIGH_GAIN_TAGS)}")

    return issues
# ── Validation ─────────────────────────────────────────────────────────────────

MIN_DISTANCE_M = 400   # 1/4 a mile
MIN_GAIN_M     = 10


def is_valid_hike(distance_m: float, elevation_gain_m: float) -> bool:
    return distance_m >= MIN_DISTANCE_M and elevation_gain_m >= MIN_GAIN_M


def is_noise(name: str, tags: dict) -> bool:
    lower = name.lower().strip()
    if lower.startswith(SKIP_NAME_PREFIXES):
        return True
    if any(frag in lower for frag in SKIP_NAME_FRAGMENTS):
        return True
    if tags.get("highway") in {"residential", "unclassified", "tertiary",
                               "proposed", "construction"}:
        return True
    return False