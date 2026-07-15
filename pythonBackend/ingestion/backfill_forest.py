#!/usr/bin/env python3
"""
backfill_forest.py

Tag hikes that run through tree cover with a `forest` tag, by sampling the ESA
WorldCover 10 m land-cover raster at each trail's stored geometry points.

WHY THIS EXISTS
───────────────
"Wooded / forested" is a searchable feature users ask for ("best wooded hikes
near me"), and the parser already maps wooded/woods/forest → a required `forest`
tag — but NOTHING ever assigned that tag. The ingestion pull only fetches
hiking route relations (osm_client.QUERY) with skeleton member geometry, so it
carries no land-cover at all, and overpass_enrichment.py has no forest detector.
So every "wooded" search hard-failed and fell back. This closes that gap.

Forest is a CONTAINMENT question (does the trail run *through* woods?), not a
nearby-point-of-interest one, so instead of a per-trail Overpass loop this
samples a land-cover raster at the trail's own points — the same shape as
backfill_elevation.py, fully offline, whole DB in minutes.

WorldCover is used (not OSM landuse=forest) because it directly measures tree
CANOPY at 10 m with complete coverage — the thing "wooded" actually means —
whereas OSM forest polygons are administrative and patchy. NOTE: this makes
`forest` a RASTER-derived tag, unlike the OSM-derived feature tags from
overpass_enrichment. It is deliberately NOT in that module's DETECTORS /
VERIFIABLE_TAGS, so an enrichment run will preserve it rather than strip it.

DATA YOU NEED (one-time download)
─────────────────────────────────
ESA WorldCover 2021 v200 GeoTIFF tiles covering your region, into --tile-dir.
Tiles are 3°×3°, named by their SW corner, e.g. ESA_WorldCover_10m_2021_v200_
N33W084_Map.tif. Public, free, on AWS Open Data (no credentials):

    aws s3 cp --no-sign-request \
      s3://esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_N33W084_Map.tif .

For the current NC + RI dataset the covering tiles are:
    NC : N33W084 N33W081 N33W078 N36W084 N36W081 N36W078
    RI : N39W072  (plus N42W072 for the sliver above 42°N)
Grab only the ones your trails actually fall in — missing tiles just mean those
points count as "no coverage" (the run reports coverage % per trail).

USAGE (run from inside ingestion/ or from pythonBackend/)
    python ingestion/backfill_forest.py --tile-dir ./worldcover --dry-run --batch 20
    python ingestion/backfill_forest.py --tile-dir ./worldcover

Idempotent: deterministic given the geometry + tiles + threshold. It is
AUTHORITATIVE for `forest` — a re-run adds the tag to trails now over threshold
and removes a stale `forest` from trails now under it, touching no other tag.

Requires rasterio (`pip install rasterio` — bundles GDAL via wheels).
"""

import argparse
import json
import math
import os
import sys
from glob import glob
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from DBConnection import get_connection, close_pool

try:
    import rasterio
except ImportError:  # pragma: no cover - friendly guidance, not a stack trace
    rasterio = None

FOREST_TAG = "forest"

# WorldCover class codes. 10 = Tree cover; 0 = nodata / outside coverage.
# 95 (mangroves) is folded in as tree canopy for coastal trails; everything
# else (shrubland/grassland/cropland/built/bare/water/wetland/…) is not.
DEFAULT_TREE_CLASSES = "10,95"
WORLDCOVER_NODATA = 0


def _segments(geom: dict) -> list:
    coords = (geom or {}).get("coordinates") or []
    gtype = (geom or {}).get("type")
    if gtype == "MultiLineString":
        return [seg for seg in coords if seg]
    if gtype == "LineString":
        return [coords] if coords else []
    return []


def _tile_id(lat: float, lon: float) -> str:
    """WorldCover 3° tile id for a point, e.g. (35.5, -82.5) -> 'N33W084'."""
    lat_sw = int(math.floor(lat / 3.0) * 3)
    lon_sw = int(math.floor(lon / 3.0) * 3)
    ns = f"N{lat_sw:02d}" if lat_sw >= 0 else f"S{abs(lat_sw):02d}"
    ew = f"E{lon_sw:03d}" if lon_sw >= 0 else f"W{abs(lon_sw):03d}"
    return f"{ns}{ew}"


class _TileCache:
    """Lazily opens WorldCover tile rasters from tile_dir, one per tile id.
    Caches misses (None) so a missing tile isn't globbed again every point."""

    def __init__(self, tile_dir: str):
        self._dir = tile_dir
        self._open: dict[str, object] = {}
        self.missing: set[str] = set()

    def get(self, tile_id: str):
        if tile_id in self._open:
            return self._open[tile_id]
        matches = glob(os.path.join(self._dir, f"*{tile_id}*.tif"))
        ds = rasterio.open(matches[0]) if matches else None
        if ds is None:
            self.missing.add(tile_id)
        self._open[tile_id] = ds
        return ds

    def close(self):
        for ds in self._open.values():
            if ds is not None:
                ds.close()


def _sample_trail(segments: list, tiles: _TileCache, tree_classes: set[int]):
    """
    (tree_fraction, covered, total) for a trail. Groups the trail's points by
    tile so each raster is sampled in one batched call. Points whose tile file
    is missing, or that read as nodata, count as uncovered.
    """
    by_tile: dict[str, list[tuple[float, float]]] = {}
    total = 0
    for seg in segments:
        for pt in seg:
            if len(pt) < 2:
                continue
            total += 1
            lon, lat = float(pt[0]), float(pt[1])
            by_tile.setdefault(_tile_id(lat, lon), []).append((lon, lat))

    covered = tree = 0
    for tile_id, xys in by_tile.items():
        ds = tiles.get(tile_id)
        if ds is None:
            continue
        for val in ds.sample(xys):   # rasterio wants (x=lon, y=lat)
            cls = int(val[0])
            if cls == WORLDCOVER_NODATA:
                continue
            covered += 1
            if cls in tree_classes:
                tree += 1

    frac = (tree / covered) if covered else 0.0
    return frac, covered, total


def backfill(
    dry_run: bool,
    tile_dir: str,
    tree_fraction: float,
    tree_classes: set[int],
    min_coverage: float,
    limit: Optional[int],
) -> None:
    if rasterio is None:
        print("ERROR: rasterio is not installed. Run:  pip install rasterio")
        return
    if not os.path.isdir(tile_dir):
        print(f"ERROR: --tile-dir '{tile_dir}' does not exist. "
              f"Download WorldCover tiles into it first (see module docstring).")
        return

    tiles = _TileCache(tile_dir)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                sql = "SELECT id, name, geometry, tags FROM hikes ORDER BY id"
                params: dict = {}
                if limit:
                    sql += " LIMIT %(limit)s"
                    params["limit"] = limit
                cur.execute(sql, params)
                rows = cur.fetchall()

                print(f"Processing {len(rows)} hike(s)  "
                      f"(tree if >= {tree_fraction:.0%} of covered points are "
                      f"classes {sorted(tree_classes)}).")

                added = removed = skipped = 0
                for row in rows:
                    geom = row["geometry"]
                    if isinstance(geom, str):
                        geom = json.loads(geom)
                    segments = _segments(geom or {})
                    if not segments:
                        skipped += 1
                        continue

                    frac, covered, total = _sample_trail(segments, tiles, tree_classes)
                    cov_pct = covered / total if total else 0.0
                    if cov_pct < min_coverage:
                        print(f"  SKIP  {row['name']}: only {cov_pct:.0%} raster coverage "
                              f"({covered}/{total}) — need tiles or trust threshold; left as-is")
                        skipped += 1
                        continue

                    is_forest = frac >= tree_fraction
                    old_tags = set(row.get("tags") or [])
                    has_tag = FOREST_TAG in old_tags

                    if is_forest == has_tag:
                        continue  # already correct

                    new_tags = sorted(
                        old_tags | {FOREST_TAG} if is_forest else old_tags - {FOREST_TAG}
                    )
                    verb = "+forest" if is_forest else "-forest"
                    if is_forest:
                        added += 1
                    else:
                        removed += 1

                    if dry_run:
                        print(f"  [dry-run] {verb:8} {row['name']}: "
                              f"{frac:.0%} tree over {covered} pts")
                        continue

                    cur.execute(
                        "UPDATE hikes SET tags = %s WHERE id = %s",
                        (new_tags, str(row["id"])),
                    )
                    print(f"  {verb:8} {row['name']}: {frac:.0%} tree over {covered} pts")

            # get_connection commits on clean exit.

        if tiles.missing:
            print(f"\nNote: {len(tiles.missing)} tile(s) referenced but not found in "
                  f"{tile_dir}: {', '.join(sorted(tiles.missing))}")
        verb = "Would tag" if dry_run else "Tagged"
        print(f"\n{verb} +forest: {added}   -forest (cleared stale): {removed}   skipped: {skipped}")
    finally:
        tiles.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Tag forested hikes by sampling ESA WorldCover land cover.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--dry-run", action="store_true", help="Print changes; write nothing.")
    ap.add_argument("--tile-dir", default="./worldcover", metavar="DIR",
                    help="Directory holding the ESA WorldCover .tif tiles.")
    ap.add_argument("--tree-fraction", type=float, default=0.5, metavar="F",
                    help="Fraction of covered points that must be tree cover to tag forest.")
    ap.add_argument("--tree-classes", default=DEFAULT_TREE_CLASSES, metavar="CSV",
                    help="WorldCover class codes counted as tree canopy.")
    ap.add_argument("--min-coverage", type=float, default=0.5, metavar="F",
                    help="Skip a trail if fewer than this fraction of points have raster coverage.")
    ap.add_argument("--batch", type=int, default=None, metavar="N",
                    help="Process at most N hikes this run.")
    args = ap.parse_args()
    tree_classes = {int(c) for c in args.tree_classes.split(",") if c.strip()}
    try:
        backfill(
            dry_run=args.dry_run, tile_dir=args.tile_dir,
            tree_fraction=args.tree_fraction, tree_classes=tree_classes,
            min_coverage=args.min_coverage, limit=args.batch,
        )
    finally:
        close_pool()
