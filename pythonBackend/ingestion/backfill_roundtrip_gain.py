#!/usr/bin/env python3
"""
backfill_roundtrip_gain.py — correct elevation gain for OUT-AND-BACK trails.

The base gain written by backfill_elevation.py is the ONE-WAY summed ascent. That
is correct for loops and linear/point-to-point trails, but WRONG for an
out-and-back: you retrace the path, so every descent you walk on the way out
becomes a climb on the way back. The round-trip gain a hiker actually experiences
is the one-way ascent PLUS the one-way descent.

A trail whose stored one-way geometry runs net-downhill (e.g. Spence Ridge,
descending into Linville Gorge) therefore reads far too low — its ascent is tiny,
and the real "climb out" lives entirely in the descent leg we were discarding.
That's the "strenuous trail labelled flat / 65 m" bug.

Why ELEVATION RANGE, not ascent+descent
----------------------------------------
On a 30 m DSM, summing ascent+descent doubles the per-step noise (a graded climb
invents phantom descents; a canopy-laden greenway invents both). So instead of a
noisy delta-sum we use the noise-robust ELEVATION RANGE (max_altitude_m -
min_altitude_m): two altitude readings, not a sum of hundreds of noisy deltas. For
a mostly-monotonic out-and-back — the common case (a trail out to a summit, lake,
waterfall, or gorge floor) — the range IS the round-trip gain (drop in, climb out).

Calibrated against known trails (see ingestion/diagnose_elevation.py):
    Spence Ridge   65 -> 266 m   (known ~250, was "flat")
    McMullen g'way  92 ->  22 m   (known ~12, was inflated by canopy)
    Rattlesnake    223 -> 227 m   (known ~225, stays accurate)
Range fixes BOTH the under-counts and the over-counts.

Scope + guards
--------------
  * Only trail_shape = 'out_and_back'. Loops and point_to_point/linear trails keep
    their summed ascent (you don't retrace them, so range would UNDER-count — the
    49 km Mountains-to-Sea segment has range 818 m but real gain ~5523 m).
  * Only length_km <= ROUNDTRIP_GAIN_MAX_KM. This excludes long LINEAR thru-trails
    that the pre-guard distance run mislabelled 'out_and_back' (MST, American
    Tobacco, Neusiok) — they are long, so a length cap cleanly separates them from
    genuine out-and-backs (almost all well under 30 km round-trip).
  * Idempotent: gain := (max-min) is stable across re-runs.

Pipeline position: run AFTER backfill_elevation.py (which sets min/max altitude)
AND backfill_trail_distances.py (which sets trail_shape). A subsequent
`backfill_elevation.py --force` would overwrite gain with the one-way sum again, so
re-run this afterwards. Then run backfill_difficulty.py so difficulty, the
gain-tier tag, and gear reflect the corrected gain:

    python ingestion/backfill_roundtrip_gain.py --dry-run
    python ingestion/backfill_roundtrip_gain.py
    python ingestion/backfill_difficulty.py
"""

import argparse
import os
import sys

# Runnable from inside ingestion/ or from pythonBackend/.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from DBConnection import get_connection, close_pool
from characterizations import gain_tier_tag, GAIN_TIER_TAGS, TRAIL_SHAPE_OUT_AND_BACK

# Stored length_km (round-trip for an out-and-back) above which we DON'T apply the
# range rule — a long open trail is far more likely a mislabelled linear corridor
# than a genuine >30 km round-trip out-and-back, and range under-counts linear.
ROUNDTRIP_GAIN_MAX_KM = 30.0


def backfill(dry_run: bool = False) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, length_km, elevation_gain_m,
                       min_altitude_m, max_altitude_m, tags
                FROM hikes
                WHERE trail_shape = %s
                  AND length_km <= %s
                  AND min_altitude_m IS NOT NULL
                  AND max_altitude_m IS NOT NULL
                """,
                (TRAIL_SHAPE_OUT_AND_BACK, ROUNDTRIP_GAIN_MAX_KM),
            )
            rows = cur.fetchall()
            print(f"Found {len(rows)} out-and-back hike(s) within "
                  f"{ROUNDTRIP_GAIN_MAX_KM:.0f} km round-trip.")

            changed = skipped = 0
            for row in rows:
                lo = float(row["min_altitude_m"])
                hi = float(row["max_altitude_m"])
                new_gain = round(hi - lo, 1)
                old_gain = round(float(row["elevation_gain_m"] or 0), 1)

                # Degenerate/void extremes — leave the row untouched.
                if new_gain <= 0:
                    skipped += 1
                    continue

                # Swap ONLY the gain-tier tag; every other tag (feature +
                # provenance markers like dem_elevation) is preserved. Difficulty
                # and gear are left to backfill_difficulty.py, which recomputes
                # them from the corrected gain.
                old_tags = list(row.get("tags") or [])
                new_tags = sorted(
                    {t for t in old_tags if t not in GAIN_TIER_TAGS}
                    | {gain_tier_tag(new_gain)}
                )

                if abs(new_gain - old_gain) < 0.1 and set(new_tags) == set(old_tags):
                    skipped += 1
                    continue

                arrow = "up" if new_gain > old_gain else "dn"
                if dry_run:
                    print(f"  [dry-run] {row['name']}: {old_gain:.0f} -> {new_gain:.0f} m ({arrow})")
                else:
                    cur.execute(
                        "UPDATE hikes SET elevation_gain_m = %s, tags = %s WHERE id = %s",
                        (new_gain, new_tags, str(row["id"])),
                    )
                changed += 1

        # get_connection commits on clean exit of the context manager.

    verb = "Would correct" if dry_run else "Corrected"
    print(f"\n{verb}: {changed}   unchanged/skipped: {skipped}")
    if not dry_run and changed:
        print("Next: run  python ingestion/backfill_difficulty.py  to re-derive "
              "difficulty + gear from the corrected gain.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Set out-and-back elevation gain to the noise-robust "
                    "round-trip proxy (max-min altitude range)."
    )
    ap.add_argument("--dry-run", action="store_true", help="Print what would change; write nothing.")
    args = ap.parse_args()
    try:
        backfill(dry_run=args.dry_run)
    finally:
        close_pool()
