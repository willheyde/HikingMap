"""
ingestion/overpass_enrichment.py

Post-ingest enrichment pass that queries the Overpass API for natural and
man-made features within a short distance of each hike's trail line (via
Overpass `around:`), then patches `tags[]` and `can_camp` on every hike
record in the database.

Concurrency model
─────────────────
A ThreadPoolExecutor runs N worker threads simultaneously.  Each worker
calls Overpass independently — but all share a single RateLimiter that
serialises the *gap between requests*, guaranteeing at least `sleep_s`
seconds between any two API calls regardless of worker count.

This eliminates the response-latency dead time of the sequential version:
while thread A is waiting on Overpass, threads B/C are already mid-flight.
Throughput is still bounded by the rate limit (1 req / sleep_s), but
wall-clock time drops by ~(latency / sleep_s) × 100 %.

Each worker uses a thread-local HikeService/HikeRepository so DB
connections are never shared across threads.  This requires HikeRepository
to open its own connection — it must NOT rely on a module-level shared conn.

Usage (from project root):
    python ingestion/overpass_enrichment.py
    python ingestion/overpass_enrichment.py --batch 200 --workers 4 --sleep 1.5
    python ingestion/overpass_enrichment.py --force --dry-run

Options:
    --batch   N    Process at most N pending hikes this run (default: all)
    --workers N    Concurrent Overpass threads (default: 3, max recommended: 5)
    --sleep   S    Minimum seconds between any two API calls (default: 1.5)
    --force        Re-enrich hikes already marked overpass_enriched
    --dry-run      Query Overpass and log results but skip all DB writes
"""

import sys
import time
import math
import logging
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

sys.path.append(str(Path(__file__).parent.parent))

from Repos.HikeRepo import HikeRepository
from Services.HikeService import HikeService

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

OVERPASS_URL     = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT  = 35          # HTTP socket timeout — slightly above Overpass timeout
OVERPASS_TIMEOUT = 30          # [timeout:N] value embedded in QL query
MAX_RETRIES      = 3
RETRY_BACKOFF    = 6.0         # initial back-off seconds; doubles on each retry
BBOX_BUFFER_DEG  = 0.009       # ≈ 1 km padding added to every side of trail bbox

# Proximity filtering. `around:` tests the trail LINE server-side, so a feature
# is only returned when the trail actually passes within this many metres of it
# — replacing the old "anywhere in the trail's bounding box" test that let a
# stream 1 km away in the bbox corner tag a hike as `river`. Containment
# features (protected areas / nature reserves) stay on the bbox test instead —
# a trail deep inside a reserve is nowhere near its boundary line.
TRAIL_PROXIMITY_M = 75         # around-radius (m) for proximity features
_COORD_MIN_GAP_M  = 60.0       # decimate trail to ~this spacing before building the polyline
_COORD_MAX_POINTS = 200        # hard cap on polyline vertices (keeps the QL body small)

MARKER_TAG = "overpass_enriched"

# ── Thread-local DB connections ────────────────────────────────────────────────

_thread_local = threading.local()


def _thread_service() -> HikeService:
    """
    Returns a per-thread HikeService, lazily instantiating one on first access.
    Keeps DB connections off the main thread and avoids sharing a single
    connection across workers.

    Precondition: HikeRepository() must open its own connection — do NOT use
    this pattern if your repo relies on a shared module-level connection object.
    """
    if not hasattr(_thread_local, "service"):
        _thread_local.service = HikeService(HikeRepository())
    return _thread_local.service


# ── Rate limiter ───────────────────────────────────────────────────────────────

class _RateLimiter:
    """
    Thread-safe rate limiter.

    Serialises Overpass requests across all worker threads by enforcing a
    minimum gap of `interval` seconds between consecutive acquire() calls.
    Workers block inside acquire() rather than sleeping after the call,
    which lets them immediately start the HTTP request once the gap expires.
    """

    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._lock     = threading.Lock()
        self._last_ts  = 0.0          # monotonic timestamp of last release

    def acquire(self) -> None:
        with self._lock:
            gap = self._interval - (time.monotonic() - self._last_ts)
            if gap > 0:
                time.sleep(gap)
            self._last_ts = time.monotonic()


# ── Feature detectors ──────────────────────────────────────────────────────────

ElementTags = dict[str, str]
Predicate   = Callable[[ElementTags], bool]

DETECTORS: list[tuple[str, Predicate]] = [

    # ── Waterfalls ─────────────────────────────────────────────────────────────
    # Covers: OSM primary tag, waterway=waterfall (alt tag), weirs/dams
    # (RI mill dam spillways were the original motivation for weir/dam).
    # BUG FIX: previous version checked waterway=weir|dam in the detector but
    # never requested those waterway values from Overpass. Query now matches.
    (
        "waterfall",
        lambda t: (
            t.get("natural") == "waterfall"
            or t.get("waterway") in {"waterfall", "weir", "dam"}
            or t.get("man_made") == "weir"
        ),
    ),

    # ── Summits ────────────────────────────────────────────────────────────────
    ("summit",     lambda t: t.get("natural") in {"peak", "volcano"}),

    # ── Standing water ─────────────────────────────────────────────────────────
    # Requires an EXPLICIT water=* subtag naming a standing-water body. A bare
    # `natural=water` (no subtag) is NOT assumed to be a lake — that default was
    # over-tagging riverbank/greenway polygons (which OSM often maps as bare
    # `natural=water` or `water=river`) as lakes. A `natural=water` + `water=river`
    # polygon matches neither this detector nor the waterway detectors below
    # (those key off `waterway`, not `water`), so it is intentionally dropped.
    (
        "lake",
        lambda t: (
            t.get("natural") == "water"
            and t.get("water") in {"lake", "reservoir", "pond", "lagoon"}
        ),
    ),

    # ── Moving water ───────────────────────────────────────────────────────────
    # `river` and `stream` are separate tags. Streams are by far the densest
    # waterway in mountain terrain, so folding them into `river` made `river`
    # fire on ~every trail; keeping them apart lets `river` mean an actual river
    # (waterway=river|canal) while a nearby creek gets the distinct `stream` tag.
    ("river",      lambda t: t.get("waterway") in {"river", "canal"}),
    ("stream",     lambda t: t.get("waterway") == "stream"),

    # ── Springs / water sources ────────────────────────────────────────────────
    # Matches "spring", "water source", "potable water on trail" queries.
    ("spring",     lambda t: t.get("natural") == "spring"),
    ("hot_spring", lambda t: t.get("natural") == "hot_spring"),

    # ── Rapids / whitewater ────────────────────────────────────────────────────
    # Matches "rapids", "whitewater", "class III", etc.
    # OSM uses both whitewater=rapid and rapid=yes; natural=rapids is rare
    # but included for completeness.
    (
        "rapids",
        lambda t: (
            t.get("whitewater") == "rapid"
            or t.get("rapid") == "yes"
            or t.get("natural") == "rapids"
        ),
    ),

    # ── Swimming ───────────────────────────────────────────────────────────────
    # Matches "swimming hole", "swim", "swimming area".
    # NC: Sliding Rock, Skinny Dip Falls, Deep Creek; RI: state park beaches.
    ("swimming",   lambda t: t.get("leisure") == "swimming_area"),

    # ── Terrain / geology ──────────────────────────────────────────────────────
    ("cliff",      lambda t: t.get("natural") == "cliff"),
    ("cave",       lambda t: t.get("natural") == "cave_entrance"),
    ("glacier",    lambda t: t.get("natural") == "glacier"),

    # Matches "gorge", "canyon", "chasm".
    # NC: Linville Gorge, Tallulah area. OSM coverage is moderate.
    ("gorge",      lambda t: t.get("natural") == "gorge"),

    # Matches "natural arch", "rock arch", "window rock".
    ("arch",       lambda t: t.get("natural") == "arch"),

    # Matches "exposed rock", "granite dome", "bald", "rock scramble".
    # NC: Max Patch, Black Balsam, Looking Glass Rock.
    ("exposed_rock", lambda t: t.get("natural") in {"bare_rock", "scree"}),

    # ── Vegetation ─────────────────────────────────────────────────────────────
    # Matches "meadow", "open field", "wildflower field", "heath".
    ("meadow",     lambda t: t.get("natural") in {"grassland", "heath", "scrub"}),

    # Matches "wetland", "bog", "marsh", "swamp".
    # NC: Croatan National Forest coastal trails; RI: coastal salt marshes.
    ("wetland",    lambda t: t.get("natural") in {"wetland", "marsh", "bog"}),

    # ── Coastal features ───────────────────────────────────────────────────────
    # Matches "beach", "coastal walk", "shoreline hike".
    # NC: Cape Hatteras, Outer Banks trails; RI: Cliff Walk, East Beach.
    ("beach",      lambda t: t.get("natural") == "beach"),

    # Matches "sand dune", "dunes".
    # NC: Jockey's Ridge; RI: barrier island dunes.
    ("sand_dune",  lambda t: t.get("natural") == "dune"),

    # Matches "pier", "boardwalk", "coastal boardwalk".
    # RI: many coastal town piers; NC: sound-side boardwalk trails.
    ("pier",       lambda t: t.get("man_made") == "pier"),

    # ── Tourism / viewpoints ───────────────────────────────────────────────────
    # Matches "overlook", "viewpoint", "scenic view", "vista".
    ("viewpoint",  lambda t: t.get("tourism") == "viewpoint"),

    # Matches "fire tower", "observation tower", "lookout tower".
    # NC: Wayah Bald, Firescald Ridge, Pilot Mountain.
    # Only includes actual observation/fire towers — excludes cell/water towers.
    (
        "observation_tower",
        lambda t: (
            t.get("man_made") == "tower"
            and t.get("tower:type") in {"observation", "fire_watch", "watchtower"}
        ),
    ),

    # Matches "lighthouse", "light station".
    # RI: Point Judith, Castle Hill, Beavertail; NC: Cape Hatteras, Bodie Island.
    ("lighthouse", lambda t: t.get("man_made") == "lighthouse"),

    # ── Historic / cultural ────────────────────────────────────────────────────
    # Matches "ruins", "historic site", "old fort", "battlefield", "mine",
    # "archaeological site", "monument", "memorial".
    (
        "historic",
        lambda t: t.get("historic") in {
            "ruins", "castle", "fort", "archaeological_site",
            "monument", "battlefield", "memorial", "mine",
        },
    ),

    # ── Amenities ──────────────────────────────────────────────────────────────
    # Matches "picnic area", "picnic tables", "family-friendly", "day use area".
    ("picnic",     lambda t: t.get("tourism") == "picnic_site"),

    # ── Shelters / lean-tos ────────────────────────────────────────────────────
    # Matches "shelter", "lean-to", "hut", "backcountry shelter".
    # NC: extensive AT lean-to network. RI: limited but some state forest shelters.
    (
        "shelter",
        lambda t: (
            t.get("tourism") == "wilderness_hut"
            or t.get("amenity") == "shelter"
        ),
    ),

    # ── Wildlife / birding ─────────────────────────────────────────────────────
    # Matches "wildlife viewing", "bird watching", "birding", "bird blind".
    ("bird_watching", lambda t: t.get("leisure") == "bird_hide"),

    # Matches "wildlife area", "nature reserve", "protected land".
    (
        "wildlife",
        lambda t: (
            t.get("leisure") == "nature_reserve"
            or t.get("boundary") == "protected_area"
        ),
    ),

    # ── Camping — sets can_camp flag, does NOT add a tag ──────────────────────
    (
        "_can_camp",
        lambda t: (
            t.get("tourism") in {"camp_site", "caravan_site"}
            or t.get("leisure") == "camp_site"
            or t.get("amenity") == "camping"
        ),
    ),
]
# Tags Overpass can independently confirm or refute. Any of these appearing
# on a hike before enrichment (previously: derive_tags()'s name-substring
# guesses) is provisional at best — once Overpass has actually been queried,
# only a real matching feature should keep the tag. `_can_camp` is excluded;
# it maps to a boolean column, not a tag.
VERIFIABLE_TAGS = frozenset(feature for feature, _ in DETECTORS if not feature.startswith("_"))
# ── Overpass query template ────────────────────────────────────────────────────
#
# Every OSM key/value referenced in a DETECTOR predicate above must have a
# corresponding line here — otherwise Overpass won't return the element and
# the detector can never fire.  This template is the authoritative source of
# truth; keep it in sync with DETECTORS whenever you add a new feature.
#
# Structure: nodes first (point features), then ways (area / linear features).
# Relations are intentionally omitted — protected area boundaries as relations
# are rarely needed at trail scale and slow the query significantly.
#
# Two region filters are interpolated:
#   {filt}  →  around:<r>,<trail polyline>   (proximity — most features)
#   {bbox}  →  <s,w,n,e>                      (containment — protected areas)
# `around` returns only features the trail passes near, which both fixes the
# over-broad `river`/`stream` tagging AND shrinks payloads. Protected areas /
# nature reserves stay on {bbox}: their boundary line can be far from a trail
# that runs deep inside them, so proximity would wrongly drop `wildlife`.

_QUERY_TEMPLATE = """\
[out:json][timeout:{timeout}];
(
  node["natural"~"waterfall|peak|volcano|cave_entrance|glacier|hot_spring|spring|water|grassland|heath|scrub|cliff|gorge|arch|bare_rock|scree|wetland|marsh|bog|beach|dune|rapids"]({filt});
  node["waterway"~"waterfall|weir|dam|river|stream|canal"]({filt});
  node["whitewater"="rapid"]({filt});
  node["rapid"="yes"]({filt});
  node["tourism"~"viewpoint|camp_site|caravan_site|wilderness_hut|picnic_site"]({filt});
  node["historic"~"ruins|castle|fort|archaeological_site|monument|battlefield|memorial|mine"]({filt});
  node["leisure"~"camp_site|swimming_area|bird_hide"]({filt});
  node["amenity"~"camping|shelter"]({filt});
  node["man_made"~"weir|tower|lighthouse|pier"]({filt});
  way["natural"~"waterfall|water|glacier|grassland|heath|scrub|cliff|gorge|arch|bare_rock|scree|wetland|marsh|bog|beach|dune"]({filt});
  way["waterway"~"waterfall|weir|dam|river|stream|canal"]({filt});
  way["tourism"~"camp_site|caravan_site|wilderness_hut|picnic_site"]({filt});
  way["historic"~"ruins|castle|fort|archaeological_site|monument|battlefield|memorial|mine"]({filt});
  way["leisure"~"camp_site|swimming_area"]({filt});
  way["amenity"~"camping|shelter"]({filt});
  way["man_made"~"weir|tower|lighthouse|pier"]({filt});
  node["boundary"="protected_area"]({bbox});
  node["leisure"="nature_reserve"]({bbox});
  way["boundary"="protected_area"]({bbox});
  way["leisure"="nature_reserve"]({bbox});
);
out tags;"""

# ── Geometry helpers ───────────────────────────────────────────────────────────

def _bbox_from_geometry(
    geometry: dict,
) -> Optional[tuple[float, float, float, float]]:
    """
    Derives a buffered bbox from a GeoJSON LineString or MultiLineString.
    Coords are [lon, lat, ele?]; Overpass bbox order is (s, w, n, e).
    Returns None if geometry is absent or malformed.

    MultiLineString is a legitimate output of merge_duplicates.py's
    stitch_geometries() (used when trail fragments have a real gap in OSM
    and can't be joined) — its coordinates are nested one level deeper
    than LineString's, so they must be flattened before taking min/max.
    """
    try:
        coords = geometry["coordinates"]
        if not coords:
            return None

        if geometry.get("type") == "MultiLineString":
            points = [pt for segment in coords for pt in segment]
        else:
            points = coords

        if not points:
            return None

        lats = [p[1] for p in points]
        lons = [p[0] for p in points]
        return (
            min(lats) - BBOX_BUFFER_DEG,
            min(lons) - BBOX_BUFFER_DEG,
            max(lats) + BBOX_BUFFER_DEG,
            max(lons) + BBOX_BUFFER_DEG,
        )
    except (KeyError, IndexError, TypeError):
        return None


def _flatten_points(geometry: dict) -> list[tuple[float, float]]:
    """
    Flattened (lat, lon) vertices of a GeoJSON LineString / MultiLineString.
    GeoJSON coords are [lon, lat, ele?]; returned tuples are (lat, lon) to match
    Overpass's coordinate order. Returns [] if geometry is absent or malformed.
    """
    try:
        coords = geometry["coordinates"]
        if not coords:
            return []
        if geometry.get("type") == "MultiLineString":
            raw = [pt for segment in coords for pt in segment]
        else:
            raw = coords
        return [(p[1], p[0]) for p in raw if len(p) >= 2]
    except (KeyError, IndexError, TypeError):
        return []


def _trail_coords_string(geometry: dict) -> Optional[str]:
    """
    Builds the 'lat,lon,lat,lon,...' polyline that Overpass `around:` tests
    against. The trail is decimated to ~_COORD_MIN_GAP_M spacing (capped at
    _COORD_MAX_POINTS) so the query body stays small — `around` matches against
    the segments connecting these points, not just the points themselves, so
    light decimation doesn't open coverage gaps at a 75 m radius.

    Returns None when the geometry has no usable vertices (same signal as
    _bbox_from_geometry → treated as invalid_geometry upstream).
    """
    pts = _flatten_points(geometry)
    if not pts:
        return None

    # Local metres-per-degree at the trail's latitude (equirectangular; the
    # trail spans at most a few km so this is well under 1 % off).
    lat0 = pts[0][0]
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    gap_sq = _COORD_MIN_GAP_M ** 2

    kept = [pts[0]]
    last = pts[0]
    for la, lo in pts[1:]:
        dx = (lo - last[1]) * m_per_deg_lon
        dy = (la - last[0]) * m_per_deg_lat
        if dx * dx + dy * dy >= gap_sq:
            kept.append((la, lo))
            last = (la, lo)
    if kept[-1] != pts[-1]:
        kept.append(pts[-1])

    if len(kept) > _COORD_MAX_POINTS:
        step = math.ceil(len(kept) / _COORD_MAX_POINTS)
        kept = kept[::step]
        if kept[-1] != pts[-1]:
            kept.append(pts[-1])

    return ",".join(f"{la:.5f},{lo:.5f}" for la, lo in kept)


def _build_query(bbox: tuple[float, float, float, float], coords_str: str) -> str:
    s, w, n, e = bbox
    return _QUERY_TEMPLATE.format(
        timeout=OVERPASS_TIMEOUT,
        filt=f"around:{TRAIL_PROXIMITY_M},{coords_str}",
        bbox=f"{s:.6f},{w:.6f},{n:.6f},{e:.6f}",
    )


# ── HTTP ───────────────────────────────────────────────────────────────────────

def _post_overpass(query: str, limiter: "_RateLimiter") -> Optional[dict]:
    """POSTs an Overpass QL query with exponential back-off on failure or 429."""
    delay = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        limiter.acquire()
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "HikeBuilder-Enrichment/1.0"},
            )
            if resp.status_code == 429:
                wait = delay * (2 ** (attempt - 1))
                log.warning(f"Rate-limited (attempt {attempt}) — waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()

        except requests.Timeout:
            log.warning(f"Request timed out (attempt {attempt}/{MAX_RETRIES})")
        except requests.RequestException as exc:
            log.warning(f"Request error (attempt {attempt}/{MAX_RETRIES}): {exc}")

        if attempt < MAX_RETRIES:
            time.sleep(delay)
            delay *= 2

    return None

# ── Feature detection ──────────────────────────────────────────────────────────

def _detect_features(data: dict) -> tuple[set[str], bool]:
    """
    Single pass over Overpass elements — tests every DETECTOR predicate.
    Returns (new_hike_tags, can_camp_found).
    """
    new_tags: set[str] = set()
    can_camp            = False

    for element in data.get("elements", []):
        etags = element.get("tags") or {}
        for feature, predicate in DETECTORS:
            try:
                if predicate(etags):
                    if feature == "_can_camp":
                        can_camp = True
                    else:
                        new_tags.add(feature)
            except Exception:
                pass   # malformed predicate should never abort enrichment

    return new_tags, can_camp


# ── Per-hike enrichment (called from worker threads) ──────────────────────────

# new
def enrich_one(hike, limiter: "_RateLimiter") -> tuple[set[str], bool, str]:
    """
    Runs Overpass enrichment for a single hike.  Does NOT mutate the hike.
    Returns (new_tags, can_camp, status), where status is one of:

      "success"          — Overpass was queried successfully (possibly with
                            zero features found — that's a real, useful
                            result, not a failure).
      "invalid_geometry"  — hike.geometry is missing/malformed. PERMANENT —
                            no network call was even attempted, and retrying
                            will fail identically every time. Callers should
                            mark this done (distinctly) rather than leaving
                            it pending forever.
      "api_failure"       — Overpass couldn't be reached/queried after
                            retries. TRANSIENT — callers must leave the hike
                            completely unmarked so it's retried next run.
    """
    bbox   = _bbox_from_geometry(hike.geometry)
    coords = _trail_coords_string(hike.geometry)
    if bbox is None or coords is None:
        log.warning(f"  [{hike.name}] Missing or malformed geometry — skipped")
        return set(), False, "invalid_geometry"

    data = _post_overpass(_build_query(bbox, coords), limiter)
    if data is None:
        log.error(f"  [{hike.name}] Overpass failed after {MAX_RETRIES} attempts")
        return set(), False, "api_failure"

    new_tags, can_camp = _detect_features(data)
    return new_tags, can_camp, "success"


# ── Worker function ────────────────────────────────────────────────────────────

# new
def _enrich_worker(
    hike,
    limiter:  _RateLimiter,
    dry_run:  bool,
) -> tuple[set[str], set[str], bool, str]:
    """
    Returns (added_tags, removed_tags, camp_upgraded, status).
    status is "success" | "invalid_geometry" | "api_failure" — see enrich_one.
    """
    new_tags, camp_found, status = enrich_one(hike, limiter)

    if status in ("api_failure", "invalid_geometry"):
        # Neither is written to the DB. api_failure is transient — retry
        # next run. invalid_geometry should never actually reach here in
        # normal operation, since run() filters these out before
        # submission (see the partition there); if this branch fires,
        # something changed underneath us between listing and processing
        # and it's worth investigating, not silently marking done.
        return set(), set(), False, status

    existing_tags = set(hike.tags or [])

    # status == "success"
    added_tags    = new_tags - existing_tags
    # Overpass is authoritative for anything it's capable of verifying —
    # a verifiable tag that survived from before (e.g. a stale name-guess)
    # but wasn't confirmed this run gets dropped.
    removed_tags  = (existing_tags & VERIFIABLE_TAGS) - new_tags
    merged_tags   = sorted((existing_tags - removed_tags) | new_tags | {MARKER_TAG})
    camp_upgraded = camp_found and not hike.can_camp

    if not dry_run:
        hike.tags            = merged_tags
        hike.can_camp        = hike.can_camp or camp_found
        hike.last_synced_at  = datetime.now(timezone.utc)
        _thread_service().update_hike(hike)

    return added_tags, removed_tags, camp_upgraded, status


# ── Main loop ──────────────────────────────────────────────────────────────────

def run(
    batch_size: Optional[int],
    workers:    int,
    sleep_s:    float,
    force:      bool,
    dry_run:    bool,
) -> None:
    # Use a dedicated service just for the initial list fetch.
    service   = HikeService(HikeRepository())
    all_hikes = service.list_hikes()
    log.info(f"Total hikes in DB  : {len(all_hikes)}")

    if not force:
        all_hikes = [h for h in all_hikes if MARKER_TAG not in (h.tags or [])]
        log.info(f"Pending enrichment : {len(all_hikes)}")

    # Partition out geometry-invalid hikes up front. These fail before any
    # network call (_bbox_from_geometry returns None) and will fail
    # identically every future run — retrying doesn't fix a bad geometry
    # column, only a re-ingest/re-merge does. Excluded here, not tagged:
    # tagging would mean writing an internal marker into the same tags[]
    # array HikeSearchService filters on and the app likely displays.
    geometry_invalid_hikes = [h for h in all_hikes if _bbox_from_geometry(h.geometry) is None]
    all_hikes               = [h for h in all_hikes if _bbox_from_geometry(h.geometry) is not None]

    if geometry_invalid_hikes:
        log.warning(
            f"Excluding {len(geometry_invalid_hikes)} hike(s) with missing/malformed "
            f"geometry — needs a data fix upstream (re-ingest/re-merge), not a retry:"
        )
        for h in geometry_invalid_hikes[:20]:
            log.warning(f"    {h.name}  (id={h.id})")
        if len(geometry_invalid_hikes) > 20:
            log.warning(f"    ... and {len(geometry_invalid_hikes) - 20} more")

    if batch_size:
        all_hikes = all_hikes[:batch_size]
        log.info(f"Batch cap applied  : processing {len(all_hikes)}")

    if dry_run:
        log.info("DRY RUN — Overpass will be queried but no DB writes will occur")

    log.info(
        f"Workers: {workers}  |  Min interval: {sleep_s}s  "
        f"→ max ~{1/sleep_s:.2f} req/s"
    )

    # new
    limiter  = _RateLimiter(sleep_s)
    enriched                  = 0
    unexpected_geometry_issue = 0   # should stay 0 — see _enrich_worker note
    api_failed                = 0
    errors                    = 0
    total                     = len(all_hikes)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        # Submit all hikes upfront so the pool can start immediately.
        future_to_hike = {
            pool.submit(_enrich_worker, hike, limiter, dry_run): hike
            for hike in all_hikes
        }

        # Process results as they complete — order is non-deterministic.
        # new
        for done_count, future in enumerate(as_completed(future_to_hike), 1):
            hike = future_to_hike[future]
            try:
                added_tags, removed_tags, camp_upgraded, status = future.result()

                if status == "api_failure":
                    log.warning(f"[{done_count:>4}/{total}]  {hike.name}  — API failure, will retry next run")
                    api_failed += 1
                    continue

                if status == "invalid_geometry":
                    log.warning(f"[{done_count:>4}/{total}]  {hike.name}  — bad geometry slipped past the upfront filter, investigate")
                    unexpected_geometry_issue += 1
                    continue

                note_parts = []
                if added_tags:
                    note_parts.append(f"+{sorted(added_tags)}")
                if removed_tags:
                    note_parts.append(f"-{sorted(removed_tags)}")
                if camp_upgraded:
                    note_parts.append("+can_camp")
                note = "  ".join(note_parts) if note_parts else "no new features"
                log.info(f"[{done_count:>4}/{total}]  {hike.name}  — {note}")
                enriched += 1
            except Exception as exc:
                log.error(
                    f"[{done_count:>4}/{total}]  ERROR on '{hike.name}': {exc}",
                    exc_info=True,
                )
                errors += 1

        log.info("─" * 45)
        log.info(f"Enriched                : {enriched}")
        log.info(f"Excluded (bad geometry) : {len(geometry_invalid_hikes)}  (see list above — needs a data fix, not a retry)")
        if unexpected_geometry_issue:
            log.warning(f"Unexpected mid-run geometry issues : {unexpected_geometry_issue}  (should be 0)")
        log.info(f"API failures            : {api_failed}  (will retry next non --force run)")
        log.info(f"Errors                  : {errors}")
    if dry_run:
        log.info("(dry run — no writes were committed)")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Concurrently enrich hike tags with Overpass API feature data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--batch", type=int, default=None, metavar="N",
        help="Max hikes to process this run (default: all pending)",
    )
    p.add_argument(
        "--workers", type=int, default=3, metavar="N",
        help="Number of concurrent Overpass threads (recommended: 3–5)",
    )
    p.add_argument(
        "--sleep", type=float, default=1.5, metavar="S",
        help="Minimum seconds between any two Overpass requests",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Re-enrich hikes already marked overpass_enriched",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Query Overpass and log results but skip all database writes",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(
        batch_size=args.batch,
        workers=args.workers,
        sleep_s=args.sleep,
        force=args.force,
        dry_run=args.dry_run,
    )