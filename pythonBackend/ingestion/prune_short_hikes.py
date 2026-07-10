#!/usr/bin/env python3
"""
prune_short_hikes.py

Delete hikes below a minimum length. Replaces the ad-hoc "remove everything under
1 mile" DB script that ran on ONE-WAY lengths and so wrongly deleted real
out-and-backs (a 0.7 mi one-way / 1.4 mi round-trip trail read as 0.7 mi and got
cut). This runs on CORRECTED round-trip length instead.

Safety invariant — only prunes rows the distance backfill has already corrected:
it deletes WHERE length_km < threshold AND trail_shape IS NOT NULL. A NULL
trail_shape means backfill_trail_distances.py hasn't classified/doubled that row
yet, so its length_km may still be one-way — pruning it now would re-create the
exact bug that lost data. Such rows are reported and skipped, not deleted.

Pipeline position — run LAST, after the distance backfill:

    ... → migrate.py up → backfill_trail_distances.py → prune_short_hikes.py

Usage (from the pythonBackend directory):

    python ingestion/prune_short_hikes.py --dry-run          # preview, delete nothing
    python ingestion/prune_short_hikes.py                    # delete < 1.0 mi (default)
    python ingestion/prune_short_hikes.py --min-miles 0.75   # different threshold

Idempotent: deletion leaves nothing below the threshold, so a second run is a
no-op.

NOTE: deletion is destructive and has no undo without a DB backup. If you'd rather
not lose the rows, a non-destructive alternative is a query-time floor (add
`min_length_km` to HikeRepo.search / the search UI) instead of deleting — same
user-facing effect, fully reversible.
"""

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from DBConnection import get_connection, close_pool

MILE_KM = 1.609344


def prune(min_miles: float = 1.0, dry_run: bool = False) -> None:
    min_km = min_miles * MILE_KM
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Un-corrected rows whose one-way length is under the threshold — we do
            # NOT touch these; they might be out-and-backs that double to over it.
            cur.execute(
                "SELECT count(*) AS n FROM hikes "
                "WHERE length_km < %s AND trail_shape IS NULL",
                (min_km,),
            )
            uncorrected = cur.fetchone()["n"]
            if uncorrected:
                print(f"WARNING: {uncorrected} short hike(s) still have trail_shape = NULL "
                      f"(not yet corrected). Run backfill_trail_distances.py first — "
                      f"skipping them so a still-one-way out-and-back isn't wrongly deleted.")

            # Rows safe to prune: corrected AND genuinely under the threshold.
            cur.execute(
                "SELECT id, name, length_km FROM hikes "
                "WHERE length_km < %s AND trail_shape IS NOT NULL "
                "ORDER BY length_km",
                (min_km,),
            )
            victims = cur.fetchall()

            print(f"{len(victims)} corrected hike(s) under {min_miles:g} mi "
                  f"({min_km:.2f} km):")
            for v in victims:
                mi = float(v["length_km"]) * 0.621371
                print(f"  {'[dry-run] ' if dry_run else ''}delete  "
                      f"{v['name']}  ({v['length_km']:.2f} km / {mi:.2f} mi)")

            if dry_run:
                print(f"\nDry run — nothing deleted. Would delete {len(victims)}.")
                return

            if victims:
                cur.execute(
                    "DELETE FROM hikes WHERE length_km < %s AND trail_shape IS NOT NULL",
                    (min_km,),
                )

        # get_connection commits on clean exit of the context manager.

    if not dry_run:
        print(f"\nDeleted {len(victims)} hike(s) under {min_miles:g} mi.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Delete hikes shorter than a minimum length (corrected round-trip)."
    )
    ap.add_argument("--min-miles", type=float, default=1.0,
                    help="Minimum trail length in miles (default: 1.0).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be deleted; delete nothing.")
    args = ap.parse_args()
    try:
        prune(min_miles=args.min_miles, dry_run=args.dry_run)
    finally:
        close_pool()
