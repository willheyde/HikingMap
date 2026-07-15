#!/usr/bin/env python3
"""
backfill_elevation.py

Re-measure elevation gain (and min/max altitude) for stored hikes from a DEM
instead of OSM node `ele` tags.

WHY THIS EXISTS
───────────────
Ingest computes gain in characterizations.compute_metrics by summing the
positive delta between consecutive geometry points — but ONLY where both points
carry an OSM `ele` tag, treating a missing value as no-data. In the regional OSM
relations most nodes have no `ele` at all, so the vast majority of segments
contribute 0 and gain is systematically undercounted (a "gentle_gain" tag ends
up next to a Difficult trail). This is the root cause; recomputing from the same
sparse OSM elevations can't fix it.

This script does NOT re-fetch trail geometry (no Overpass). It reads the
ALREADY-STORED path for each hike and queries an elevation service for every
coordinate, then recomputes:
    elevation_gain_m   sum of positive deltas along the path (per segment for a
                       MultiLineString, so the empty gaps between disconnected
                       fragments are never counted)
    min_altitude_m     min sampled elevation
    max_altitude_m     max sampled elevation

It deliberately does NOT touch difficulty, the gain-tier tag, or
gear_requirements — those are derived values and are re-consolidated from the
corrected gain by backfill_difficulty.py, which is meant to run immediately
after this. Run order for a data fix (no re-ingest needed):

    python ingestion/backfill_elevation.py --dry-run --batch 5   # sanity first
    python ingestion/backfill_elevation.py                       # whole DB
    python ingestion/backfill_difficulty.py --dry-run            # preview retune
    python ingestion/backfill_difficulty.py

ELEVATION SOURCE
────────────────
DEFAULT — Copernicus GLO-30 DEM (recommended). A public 30 m global DEM of
1°×1° Cloud-Optimized GeoTIFF tiles on AWS Open Data, no login required. Two
ways to read it, both handled by --dem-dir / --dem-url-base:

    # Zero download — GDAL /vsicurl range-reads only the blocks each trail
    # touches, straight from S3 (no daily cap, whole DB in minutes):
    python ingestion/backfill_elevation.py

    # Fully offline — point at pre-downloaded tiles (falls back to /vsicurl
    # for any tile not present locally):
    python ingestion/backfill_elevation.py --dem-dir ./copernicus_dem
    # tiles: https://copernicus-dem-30m.s3.amazonaws.com/
    #   Copernicus_DSM_COG_10_N35_00_W083_00_DEM/..._DEM.tif  (SW-corner named)

ALTERNATIVE — opentopodata HTTP endpoint via --http --elevation-url. A
self-hosted instance (Docker) works, but SRTM-30m needs a NASA Earthdata login;
the public instance is rate-limited (1 req/s, 1000 calls/day) and too small for
the full set. Prefer the Copernicus DEM above.

Accuracy caveat: 30 m DEM sampled at the geometry's point spacing. Gain goes
from far-too-low to close-to-real for almost every trail, but a switchback-y
trail with sparse geometry can still slightly under-read. Much better, not
perfect.

IDEMPOTENCY
───────────
The recompute is deterministic (same geometry + same DEM → same gain), so a
re-run is always safe. A marker tag ("dem_elevation", same convention as
"overpass_enriched") is added to each corrected row so subsequent runs skip it
by default — letting a slow public-API run be done in resumable --batch chunks.
Pass --force to re-process rows that already carry the marker.

Run from inside ingestion/ (sibling imports) or from pythonBackend/.
"""

import argparse
import json
import math
import os
import sys
import time
from glob import glob
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

try:
    import rasterio               # only needed for the local/vsicurl DEM mode
except ImportError:               # pragma: no cover
    rasterio = None

from DBConnection import get_connection, close_pool
from characterizations import haversine

# Provenance + idempotency marker. Same visible-tag convention as
# "overpass_enriched" already in the dataset. Preserved by backfill_difficulty.py.
DEM_MARKER = "dem_elevation"

DEFAULT_ELEVATION_URL = "http://localhost:5000/v1/srtm30m"
# opentopodata's per-request location cap (public instance = 100). Self-hosted
# can go higher, but 100 is a safe default that works everywhere.
DEFAULT_BATCH_SIZE = 100
# Coordinates rounded to this many decimals before de-duping within a trail
# (~1 m at 5 dp), so repeated/near-identical vertices don't cost extra queries.
_COORD_DP = 5


def _segments(geom: dict) -> list:
    """Stored geometry → list of [lon, lat, ...] segments. LineString is one
    segment; MultiLineString is several; anything else → []."""
    coords = (geom or {}).get("coordinates") or []
    gtype = (geom or {}).get("type")
    if gtype == "MultiLineString":
        return [seg for seg in coords if seg]
    if gtype == "LineString":
        return [coords] if coords else []
    return []


def _point_key(lon: float, lat: float) -> tuple:
    return (round(lat, _COORD_DP), round(lon, _COORD_DP))


def _fetch_elevations(
    keys: list[tuple],
    client: httpx.Client,
    url: str,
    batch_size: int,
    sleep: float,
) -> dict[tuple, Optional[float]]:
    """
    Queries the elevation service for unique (lat, lon) keys. Returns a map
    key -> elevation_m (None where the service has no coverage / returns null).
    Batches at batch_size; sleeps between batches when sleep > 0.
    """
    result: dict[tuple, Optional[float]] = {}
    for i in range(0, len(keys), batch_size):
        chunk = keys[i : i + batch_size]
        locations = "|".join(f"{lat},{lon}" for (lat, lon) in chunk)
        resp = client.post(url, data={"locations": locations})
        resp.raise_for_status()
        payload = resp.json()
        for key, entry in zip(chunk, payload.get("results", [])):
            ele = entry.get("elevation") if isinstance(entry, dict) else None
            result[key] = float(ele) if ele is not None else None
        if sleep > 0 and i + batch_size < len(keys):
            time.sleep(sleep)
    return result


# ── Local / vsicurl DEM mode (Copernicus GLO-30) ──────────────────────────────
#
# Preferred over the HTTP elevation service: no daily cap, no Docker, no NASA
# Earthdata login. Copernicus GLO-30 is a public 30 m global DEM of 1°×1°
# Cloud-Optimized GeoTIFF tiles on AWS Open Data. Because they're COGs, GDAL can
# range-read only the blocks a trail touches straight over HTTP (/vsicurl/), so
# the whole DB can be sampled with zero bulk download — or point --dem-dir at
# pre-downloaded tiles for a fully offline run.

DEFAULT_DEM_URL_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"


def _dem_tile_id(lat: float, lon: float) -> str:
    """Copernicus GLO-30 1° tile id for a point, e.g. (35.3, -82.8) ->
    'N35_00_W083_00' (named by the tile's SW corner)."""
    la = int(math.floor(lat))
    lo = int(math.floor(lon))
    ns = f"N{la:02d}" if la >= 0 else f"S{abs(la):02d}"
    ew = f"E{lo:03d}" if lo >= 0 else f"W{abs(lo):03d}"
    return f"{ns}_00_{ew}_00"


def _dem_object_path(tile_id: str) -> str:
    name = f"Copernicus_DSM_COG_10_{tile_id}_DEM"
    return f"{name}/{name}.tif"


class _DemTiles:
    """
    Opens Copernicus GLO-30 tiles by id. Prefers a local .tif in tile_dir; if
    absent and url_base is set, opens the tile remotely via GDAL /vsicurl/ (COG
    range reads). Caches opened datasets and misses. `used_remote` tracks whether
    any tile was served over the network (so the run can report it).
    """

    def __init__(self, tile_dir: Optional[str], url_base: Optional[str]):
        self._dir = tile_dir
        self._url_base = url_base.rstrip("/") if url_base else None
        self._open: dict[str, object] = {}
        self.missing: set[str] = set()
        self.used_remote = False

    def get(self, tile_id: str):
        if tile_id in self._open:
            return self._open[tile_id]
        ds = None
        if self._dir:
            matches = glob(os.path.join(self._dir, f"*{tile_id}*.tif"))
            if matches:
                ds = rasterio.open(matches[0])
        if ds is None and self._url_base:
            try:
                ds = rasterio.open(f"/vsicurl/{self._url_base}/{_dem_object_path(tile_id)}")
                self.used_remote = True
            except Exception:
                ds = None
        if ds is None:
            self.missing.add(tile_id)
        self._open[tile_id] = ds
        return ds

    def close(self):
        for ds in self._open.values():
            if ds is not None:
                ds.close()


def _sample_elevations_local(keys: list[tuple], tiles: "_DemTiles") -> dict[tuple, Optional[float]]:
    """Sample the DEM at each (lat, lon) key. Groups by tile so each raster is
    read once. None where the tile is unavailable or the value is nodata."""
    result: dict[tuple, Optional[float]] = {}
    by_tile: dict[str, list[tuple]] = {}
    for key in keys:
        lat, lon = key
        by_tile.setdefault(_dem_tile_id(lat, lon), []).append(key)

    for tile_id, klist in by_tile.items():
        ds = tiles.get(tile_id)
        if ds is None:
            for key in klist:
                result[key] = None
            continue
        nodata = ds.nodata
        xys = [(lon, lat) for (lat, lon) in klist]   # rasterio wants (x=lon, y=lat)
        for key, val in zip(klist, ds.sample(xys)):
            v = float(val[0])
            result[key] = None if (nodata is not None and v == nodata) else v
    return result


def _recompute(segments: list, ele_by_key: dict, min_delta: float):
    """
    (gain_m, min_alt_m, max_alt_m, covered, total) from sampled elevations.
    Positive deltas only, per segment (never across a MultiLineString gap);
    deltas below min_delta are ignored as DEM noise.
    """
    gain = 0.0
    alts: list[float] = []
    covered = total = 0
    for seg in segments:
        prev: Optional[float] = None
        for pt in seg:
            total += 1
            ele = ele_by_key.get(_point_key(pt[0], pt[1]))
            if ele is None:
                prev = None  # break the delta chain across a coverage hole
                continue
            covered += 1
            alts.append(ele)
            if prev is not None:
                delta = ele - prev
                if delta >= min_delta:
                    gain += delta
            prev = ele
    if not alts:
        return None, None, None, covered, total
    return gain, min(alts), max(alts), covered, total


def backfill(
    dry_run: bool,
    force: bool,
    limit: Optional[int],
    url: str,
    batch_size: int,
    sleep: float,
    min_delta: float,
    dem_dir: Optional[str],
    dem_url_base: Optional[str],
) -> None:
    # DEM mode (local tiles and/or /vsicurl Copernicus) is active whenever a
    # tile dir or a url base is given; otherwise fall back to the HTTP
    # elevation service. DEM mode is the recommended path.
    use_dem = bool(dem_dir) or bool(dem_url_base)
    if use_dem and rasterio is None:
        print("ERROR: rasterio is not installed (needed for DEM mode). "
              "Run:  pip install rasterio")
        return
    if dem_dir and not os.path.isdir(dem_dir):
        print(f"NOTE: --dem-dir '{dem_dir}' does not exist; relying on /vsicurl "
              f"remote reads from {dem_url_base or '(none)'}.")

    dem_tiles = _DemTiles(dem_dir, dem_url_base) if use_dem else None
    client = None if use_dem else httpx.Client(
        timeout=30.0, headers={"User-Agent": "HikeBuilder/1.0"}
    )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                where = "" if force else "WHERE NOT (%(marker)s = ANY(tags))"
                sql = (
                    "SELECT id, name, geometry, tags, elevation_gain_m, "
                    "min_altitude_m, max_altitude_m "
                    f"FROM hikes {where} ORDER BY id"
                )
                params = {} if force else {"marker": DEM_MARKER}
                if limit:
                    sql += " LIMIT %(limit)s"
                    params["limit"] = limit
                cur.execute(sql, params)
                rows = cur.fetchall()

                src = ("DEM " + ("local+vsicurl" if dem_dir else "vsicurl")) if use_dem else f"HTTP {url}"
                print(f"Found {len(rows)} hike(s) to process"
                      f"{'' if force else ' (unmarked only)'} — source: {src}.")

                updated = skipped = 0
                for row in rows:
                    geom = row["geometry"]
                    if isinstance(geom, str):
                        geom = json.loads(geom)
                    segments = _segments(geom or {})
                    if not segments:
                        print(f"  SKIP  {row['name']}: no usable geometry")
                        skipped += 1
                        continue

                    keys = sorted({
                        _point_key(pt[0], pt[1])
                        for seg in segments for pt in seg
                        if len(pt) >= 2
                    })
                    try:
                        if use_dem:
                            ele_by_key = _sample_elevations_local(keys, dem_tiles)
                        else:
                            ele_by_key = _fetch_elevations(keys, client, url, batch_size, sleep)
                    except Exception as e:
                        print(f"  ! {row['name']} ({row['id']}): elevation lookup failed — {e}")
                        skipped += 1
                        continue

                    gain, min_alt, max_alt, covered, total = _recompute(
                        segments, ele_by_key, min_delta
                    )
                    if gain is None:
                        print(f"  SKIP  {row['name']}: no elevation coverage "
                              f"(0/{total} points) — left as-is")
                        skipped += 1
                        continue

                    old_gain = float(row["elevation_gain_m"] or 0)
                    new_gain = round(gain, 1)
                    cov_pct = 100 * covered / total if total else 0

                    if dry_run:
                        print(f"  [dry-run] {row['name']}: gain {old_gain:.0f}→{new_gain:.0f} m "
                              f"| alt {min_alt:.0f}–{max_alt:.0f} m | coverage {cov_pct:.0f}%")
                        updated += 1
                        continue

                    new_tags = sorted(set(row.get("tags") or []) | {DEM_MARKER})
                    cur.execute(
                        """
                        UPDATE hikes SET
                            elevation_gain_m = %s,
                            min_altitude_m   = %s,
                            max_altitude_m   = %s,
                            tags             = %s
                        WHERE id = %s
                        """,
                        (new_gain, round(min_alt, 1), round(max_alt, 1),
                         new_tags, str(row["id"])),
                    )
                    print(f"  OK    {row['name']}: gain {old_gain:.0f}→{new_gain:.0f} m "
                          f"(coverage {cov_pct:.0f}%)")
                    updated += 1

            # get_connection commits on clean exit.
    finally:
        if client is not None:
            client.close()
        if dem_tiles is not None:
            if dem_tiles.missing:
                print(f"\nNote: {len(dem_tiles.missing)} DEM tile(s) unavailable "
                      f"(no local file and no remote): {', '.join(sorted(dem_tiles.missing))}")
            dem_tiles.close()

    verb = "Would update" if dry_run else "Updated"
    print(f"\n{verb}: {updated}   skipped: {skipped}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Re-measure elevation gain/altitude from a DEM (opentopodata).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--dry-run", action="store_true", help="Print changes; write nothing.")
    ap.add_argument("--force", action="store_true",
                    help="Re-process rows already marked '%s' (default skips them)." % DEM_MARKER)
    ap.add_argument("--batch", type=int, default=None, metavar="N",
                    help="Process at most N hikes this run (resumable chunking).")
    ap.add_argument("--elevation-url", default=DEFAULT_ELEVATION_URL, metavar="URL",
                    help="opentopodata-compatible endpoint.")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, metavar="N",
                    help="Coordinates per elevation request.")
    ap.add_argument("--sleep", type=float, default=0.0, metavar="SEC",
                    help="Seconds between elevation requests (use 1.0 for the public API).")
    ap.add_argument("--min-delta", type=float, default=0.0, metavar="M",
                    help="Ignore per-step gains below this (m) as DEM noise.")
    # ── DEM mode is the DEFAULT (recommended): Copernicus GLO-30 tiles, read
    #    locally from --dem-dir and/or remotely via /vsicurl. Use --http to fall
    #    back to an opentopodata HTTP endpoint instead. ──────────────────────────
    ap.add_argument("--dem-dir", default=None, metavar="DIR",
                    help="Read Copernicus GLO-30 .tif tiles from here first "
                         "(missing tiles fall back to --dem-url-base via /vsicurl).")
    ap.add_argument("--dem-url-base", default=DEFAULT_DEM_URL_BASE, metavar="URL",
                    help="S3/HTTP base for Copernicus GLO-30 COG tiles, read via "
                         "/vsicurl when a tile isn't local.")
    ap.add_argument("--no-vsicurl", action="store_true",
                    help="Disable /vsicurl remote reads (use only local --dem-dir tiles).")
    ap.add_argument("--http", action="store_true",
                    help="Use the opentopodata HTTP endpoint (--elevation-url) "
                         "instead of the default local/Copernicus DEM.")
    args = ap.parse_args()

    if args.http:
        dem_dir = dem_url_base = None            # HTTP opentopodata mode
    else:
        dem_dir = args.dem_dir
        dem_url_base = None if args.no_vsicurl else (args.dem_url_base or None)
        if not dem_dir and not dem_url_base:
            ap.error("DEM mode needs a source: pass --dem-dir, or don't use "
                     "--no-vsicurl (so /vsicurl can read tiles remotely), or use --http.")
    try:
        backfill(
            dry_run=args.dry_run, force=args.force, limit=args.batch,
            url=args.elevation_url, batch_size=args.batch_size,
            sleep=args.sleep, min_delta=args.min_delta,
            dem_dir=dem_dir, dem_url_base=dem_url_base,
        )
    finally:
        close_pool()
