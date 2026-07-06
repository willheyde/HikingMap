"""
ingestion/merge_duplicates.py

Post-ingest deduplication pass.  Finds hikes sharing the same name and region
(artefacts of OSM way fragmentation), stitches their LineString geometries
end-to-end, consolidates stats, and replaces the whole group with one
canonical hike record.

Pipeline position — always run in this order:
    python ingestion/ingest.py
    python ingestion/merge_duplicates.py        ← here
    python ingestion/overpass_enrichment.py

The overpass_enriched marker is stripped from merged tags so that
overpass_enrichment re-processes the consolidated record with the full
bounding box of the stitched geometry.

Usage:
    python ingestion/merge_duplicates.py
    python ingestion/merge_duplicates.py --dry-run
    python ingestion/merge_duplicates.py --batch 50 --dry-run

Options:
    --dry-run      Log full merge plan but skip all DB writes
    --batch N      Process at most N duplicate groups this run (default: all)
"""

import sys
import logging
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from math import hypot
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).parent.parent))

from Repos.HikeRepo import HikeRepository
from Services.HikeService import HikeService
from ingestion.characterizations import (
    calculate_difficulty,
    derive_tags,
    find_data_quality_issues,
    haversine,
)
from ingestion.overpass_enrichment import VERIFIABLE_TAGS
# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

# Endpoints closer than this (in degrees, ~200 m) are considered connected
# and will be stitched into a single LineString.  Gaps larger than this
# produce a MultiLineString fallback — both are valid GeoJSON and render
# correctly in Mapbox / Leaflet.
STITCH_THRESHOLD_DEG = 0.002

# The enrichment marker tag — stripped before merge so overpass_enrichment
# re-runs on the newly stitched geometry.
OVERPASS_MARKER = "overpass_enriched"


# ── Geometry ───────────────────────────────────────────────────────────────────

def _ep_dist(a: list, b: list) -> float:
    """Euclidean distance between two [lon, lat, ?ele] points."""
    return hypot(a[0] - b[0], a[1] - b[1])


def stitch_geometries(segments: list[list]) -> dict:
    """
    Greedily stitches coordinate arrays into a single GeoJSON LineString.

    Algorithm
    ─────────
    Starting from the first (longest) segment, each iteration picks the
    remaining segment whose nearest endpoint is closest to the current
    tail — reversing either chain as needed so the join is end-to-start.

    Falls back to MultiLineString if any gap exceeds STITCH_THRESHOLD_DEG.
    Both types render correctly in standard map libraries.

    Args:
        segments: list of GeoJSON coordinate arrays [[lon, lat, ele?], ...]
                  ordered longest-first (callers sort by length_km desc).

    Returns:
        GeoJSON geometry dict — {"type": "LineString", ...} or
        {"type": "MultiLineString", ...}.
    """
    if not segments:
        raise ValueError("stitch_geometries called with empty segment list")
    if len(segments) == 1:
        return {"type": "LineString", "coordinates": segments[0]}

    result    = list(segments[0])
    remaining = list(segments[1:])   # index-tracked for safe removal

    while remaining:
        best_dist     = float("inf")
        best_idx      = -1
        best_flip_res = False
        best_flip_seg = False

        for idx, seg in enumerate(remaining):
            # Test all 4 endpoint orientations:
            #   flip_result × flip_seg  →  which tail/head pair to measure
            for flip_r, flip_s in [
                (False, False),   # result_tail → seg_head
                (False, True),    # result_tail → seg_tail  (seg reversed)
                (True,  False),   # result_head → seg_head  (result reversed)
                (True,  True),    # result_head → seg_tail  (both reversed)
            ]:
                r_tail = (result[::-1] if flip_r else result)[-1]
                s_head = (seg[::-1]    if flip_s else seg)[0]
                d      = _ep_dist(r_tail, s_head)
                if d < best_dist:
                    best_dist     = d
                    best_idx      = idx
                    best_flip_res = flip_r
                    best_flip_seg = flip_s

        if best_dist > STITCH_THRESHOLD_DEG:
            # Gap too large — segments are genuinely disconnected
            log.debug(
                f"  Segment gap {best_dist:.4f}° > threshold "
                f"({STITCH_THRESHOLD_DEG}°) — using MultiLineString"
            )
            return {
                "type":        "MultiLineString",
                "coordinates": [result] + remaining,
            }

        # Apply orientations and join
        if best_flip_res:
            result = result[::-1]
        chosen = remaining.pop(best_idx)
        if best_flip_seg:
            chosen = chosen[::-1]

        result = result + chosen

    return {"type": "LineString", "coordinates": result}


# ── Grouping ───────────────────────────────────────────────────────────────────

# near STITCH_THRESHOLD_DEG
MAX_MERGE_GAP_KM = 2.0
# Real OSM way splits for a single trail (road crossings, parking areas,
# tagging boundaries) leave gaps of tens of meters up to a km or so.
# Two fragments further apart than this sharing a name are almost
# certainly distinct trails (e.g. "Red Trail" in two different parks),
# not the same trail split by OSM. Long real trails (Mountains-to-Sea,
# AT) still cluster correctly here because their fragments are closely
# spaced end-to-end even though the *overall* path spans hundreds of km —
# this checks local adjacency, not total span.


def _endpoints(geometry: dict) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
    """Returns ((lat, lon), (lat, lon)) for a geometry's first/last point."""
    try:
        coords = geometry["coordinates"]
        points = (
            [pt for seg in coords for pt in seg]
            if geometry.get("type") == "MultiLineString"
            else coords
        )
        if len(points) < 2:
            return None
        return (points[0][1], points[0][0]), (points[-1][1], points[-1][0])
    except (KeyError, IndexError, TypeError):
        return None


def _min_endpoint_gap_km(a: dict, b: dict) -> float:
    ea, eb = _endpoints(a), _endpoints(b)
    if ea is None or eb is None:
        return float("inf")   # can't verify proximity — don't merge
    a_start, a_end = ea
    b_start, b_end = eb
    pairs = [(a_start, b_start), (a_start, b_end), (a_end, b_start), (a_end, b_end)]
    return min(haversine(p1[0], p1[1], p2[0], p2[1]) for p1, p2 in pairs) / 1000


def _cluster_by_proximity(hikes: list) -> list[list]:
    """Union-Find: only chain hikes together whose endpoints are actually close."""
    n = len(hikes)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if _min_endpoint_gap_km(hikes[i].geometry, hikes[j].geometry) <= MAX_MERGE_GAP_KM:
                union(i, j)

    clusters: dict[int, list] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(hikes[i])
    return list(clusters.values())


def find_duplicate_groups(all_hikes: list) -> list[list]:
    """
    Groups hikes by (normalised_name, region), then splits each bucket into
    spatially-connected clusters via _cluster_by_proximity — so distinct
    trails sharing a generic name (e.g. "Red Trail" in two different parks)
    don't get merged into one physically nonsensical record, while genuinely
    long trails (Mountains-to-Sea, AT) still merge correctly since their
    fragments chain together with small local gaps.
    """
    buckets: dict[tuple, list] = defaultdict(list)
    for hike in all_hikes:
        key = (hike.name.strip().lower(), (hike.region or "").strip().lower())
        buckets[key].append(hike)

    groups: list[list] = []
    for bucket in buckets.values():
        if len(bucket) > 1:
            groups.extend(_cluster_by_proximity(bucket))

    return [g for g in groups if len(g) > 1]


# ── Merging ────────────────────────────────────────────────────────────────────
def _recompute_stats_from_geometry(geometry: dict) -> tuple[float | None, float | None]:
    """
    Recomputes (length_km, gain_m) by walking a merged LineString's final,
    deduplicated coordinate sequence directly, instead of summing each
    fragment's independently computed length_km / elevation_gain_m.

    Summing per-fragment stats assumes fragments never share nodes or
    overlapping ground — an assumption OSM way-splitting can violate (a
    junction node counted in two fragments, or a genuinely duplicated way).
    Recomputing from the stitched path measures the ground exactly once
    regardless of how many DB rows it came from.

    Returns (None, None) for anything other than a plain LineString —
    a MultiLineString means the fragments are genuinely disconnected (no
    shared nodes possible), so the caller should keep the per-fragment sums.
    Also returns None for gain if any point is missing elevation data,
    rather than silently undercounting across the gap.
    """
    if geometry.get("type") != "LineString":
        return None, None

    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return None, None

    have_elevation = all(len(c) > 2 and c[2] is not None for c in coords)

    distance_m = 0.0
    gain_m = 0.0
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i - 1][0], coords[i - 1][1]
        lon2, lat2 = coords[i][0], coords[i][1]
        distance_m += haversine(lat1, lon1, lat2, lon2)
        if have_elevation:
            delta = coords[i][2] - coords[i - 1][2]
            if delta > 0:
                gain_m += delta

    return distance_m / 1000, (gain_m if have_elevation else None)
def merge_group(hikes: list) -> tuple:
    """
    Merges a duplicate group into a single consolidated Hike.
    Does NOT mutate the DB — returns (merged_hike, [ids_to_delete]).

    Merge rules
    ───────────
    primary            longest segment (most representative trailhead lat/lng)
    length_km/gain_m   recomputed from the stitched geometry when possible
                       (see _recompute_stats_from_geometry) — falls back to
                       summing fragment stats only for MultiLineString or
                       missing elevation data
    min_altitude_m     min across segments
    max_altitude_m     max across segments
    difficulty         recalculated from merged length + merged gain
    season_start_month earliest start across segments
    season_end_month   latest end across segments
    permits_required   True if any segment requires permits
    can_camp           True if any segment allows camping
    tags               recomputed FRESH from the merged totals via
                       derive_tags() (duration/gain/altitude/season/
                       permits/name) — NOT a blind tag union. A stale tier
                       tag from whichever fragment happened to be primary
                       (e.g. "flat") must not survive once merged totals no
                       longer support it. Overpass-verified feature tags
                       (VERIFIABLE_TAGS) are unioned back in separately,
                       since derive_tags() can't know about those.
    geometry           stitched LineString (or MultiLineString if disconnected)
    lat / lng          kept from primary (longest segment's trailhead)
    """
    hikes  = sorted(hikes, key=lambda h: h.length_km, reverse=True)
    primary = hikes[0]
    rest    = hikes[1:]

    # ── Geometry (computed first — numeric stats below need it) ────────────────
    segments: list[list] = []
    for h in hikes:
        try:
            coords = h.geometry["coordinates"]
            if coords:
                segments.append(list(coords))
        except (KeyError, TypeError):
            log.warning(f"  [{h.name}] id={h.id} — malformed geometry, segment skipped")

    if not segments:
        log.warning(f"  [{primary.name}] No valid geometry segments — keeping primary geometry")
        merged_geometry = primary.geometry
    else:
        merged_geometry = stitch_geometries(segments)

    # ── Numeric stats ────────────────────────────────────────────────────────
    recomputed_length_km, recomputed_gain_m = _recompute_stats_from_geometry(merged_geometry)

    total_length_km = (
        recomputed_length_km if recomputed_length_km is not None
        else sum(h.length_km for h in hikes)
    )
    total_gain_m = (
        recomputed_gain_m if recomputed_gain_m is not None
        else sum(h.elevation_gain_m for h in hikes)
    )

    merged_min_alt       = min(h.min_altitude_m     for h in hikes)
    merged_max_alt       = max(h.max_altitude_m     for h in hikes)
    merged_season_start  = min(h.season_start_month for h in hikes)
    merged_season_end    = max(h.season_end_month   for h in hikes)
    merged_permits       = any(h.permits_required   for h in hikes)
    merged_can_camp      = any(h.can_camp           for h in hikes)
    merged_difficulty    = calculate_difficulty(total_length_km, total_gain_m)

    # ── Tags — recomputed fresh, not unioned ────────────────────────────────
    recomputed_tags = set(derive_tags(
        length_km          = total_length_km,
        elevation_gain_m   = total_gain_m,
        max_altitude_m     = merged_max_alt,
        season_start_month = merged_season_start,
        season_end_month   = merged_season_end,
        permits_required   = merged_permits,
        name                = primary.name,
    ))
    preserved_overpass_tags = {
        t for h in hikes for t in (h.tags or []) if t in VERIFIABLE_TAGS
    }
    merged_tags = sorted(recomputed_tags | preserved_overpass_tags)

    quality_issues = find_data_quality_issues(
        total_length_km, total_gain_m, merged_difficulty, merged_tags
    )
    if quality_issues:
        log.warning(f"  [{primary.name}] merged record still fails sanity checks: {'; '.join(quality_issues)}")

    # ── Apply to primary object ─────────────────────────────────────────────
    primary.length_km          = round(total_length_km, 2)
    primary.elevation_gain_m   = round(total_gain_m,    1)
    primary.min_altitude_m     = round(merged_min_alt,  1)
    primary.max_altitude_m     = round(merged_max_alt,  1)
    primary.difficulty         = merged_difficulty
    primary.season_start_month = merged_season_start
    primary.season_end_month   = merged_season_end
    primary.permits_required   = merged_permits
    primary.can_camp           = merged_can_camp
    primary.tags               = merged_tags
    primary.geometry           = merged_geometry
    primary.last_synced_at     = datetime.now(timezone.utc)

    delete_ids = [h.id for h in rest]
    return primary, delete_ids


# ── Main loop ──────────────────────────────────────────────────────────────────

def run(dry_run: bool, batch_size: Optional[int]) -> None:
    service   = HikeService(HikeRepository())
    all_hikes = service.list_hikes()
    log.info(f"Total hikes in DB  : {len(all_hikes)}")

    groups = find_duplicate_groups(all_hikes)
    log.info(f"Duplicate groups   : {len(groups)}")

    if not groups:
        log.info("Nothing to merge — exiting.")
        return

    if batch_size:
        groups = groups[:batch_size]
        log.info(f"Batch cap applied  : processing {len(groups)} groups")

    if dry_run:
        log.info("DRY RUN — Overpass will be queried but no DB writes will occur")

    merged_count = errors = 0
    total        = len(groups)

    for i, group in enumerate(groups, 1):
        segment_summary = "  +  ".join(
            f"'{h.name}' ({h.length_km:.1f} km, +{h.elevation_gain_m:.0f} m)"
            for h in sorted(group, key=lambda h: h.length_km, reverse=True)
        )
        log.info(f"[{i:>4}/{total}]  {segment_summary}")

        try:
            merged_hike, delete_ids = merge_group(group)
            geo_type = merged_hike.geometry.get("type", "unknown")

            log.info(
                f"         → {merged_hike.length_km:.1f} km total  |  "
                f"+{merged_hike.elevation_gain_m:.0f} m gain  |  "
                f"{merged_hike.difficulty}  |  "
                f"geometry: {geo_type}  |  "
                f"deleting {len(delete_ids)} fragment(s)"
            )

            if not dry_run:
                service.update_hike(merged_hike)
                for hike_id in delete_ids:
                    service.delete_hike(hike_id)

            merged_count += 1

        except Exception as exc:
            log.error(
                f"         ERROR merging group '{group[0].name}': {exc}",
                exc_info=True,
            )
            errors += 1

    log.info("─" * 50)
    log.info(f"Groups merged : {merged_count}")
    log.info(f"Errors        : {errors}")
    if dry_run:
        log.info("(dry run — no writes were committed)")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge duplicate hike records caused by OSM way fragmentation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Log full merge plan but skip all DB writes",
    )
    p.add_argument(
        "--batch", type=int, default=None, metavar="N",
        help="Max duplicate groups to process this run (default: all)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(dry_run=args.dry_run, batch_size=args.batch)