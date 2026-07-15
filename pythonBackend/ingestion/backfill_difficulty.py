#!/usr/bin/env python3
"""
backfill_difficulty.py

Recompute difficulty (and re-consolidate the gain-tier tag + gear_requirements)
across the DB from each hike's stored length + elevation gain.

WHY THIS EXISTS
───────────────
Two related findings from QA:
  1. Difficulty is over-rated — trails public sources call "Hard" land on
     "Expert". The cause is the Shenandoah rating→tier mapping running ~one
     tier hot, so this retunes the THRESHOLDS (recomputing with the old
     thresholds would change nothing).
  2. A "gentle_gain" tag sitting next to a Difficult label — the gain-tier tag
     was derived from the old undercounted gain. This refreshes ONLY that tag
     from the current gain, leaving every other tag (feature tags, the
     overpass_enriched / dem_elevation markers) intact.

RUN AFTER backfill_elevation.py — difficulty and the gain tier both depend on
elevation gain, so retuning against the still-undercounted gain would set the
wrong bands and the corrected gain would then re-cross trails back up.

    python ingestion/backfill_elevation.py
    python ingestion/backfill_difficulty.py --dry-run   # preview reclassification
    python ingestion/backfill_difficulty.py

THRESHOLDS
──────────
Shenandoah rating = sqrt(2 * miles * feet_of_gain). Tier cutoffs are CLI flags
so you can tune against the real distribution the dry-run prints:

    tier        rating          default cutoff
    Easy        < easy_max      50
    Moderate    < moderate_max  110
    Difficult   < difficult_max 210
    Expert      >= difficult_max

Caveat: the formula sees only length × gain, not terrain/technicality (that's
what OSM sac_scale would give and it's rarely present in this dataset). A retune
removes the SYSTEMATIC over-rating but won't match every public rating exactly.
This recomputes purely from the formula, so it CAN move a trail down as well as
up — the dry-run reports both directions.

Idempotent: deterministic given the stored length/gain and the chosen bands.
Run from inside ingestion/ (sibling imports) or from pythonBackend/.
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from DBConnection import get_connection, close_pool
from PyObjects.Hike import DifficultyLevel
from gear_inference import GearInferenceEngine
from characterizations import GAIN_TIER_TAGS, gain_tier_tag

DEFAULT_EASY_MAX = 50.0
DEFAULT_MODERATE_MAX = 110.0
DEFAULT_DIFFICULT_MAX = 210.0


def _rating(length_km: float, gain_m: float) -> float:
    miles = length_km * 0.621371
    feet = gain_m * 3.28084
    return math.sqrt(2 * miles * feet) if (miles > 0 and feet > 0) else 0.0


def _difficulty_from_rating(rating: float, easy_max, moderate_max, difficult_max) -> DifficultyLevel:
    if rating < easy_max:      return DifficultyLevel.EASY
    if rating < moderate_max:  return DifficultyLevel.MODERATE
    if rating < difficult_max: return DifficultyLevel.DIFFICULT
    return DifficultyLevel.EXPERT


def _difficulty(raw) -> DifficultyLevel:
    try:
        return DifficultyLevel[str(raw).upper()]
    except KeyError:
        return DifficultyLevel.MODERATE


def backfill(
    dry_run: bool,
    easy_max: float,
    moderate_max: float,
    difficult_max: float,
    limit: Optional[int],
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            sql = (
                "SELECT id, name, length_km, elevation_gain_m, max_altitude_m, "
                "difficulty, tags, can_camp FROM hikes ORDER BY id"
            )
            params: dict = {}
            if limit:
                sql += " LIMIT %(limit)s"
                params["limit"] = limit
            cur.execute(sql, params)
            rows = cur.fetchall()

            print(f"Processing {len(rows)} hike(s) with bands "
                  f"easy<{easy_max:g} moderate<{moderate_max:g} "
                  f"difficult<{difficult_max:g} expert>=.")

            moves: Counter = Counter()   # (old, new) name pairs
            changed = 0

            for row in rows:
                length_km = float(row["length_km"] or 0)
                gain_m = float(row["elevation_gain_m"] or 0)
                max_alt = float(row["max_altitude_m"] or 0)

                old_diff = _difficulty(row["difficulty"])
                new_diff = _difficulty_from_rating(
                    _rating(length_km, gain_m), easy_max, moderate_max, difficult_max
                )

                # Swap ONLY the gain-tier tag; keep feature tags + markers.
                old_tags = list(row.get("tags") or [])
                new_tags = sorted(
                    {t for t in old_tags if t not in GAIN_TIER_TAGS}
                    | {gain_tier_tag(gain_m)}
                )

                new_reqs = GearInferenceEngine.infer_gear_levels(
                    length_km=length_km, gain_m=gain_m, max_alt_m=max_alt,
                    difficulty=new_diff, tags=new_tags, can_camp=bool(row.get("can_camp")),
                )

                tags_changed = sorted(old_tags) != new_tags
                if new_diff == old_diff and not tags_changed:
                    continue

                changed += 1
                if new_diff != old_diff:
                    moves[(old_diff.name, new_diff.name)] += 1

                if dry_run:
                    d = "" if new_diff == old_diff else f"  {old_diff.name}→{new_diff.name}"
                    t = "  (gain-tier tag refreshed)" if tags_changed and new_diff == old_diff else ""
                    print(f"  [dry-run] {row['name']} "
                          f"({length_km:.1f} km / {gain_m:.0f} m, rating {_rating(length_km, gain_m):.0f}){d}{t}")
                    continue

                cur.execute(
                    """
                    UPDATE hikes SET
                        difficulty        = %s,
                        tags              = %s,
                        gear_requirements = %s
                    WHERE id = %s
                    """,
                    (new_diff.name, new_tags, json.dumps(new_reqs), str(row["id"])),
                )

        # get_connection commits on clean exit.

    verb = "Would change" if dry_run else "Changed"
    print(f"\n{verb} {changed} row(s).")
    if moves:
        print("Difficulty moves:")
        for (old, new), n in sorted(moves.items(), key=lambda x: -x[1]):
            arrow = "↑" if DifficultyLevel[new].value > DifficultyLevel[old].value else "↓"
            print(f"  {arrow} {old:9}→ {new:9} : {n}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Retune + recompute difficulty from stored length/gain.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--dry-run", action="store_true", help="Print changes; write nothing.")
    ap.add_argument("--easy-max", type=float, default=DEFAULT_EASY_MAX,
                    help="Rating below this = Easy.")
    ap.add_argument("--moderate-max", type=float, default=DEFAULT_MODERATE_MAX,
                    help="Rating below this = Moderate.")
    ap.add_argument("--difficult-max", type=float, default=DEFAULT_DIFFICULT_MAX,
                    help="Rating below this = Difficult; at/above = Expert.")
    ap.add_argument("--batch", type=int, default=None, metavar="N",
                    help="Process at most N hikes this run.")
    args = ap.parse_args()
    try:
        backfill(
            dry_run=args.dry_run, easy_max=args.easy_max,
            moderate_max=args.moderate_max, difficult_max=args.difficult_max,
            limit=args.batch,
        )
    finally:
        close_pool()
