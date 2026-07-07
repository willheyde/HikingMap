#!/usr/bin/env python3
"""
004_purge_legacy_gear.py

One-shot data migration that retires the legacy "specific product catalog" gear
model in favor of the generalized A+ model (functional gear_category + capability
level in items.attributes; see gear_levels.py).

Three steps, in order:

  1. STAMP  — every legacy item (no attributes.gear_category) that a user owns
              (user_items) or that is referenced by a saved trip (trip_gear) gets
              a gear_category (+ level where derivable) written into its
              attributes, converting it in place to the generalized model. The
              existing typed attrs (temp_rating_f, waterproof, …) are preserved
              so gear adequacy keeps working. Nothing is deleted here.

  2. DROP   — drop the hike_items table. Per-trail needs now live in
              hikes.gear_requirements (migration 003); nothing reads hike_items.
              Dropping it first frees the FK on the unowned catalog rows.

  3. DELETE — delete the remaining legacy catalog rows (still no gear_category =
              not owned, not in any trip): the pure product catalog nobody uses.

Before deleting anything it writes a JSON snapshot of every affected row so the
purge is recoverable.

Run from the pythonBackend directory:

    python migrations/004_purge_legacy_gear.py --dry-run   # report only, no writes
    python migrations/004_purge_legacy_gear.py             # apply

Idempotent: re-running after a successful apply stamps nothing, drops nothing,
deletes nothing.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psycopg
from DBConnection import get_connection
from gear_levels import resolve_gear_category, resolve_level


def _snapshot(cur, path: str) -> None:
    """Dump every row we're about to change or delete to a JSON file."""
    snap = {"taken_at": datetime.datetime.utcnow().isoformat()}

    cur.execute("""
        SELECT i.id, i.name, i.item_type, i.weight, i.cost, i.image_url, i.attributes
        FROM items i WHERE NOT (i.attributes ? 'gear_category')
    """)
    snap["legacy_items"] = [
        {**dict(r), "id": str(r["id"])} for r in cur.fetchall()
    ]

    cur.execute("SELECT user_id, item_id FROM user_items")
    snap["user_items"] = [
        {"user_id": str(r["user_id"]), "item_id": str(r["item_id"])} for r in cur.fetchall()
    ]

    # hike_items may already be gone on a re-run.
    try:
        cur.execute("SELECT hike_id, item_id, importance FROM hike_items")
        snap["hike_items"] = [
            {"hike_id": str(r["hike_id"]), "item_id": str(r["item_id"]), "importance": r["importance"]}
            for r in cur.fetchall()
        ]
    except psycopg.errors.UndefinedTable:
        snap["hike_items"] = None  # table already dropped

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2, default=str)
    print(f"  snapshot written -> {path}  "
          f"({len(snap['legacy_items'])} legacy items, "
          f"{len(snap['user_items'])} user_items, "
          f"{'-' if snap['hike_items'] is None else len(snap['hike_items'])} hike_items)")


def purge(dry_run: bool = False) -> None:
    snap_path = os.path.join(
        os.path.dirname(__file__),
        f"004_purge_backup_{datetime.datetime.utcnow():%Y%m%d_%H%M%S}.json",
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            _snapshot(cur, snap_path)

            # ── 1. STAMP owned / in-trip legacy items ─────────────────────────
            cur.execute("""
                SELECT DISTINCT i.id, i.name, i.item_type, i.attributes
                FROM items i
                WHERE NOT (i.attributes ? 'gear_category')
                  AND (EXISTS (SELECT 1 FROM user_items ui WHERE ui.item_id = i.id)
                       OR EXISTS (SELECT 1 FROM trip_gear tg WHERE tg.item_id = i.id))
            """)
            to_stamp = cur.fetchall()
            print(f"\n[1/3] Stamp gear_category on {len(to_stamp)} owned/in-trip legacy item(s):")
            stamped = 0
            for r in to_stamp:
                attrs = dict(r["attributes"] or {})
                cat = resolve_gear_category(r["item_type"], attrs)
                lvl = resolve_level(cat, attrs)
                new_attrs = {**attrs, "gear_category": cat}
                if lvl:
                    new_attrs["level"] = lvl
                print(f"      {r['name']:34} -> {cat}"
                      + (f" / {lvl}" if lvl else ""))
                if not dry_run:
                    cur.execute(
                        "UPDATE items SET attributes = %s::jsonb WHERE id = %s",
                        (psycopg.types.json.Jsonb(new_attrs), str(r["id"])),
                    )
                stamped += 1

            # ── 2. DROP hike_items ────────────────────────────────────────────
            print(f"\n[2/3] Drop hike_items table"
                  + (" (dry-run: skipped)" if dry_run else ""))
            if not dry_run:
                cur.execute("DROP TABLE IF EXISTS hike_items")

            # ── 3. DELETE unowned legacy catalog rows ─────────────────────────
            cur.execute("""
                SELECT count(*) AS n FROM items i
                WHERE NOT (i.attributes ? 'gear_category')
                  AND NOT EXISTS (SELECT 1 FROM user_items ui WHERE ui.item_id = i.id)
                  AND NOT EXISTS (SELECT 1 FROM trip_gear tg WHERE tg.item_id = i.id)
            """)
            n_delete = cur.fetchone()["n"]
            print(f"\n[3/3] Delete {n_delete} unowned legacy catalog item(s)"
                  + (" (dry-run: skipped)" if dry_run else ""))
            if not dry_run:
                cur.execute("""
                    DELETE FROM items i
                    WHERE NOT (i.attributes ? 'gear_category')
                      AND NOT EXISTS (SELECT 1 FROM user_items ui WHERE ui.item_id = i.id)
                      AND NOT EXISTS (SELECT 1 FROM trip_gear tg WHERE tg.item_id = i.id)
                """)

            if dry_run:
                # Don't leave a snapshot lying around for a report-only run.
                conn.rollback()
                try:
                    os.remove(snap_path)
                except OSError:
                    pass

    verb = "Would stamp / drop / delete" if dry_run else "Stamped / dropped / deleted"
    print(f"\n{verb}: {stamped} stamped, hike_items dropped, {n_delete} deleted.")
    if dry_run:
        print("Dry run - no changes committed.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Purge legacy catalog gear; migrate owned gear to the A+ model.")
    ap.add_argument("--dry-run", action="store_true", help="Report only; write nothing.")
    args = ap.parse_args()
    purge(dry_run=args.dry_run)
