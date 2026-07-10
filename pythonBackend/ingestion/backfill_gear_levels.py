#!/usr/bin/env python3
"""
backfill_gear_levels.py

One-shot maintenance script: recompute per-hike required gear LEVELS for every
hike already in the DB and write them to hikes.gear_requirements — without
re-running the OSM ingestion pipeline.

It uses the exact same logic new ingestion does
(GearInferenceEngine.infer_gear_levels), driven off each hike's stored stats +
tags, so backfilled and freshly-ingested hikes are identical.

Run from the pythonBackend directory (after applying
migrations/003_hike_gear_requirements.sql):

    python ingestion/backfill_gear_levels.py            # apply to all hikes
    python ingestion/backfill_gear_levels.py --dry-run  # print, change nothing
    python ingestion/backfill_gear_levels.py --only-empty   # skip hikes that already have some

Idempotent: running it again recomputes the same values.
"""

import argparse
import json
import os
import sys

# Runnable from inside ingestion/ or from pythonBackend/ — make the backend
# root importable either way (mirrors run_ingestion.py's path shim).
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from DBConnection import get_connection, close_pool
from PyObjects.Hike import DifficultyLevel
from gear_inference import GearInferenceEngine


def _difficulty(raw) -> DifficultyLevel:
    """DB stores difficulty as the enum NAME (e.g. 'MODERATE'). Fall back to
    MODERATE for anything unrecognized rather than crashing the whole run."""
    try:
        return DifficultyLevel[str(raw).upper()]
    except KeyError:
        return DifficultyLevel.MODERATE


def backfill(dry_run: bool = False, only_empty: bool = False) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, length_km, elevation_gain_m, max_altitude_m,
                       difficulty, tags, can_camp, gear_requirements
                FROM hikes
                """
            )
            rows = cur.fetchall()

            print(f"Found {len(rows)} hike(s).")
            updated = skipped = failed = 0

            for row in rows:
                if only_empty and row.get("gear_requirements"):
                    skipped += 1
                    continue
                try:
                    reqs = GearInferenceEngine.infer_gear_levels(
                        length_km  = float(row["length_km"] or 0),
                        gain_m     = float(row["elevation_gain_m"] or 0),
                        max_alt_m  = float(row["max_altitude_m"] or 0),
                        difficulty = _difficulty(row["difficulty"]),
                        tags       = row.get("tags") or [],
                        can_camp   = bool(row.get("can_camp")),
                    )
                except Exception as e:
                    print(f"  ! {row['name']} ({row['id']}): inference failed — {e}")
                    failed += 1
                    continue

                if dry_run:
                    cats = ", ".join(sorted(reqs.keys()))
                    print(f"  [dry-run] {row['name']}: {cats}")
                    updated += 1
                    continue

                try:
                    cur.execute(
                        "UPDATE hikes SET gear_requirements = %s WHERE id = %s",
                        (json.dumps(reqs), str(row["id"])),
                    )
                    updated += 1
                except Exception as e:
                    print(f"  ! {row['name']} ({row['id']}): update failed — {e}")
                    failed += 1

        # get_connection commits on clean exit of the context manager.

    verb = "Would update" if dry_run else "Updated"
    print(f"\n{verb}: {updated}   skipped: {skipped}   failed: {failed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill hikes.gear_requirements from stored stats.")
    ap.add_argument("--dry-run", action="store_true", help="Print what would change; write nothing.")
    ap.add_argument("--only-empty", action="store_true", help="Skip hikes that already have gear_requirements.")
    args = ap.parse_args()
    try:
        backfill(dry_run=args.dry_run, only_empty=args.only_empty)
    finally:
        # A one-shot script never triggers the app's shutdown hook, so the lazily
        # opened psycopg_pool (with its background worker thread) would otherwise
        # be torn down by the GC at interpreter exit — which is what prints the
        # "pool was not closed" warning. Close it explicitly. No-op without the pool.
        close_pool()
