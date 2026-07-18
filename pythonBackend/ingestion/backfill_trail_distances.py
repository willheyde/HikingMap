#!/usr/bin/env python3
"""
backfill_trail_distances.py

Correct the stored length of OUT-AND-BACK trails — which OSM records one-way
(trailhead → turnaround) and so read at ~half their real round-trip distance.

THIS IS THE SOLE OWNER OF OUT-AND-BACK DOUBLING. Neither ingest (ingest.py /
hike_parser.py) nor merge_duplicates.py doubles — they only ever produce one-way
path length and leave trail_shape NULL. Doubling here, off the FINAL merged
geometry and gated by trail_shape, keeps it in exactly one place and idempotent
(a merged trail's length would otherwise be recomputed one-way by the merge step,
silently un-doing an ingest-time double). Consequently this must be the LAST step
of any pipeline run:

    ingest.py → merge_duplicates.py → overpass_enrichment.py
        → migrate.py up  (once, for the trail_shape column)
        → backfill_trail_distances.py      ← here (run after any (re-)ingest)
        → prune_short_hikes.py             (optional min-length purge, corrected)

It can also be run standalone on an existing DB (the original purpose) — it needs
no re-ingest, since it works off geometry already stored.

Handles both geometry types in the DB: a plain LineString and the
MultiLineString that merge_duplicates.py emits when it stitches OSM-fragmented
duplicates whose gaps are too wide to bridge (its endpoints are taken across all
fragments; its length sums each fragment, never the empty gaps between them).

For each hike not yet classified (hikes.trail_shape IS NULL):
  * classify LOOP vs OUT_AND_BACK from the stored geometry's overall endpoints
      - LOOP          → leave length_km untouched (geometry already spans the
                        walk); just stamp trail_shape.
      - OUT_AND_BACK  → length_km *= 2, then keep the record self-consistent:
          - difficulty        recomputed from the corrected length (Shenandoah
                              formula); NEVER downgraded, so a sac_scale-derived
                              hard rating survives even though we lack the tag.
          - length-bucket tag swapped (short/half_day/full_day/overnight/
                              multi_day); every OTHER tag — including the
                              Overpass-enrichment feature tags (waterfall,
                              lake, summit, …) — is left intact.
          - gear_requirements re-derived from the corrected length via the exact
                              call ingestion uses (infer_gear_levels).
      - UNKNOWN        → a degenerate/unsupported geometry (< 2 usable points)
                        can't be classified; it's stamped 'unknown' (length left
                        as-is) so it's non-null and never re-scanned, rather than
                        failing on every run.

Elevation gain is deliberately NOT doubled: on a there-and-back the climb is all
on the outbound leg and the return is descent, so one-way positive gain already
≈ the true round-trip gain.

Idempotent: trail_shape is the gate. A second run — or a later re-ingest, which
also stamps trail_shape whenever it sets length — skips every already-classified
row, so no distance is ever doubled twice.

Run from the pythonBackend directory (after applying migrations/005_trail_shape.sql):

    python ingestion/backfill_trail_distances.py            # apply to all hikes
    python ingestion/backfill_trail_distances.py --dry-run  # print, change nothing
"""

import argparse
import json
import os
import sys

# Runnable from inside ingestion/ or from pythonBackend/ — make the backend root
# importable either way (mirrors run_ingestion.py / backfill_gear_levels.py).
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from DBConnection import get_connection, close_pool
from PyObjects.Hike import DifficultyLevel
from gear_inference import GearInferenceEngine
from characterizations import (
    calculate_difficulty,
    classify_trail_shape,
    haversine,
    length_bucket_tag,
    LENGTH_BUCKET_TAGS,
    MAX_OUT_AND_BACK_ONEWAY_KM,
    TRAIL_SHAPE_LOOP,
    TRAIL_SHAPE_OUT_AND_BACK,
    TRAIL_SHAPE_POINT_TO_POINT,
    TRAIL_SHAPE_UNKNOWN,
)

# Flag when the length recomputed from the stored geometry diverges this much
# from the stored length_km — a signal that geometry and length_km disagree
# (e.g. a different distance method at ingest, or a dropped-way gap). Advisory
# only; the correction always doubles the STORED length so it stays idempotent.
SANITY_DIVERGENCE = 0.25


def _difficulty(raw) -> DifficultyLevel:
    """DB stores difficulty as the enum NAME (e.g. 'MODERATE'). Fall back to
    MODERATE for anything unrecognized rather than crashing the whole run."""
    try:
        return DifficultyLevel[str(raw).upper()]
    except KeyError:
        return DifficultyLevel.MODERATE


def _harder(a: DifficultyLevel, b: DifficultyLevel) -> DifficultyLevel:
    """The tougher of two difficulties. Guards against downgrading a
    sac_scale-derived rating we can't see here: doubling distance only raises the
    formula result, so we never want the recompute to LOWER a stored value."""
    return a if a.value >= b.value else b


def _segments(geom: dict) -> list:
    """
    Normalizes a stored geometry to a list of segments, each a list of
    [lon, lat, (ele)] points. A LineString is one segment; a MultiLineString
    (what merge_duplicates.py emits when it stitches OSM-fragmented duplicates
    whose gaps are too wide to bridge) is several. Anything else → [].
    """
    coords = geom.get("coordinates") or []
    if geom.get("type") == "MultiLineString":
        return [seg for seg in coords if seg]
    if geom.get("type") == "LineString":
        return [coords] if coords else []
    return []


def _endpoints(segments: list):
    """
    Overall trail endpoints as (first_lat, first_lon, last_lat, last_lon):
    the start of the first segment and the end of the last. Mirrors
    merge_duplicates._endpoints — segment order is already geometric. Returns
    None when there aren't at least two points across all segments.
    """
    pts = [p for seg in segments for p in seg]
    if len(pts) < 2:
        return None
    return pts[0][1], pts[0][0], pts[-1][1], pts[-1][0]


def _oneway_km(segments: list) -> float:
    """
    Great-circle length of the stored geometry, km — computed the SAME way the
    stored length_km was: walked within each segment and summed across segments,
    so the empty gaps BETWEEN disconnected MultiLineString fragments are never
    counted (matching merge_duplicates' fragment-sum fallback).
    """
    total_m = 0.0
    for seg in segments:
        for i in range(1, len(seg)):
            total_m += haversine(seg[i - 1][1], seg[i - 1][0], seg[i][1], seg[i][0])
    return total_m / 1000.0


def backfill(dry_run: bool = False) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, geometry, length_km, elevation_gain_m,
                       max_altitude_m, difficulty, tags, can_camp
                FROM hikes
                WHERE trail_shape IS NULL
                """
            )
            rows = cur.fetchall()

            print(f"Found {len(rows)} unclassified hike(s).")
            loops = corrected = unknown = 0

            def _stamp_unknown(row) -> None:
                """Mark a row we can't classify so it's non-null and never
                re-scanned; its length_km is left untouched."""
                if not dry_run:
                    cur.execute(
                        "UPDATE hikes SET trail_shape = %s WHERE id = %s",
                        (TRAIL_SHAPE_UNKNOWN, str(row["id"])),
                    )

            for row in rows:
                try:
                    geom = row["geometry"]
                    if isinstance(geom, str):
                        geom = json.loads(geom)
                    segments = _segments(geom or {})
                    ends     = _endpoints(segments)
                    if ends is None:
                        # Degenerate/empty/unsupported geometry — can't classify.
                        print(f"  [dry-run] UNK   {row['name']}: <2 usable points (left as-is)"
                              if dry_run else
                              f"  UNK   {row['name']}: <2 usable points — stamped 'unknown', length left as-is")
                        _stamp_unknown(row)
                        unknown += 1
                        continue

                    first_lat, first_lon, last_lat, last_lon = ends
                    shape      = classify_trail_shape(first_lat, first_lon, last_lat, last_lon)
                    stored_len = float(row["length_km"] or 0)

                    # Sanity: does the stored length match the stored geometry?
                    # (Both LineString and MultiLineString are handled by _oneway_km.)
                    recomputed = _oneway_km(segments)
                    if stored_len > 0 and abs(recomputed - stored_len) / stored_len > SANITY_DIVERGENCE:
                        print(f"  ~ {row['name']}: stored {stored_len:.2f} km vs geometry "
                              f"{recomputed:.2f} km (>{SANITY_DIVERGENCE:.0%} apart) — still doubling stored")

                    if shape == TRAIL_SHAPE_LOOP:
                        if dry_run:
                            print(f"  [dry-run] LOOP  {row['name']}: {stored_len:.2f} km (unchanged)")
                        else:
                            cur.execute(
                                "UPDATE hikes SET trail_shape = %s WHERE id = %s",
                                (TRAIL_SHAPE_LOOP, str(row["id"])),
                            )
                        loops += 1
                        continue

                    # ── Long linear guard: an OPEN trail already longer one-way
                    # than MAX_OUT_AND_BACK_ONEWAY_KM is far more likely a thru/
                    # linear corridor (AT/MST/PCT segment) than a >50 km round-trip
                    # out-and-back. Doubling would fabricate a ~2× distance, so
                    # stamp point_to_point and leave length untouched.
                    if stored_len > MAX_OUT_AND_BACK_ONEWAY_KM:
                        print(f"  [dry-run] LINEAR {row['name']}: {stored_len:.2f} km one-way "
                              f"> {MAX_OUT_AND_BACK_ONEWAY_KM:.0f} km — NOT doubled"
                              if dry_run else
                              f"  LINEAR {row['name']}: {stored_len:.2f} km one-way "
                              f"> {MAX_OUT_AND_BACK_ONEWAY_KM:.0f} km — stamped 'point_to_point', not doubled")
                        if not dry_run:
                            cur.execute(
                                "UPDATE hikes SET trail_shape = %s WHERE id = %s",
                                (TRAIL_SHAPE_POINT_TO_POINT, str(row["id"])),
                            )
                        unknown += 1
                        continue

                    # ── OUT_AND_BACK: double the stored length, keep row consistent ──
                    new_len = round(stored_len * 2, 2)
                    gain    = float(row["elevation_gain_m"] or 0)
                    max_alt = float(row["max_altitude_m"] or 0)

                    old_diff = _difficulty(row["difficulty"])
                    new_diff = _harder(old_diff, calculate_difficulty(new_len, gain))

                    old_tags = list(row.get("tags") or [])
                    new_tags = sorted(
                        {t for t in old_tags if t not in LENGTH_BUCKET_TAGS}
                        | {length_bucket_tag(new_len)}
                    )

                    new_reqs = GearInferenceEngine.infer_gear_levels(
                        length_km  = new_len,
                        gain_m     = gain,
                        max_alt_m  = max_alt,
                        difficulty = new_diff,
                        tags       = new_tags,
                        can_camp   = bool(row.get("can_camp")),
                    )

                    if dry_run:
                        d = "" if new_diff == old_diff else f", difficulty {old_diff.name}→{new_diff.name}"
                        print(f"  [dry-run] O&B   {row['name']}: {stored_len:.2f}→{new_len:.2f} km{d}")
                        corrected += 1
                        continue

                    cur.execute(
                        """
                        UPDATE hikes SET
                            length_km         = %s,
                            difficulty        = %s,
                            tags              = %s,
                            gear_requirements = %s,
                            trail_shape       = %s
                        WHERE id = %s
                        """,
                        (new_len, new_diff.name, new_tags,
                         json.dumps(new_reqs), TRAIL_SHAPE_OUT_AND_BACK, str(row["id"])),
                    )
                    corrected += 1

                except Exception as e:
                    # Nothing above should raise now, but keep a backstop: mark the
                    # row 'unknown' (still non-null, still idempotent) rather than
                    # leaving it NULL to fail again on every future run.
                    print(f"  ! {row['name']} ({row['id']}): could not classify — {e}; stamped 'unknown'")
                    try:
                        _stamp_unknown(row)
                    except Exception:
                        pass
                    unknown += 1

        # get_connection commits on clean exit of the context manager.

    verb = "Would correct" if dry_run else "Corrected"
    print(f"\nLoops (left as-is): {loops}   {verb} (out-and-back): {corrected}"
          f"   unknown (stamped, length unchanged): {unknown}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Double the one-way length of out-and-back trails; leave loops untouched."
    )
    ap.add_argument("--dry-run", action="store_true", help="Print what would change; write nothing.")
    args = ap.parse_args()
    try:
        backfill(dry_run=args.dry_run)
    finally:
        # A one-shot script never triggers the app's shutdown hook, so the lazily
        # opened psycopg_pool (with its background worker thread) would otherwise
        # be torn down by the GC at interpreter exit — which is what prints the
        # "pool was not closed" warning. Close it explicitly. No-op without the pool.
        close_pool()
