#!/usr/bin/env python3
"""
diagnose_elevation.py — READ-ONLY elevation diagnostics + DEM calibration.

Answers "was the elevation re-ingestion a net negative?" from data. This script
writes NOTHING to the database (SELECT-only) and is safe to run against prod.

Two parts:

  Part A (DB only) — the distribution of stored elevation_gain_m, gain-per-km,
      and difficulty tiers across the catalog, plus every row flagged by
      characterizations.find_data_quality_issues() (implausible grade; flat tag
      vs hard difficulty; flat tag vs high-gain tag). No DEM needed.

  Part B (needs a DEM) — re-measures a small set of GROUND-TRUTH trails (known
      real-world gain) against the known value, so you can see what actually
      helps. Per trail it prints:
        * OSM-ele — gain from the stored OSM node elevations (the 3rd coordinate
          in the geometry), plus their COVERAGE %. Tests whether the old
          OSM-tag elevations beat the DEM where they exist.
        * a --min-delta sweep in three flavours:
            - vertices  : sample the DEM only at the stored OSM vertices (what
                          production does)
            - densified : interpolate a sample every ~25 m first (defeats
                          sparse-vertex net-out)
            - smoothed  : moving-average the densified profile, then sum —
                          denoise WITHOUT the hysteresis tail-shave
      Auto-skipped if rasterio / DEM tiles are unavailable.

There is no stored "before" snapshot — the re-run overwrote elevation_gain_m in
place — so a literal before/after diff needs a pre-run DB dump. Absent that,
Part B's calibration-against-known is the substitute. If you DO have a pre-run
dump, load it into a scratch DB and run Part A against both to diff.

Run from pythonBackend/ (or ingestion/):
    python ingestion/diagnose_elevation.py                  # Part A + B (vsicurl DEM)
    python ingestion/diagnose_elevation.py --dem-dir TILES  # offline DEM tiles
    python ingestion/diagnose_elevation.py --no-calibrate   # Part A only
"""

import argparse
import json
import os
import sys

# Runnable from inside ingestion/ or from pythonBackend/.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from DBConnection import get_connection, close_pool
from PyObjects.Hike import DifficultyLevel
from characterizations import (
    find_data_quality_issues,
    gain_tier_tag,
    haversine,
)
# DEM internals reused verbatim so calibration matches production exactly. The
# 'vertices' column's hysteresis mirrors _recompute; we reimplement it locally
# (_hysteresis_gain) so the same accumulator can run on a smoothed profile too.
from backfill_elevation import (
    _segments,
    _point_key,
    _sample_elevations_local,
    _DemTiles,
    rasterio,
    DEFAULT_DEM_URL_BASE,
)

# min-delta values swept in calibration. 0 = the OLD raw-sum behaviour (no band);
# 8 = today's default. 3/5 probe whether a softer band recovers real climbs.
SWEEP_MIN_DELTAS = [0.0, 3.0, 5.0, 8.0]
# Spacing (m) for densified re-sampling — insert a sample every ~this far along
# each segment so a sustained grade between sparse OSM vertices isn't missed.
DENSIFY_SPACING_M = 25.0
# Centered moving-average window (in sample points) for the 'smoothed' column —
# smooths the elevation PROFILE before summing, instead of the hard hysteresis
# band, so noise is removed without shaving the tail off every real climb. At
# 25 m spacing, 5 points ≈ a 125 m window.
SMOOTH_WINDOW_PTS = 5

# (name ILIKE substring, known real-world gain in m or None, note). Edit freely.
GROUND_TRUTH = [
    ("Spence Ridge",      250, "guides: ~817-873 ft climb out; strenuous"),
    ("Devil's Hole",      305, "AllTrails: ~1000 ft"),
    ("McMullen Creek",     12, "flat paved greenway (~30-45 ft)"),
    ("Rattlesnake Lodge", 225, "AllTrails ~600-882 ft; distance stored one-way"),
    ("Mountains-to-Sea", None, "linear thru-trail — consistency check only"),
]


# ── Part A: DB distribution + quality flags ────────────────────────────────────

def _bucket(gain: float) -> str:
    for hi, label in [(50, "<50"), (100, "50-100"), (200, "100-200"),
                      (400, "200-400"), (800, "400-800"), (1500, "800-1500")]:
        if gain < hi:
            return label
    return "1500+"


def distribution() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, length_km, elevation_gain_m, difficulty, tags "
            "FROM hikes"
        )
        rows = cur.fetchall()

    n = len(rows)
    print(f"\n=== Part A — catalog distribution ({n} hikes) ===")
    if not n:
        print("  (no rows)")
        return

    buckets: dict[str, int] = {}
    diffs:   dict[str, int] = {}
    tiers:   dict[str, int] = {}
    grades:  list[float] = []
    flagged: list[tuple] = []

    for r in rows:
        gain = float(r["elevation_gain_m"] or 0)
        length = float(r["length_km"] or 0)
        buckets[_bucket(gain)] = buckets.get(_bucket(gain), 0) + 1
        diffs[str(r["difficulty"])] = diffs.get(str(r["difficulty"]), 0) + 1
        tiers[gain_tier_tag(gain)] = tiers.get(gain_tier_tag(gain), 0) + 1
        if length > 0:
            grades.append((gain * 3.28084) / (length * 0.621371))  # ft/mi

        try:
            dl = DifficultyLevel[str(r["difficulty"]).upper()]
        except (KeyError, AttributeError):
            dl = DifficultyLevel.MODERATE
        issues = find_data_quality_issues(length, gain, dl, list(r["tags"] or []))
        if issues:
            flagged.append((r["name"], length, gain, issues))

    def _show(title, d):
        print(f"\n  {title}")
        for k in sorted(d, key=lambda k: (-d[k], k)):
            print(f"    {k:<14} {d[k]:>5}  ({d[k]*100//n:>2}%)")

    _show("elevation_gain_m buckets", buckets)
    _show("gain-tier tag (from stored gain)", tiers)
    _show("difficulty", diffs)

    if grades:
        grades.sort()
        def pct(p): return grades[min(len(grades) - 1, int(len(grades) * p))]
        print("\n  gain per mile (ft/mi):")
        print(f"    median {pct(0.5):>7.0f}   p90 {pct(0.9):>7.0f}   "
              f"p99 {pct(0.99):>7.0f}   max {grades[-1]:>7.0f}")

    print(f"\n  data-quality flags: {len(flagged)} row(s) "
          f"({len(flagged)*100//n}%) fail find_data_quality_issues()")
    for name, length, gain, issues in flagged[:25]:
        print(f"    - {name} ({length:.1f} km, {gain:.0f} m): {'; '.join(issues)}")
    if len(flagged) > 25:
        print(f"    … and {len(flagged) - 25} more")


# ── Part B: DEM calibration against known trails ───────────────────────────────

def _densify(segments: list, spacing_m: float) -> list:
    """Interpolate extra [lon, lat] points so consecutive samples are ≤spacing_m
    apart — defeats the net-out of a real grade sampled only at sparse vertices."""
    out = []
    for seg in segments:
        if len(seg) < 2:
            out.append(seg)
            continue
        dense = [seg[0]]
        for i in range(1, len(seg)):
            lon0, lat0 = seg[i - 1][0], seg[i - 1][1]
            lon1, lat1 = seg[i][0], seg[i][1]
            d = haversine(lat0, lon0, lat1, lon1)
            steps = int(d // spacing_m)
            for k in range(1, steps + 1):
                f = (k * spacing_m) / d
                dense.append([lon0 + (lon1 - lon0) * f, lat0 + (lat1 - lat0) * f])
            dense.append(seg[i])
        out.append(dense)
    return out


def _hysteresis_gain(seqs: list, min_delta: float):
    """Gain from ordered elevation sequences (one per segment), same hysteresis
    accumulator as backfill_elevation._recompute — but on a plain list of
    Optional[float], so it can run on a SMOOTHED profile. Returns
    (gain, covered, total)."""
    gain = 0.0
    covered = total = 0
    for seq in seqs:
        base = None
        for ele in seq:
            total += 1
            if ele is None:
                base = None
                continue
            covered += 1
            if base is None:
                base = ele
                continue
            d = ele - base
            if d >= min_delta:
                gain += d
                base = ele
            elif d <= -min_delta:
                base = ele
    return gain, covered, total


def _ascent_descent(seqs: list, min_delta: float):
    """One-way ASCENT and DESCENT magnitude (same hysteresis band). For an
    out-and-back, the round-trip gain a hiker actually experiences is
    ascent + descent — the descents you walk on the way out become climbs on the
    way back. The stored gain is ascent only, which understates any trail whose
    stored one-way direction runs net-downhill (e.g. Spence Ridge descending into
    the gorge)."""
    up = down = 0.0
    for seq in seqs:
        base = None
        for ele in seq:
            if ele is None:
                base = None
                continue
            if base is None:
                base = ele
                continue
            d = ele - base
            if d >= min_delta:
                up += d
                base = ele
            elif d <= -min_delta:
                down += -d
                base = ele
    return up, down


def _smooth(seqs: list, window: int) -> list:
    """Centered moving average over each contiguous non-None run; None (a
    coverage hole) is preserved as a break so smoothing never bridges a gap."""
    if window <= 1:
        return seqs
    half = window // 2
    out = []
    for seq in seqs:
        s = [None] * len(seq)
        i, n = 0, len(seq)
        while i < n:
            if seq[i] is None:
                i += 1
                continue
            j = i
            while j < n and seq[j] is not None:
                j += 1
            run = seq[i:j]
            for k in range(len(run)):
                lo, hi = max(0, k - half), min(len(run), k + half + 1)
                s[i + k] = sum(run[lo:hi]) / (hi - lo)
            i = j
        out.append(s)
    return out


def _dem_sequences(segments: list, tiles: "_DemTiles") -> list:
    """Ordered [Optional[float]] DEM elevations per segment (sampled once)."""
    keys = list({_point_key(p[0], p[1]) for seg in segments for p in seg})
    ele_by_key = _sample_elevations_local(keys, tiles)
    return [[ele_by_key.get(_point_key(p[0], p[1])) for p in seg] for seg in segments]


def _osm_sequences(segments: list) -> list:
    """Ordered [Optional[float]] from the stored 3rd coordinate (OSM ele)."""
    return [[(p[2] if len(p) >= 3 else None) for p in seg] for seg in segments]


def calibrate(dem_dir, url_base) -> None:
    print("\n=== Part B — DEM calibration against known trails ===")
    if rasterio is None:
        print("  rasterio not installed — skipping calibration (Part A still ran).")
        return

    tiles = _DemTiles(dem_dir, url_base)
    with get_connection() as conn, conn.cursor() as cur:
        for needle, known, note in GROUND_TRUTH:
            cur.execute(
                "SELECT name, geometry, elevation_gain_m, trail_shape FROM hikes "
                "WHERE name ILIKE %s ORDER BY length_km DESC LIMIT 1",
                (f"%{needle}%",),
            )
            row = cur.fetchone()
            if not row:
                print(f"\n  {needle}: not found in DB — skipped")
                continue

            geom = row["geometry"]
            if isinstance(geom, str):
                geom = json.loads(geom)
            segs = _segments(geom or {})
            if not segs:
                print(f"\n  {row['name']}: no usable geometry — skipped")
                continue
            dense = _densify(segs, DENSIFY_SPACING_M)

            # Sample the DEM once per point set; reuse across the whole sweep.
            seqs_v = _dem_sequences(segs, tiles)
            seqs_d = _dem_sequences(dense, tiles)
            seqs_s = _smooth(seqs_d, SMOOTH_WINDOW_PTS)

            # OSM-ele: gain from the stored node elevations (raw, no band) + coverage.
            osm_g, osm_cov, osm_tot = _hysteresis_gain(_osm_sequences(segs), 0.0)
            cov_pct = (100 * osm_cov // osm_tot) if osm_tot else 0

            known_str = f"{known} m" if known is not None else "n/a (linear)"
            print(f"\n  {row['name']}")
            print(f"    stored gain: {float(row['elevation_gain_m'] or 0):.0f} m   "
                  f"known: {known_str}   ({note})")
            print(f"    OSM-ele (raw): {osm_g:>6.0f} m   "
                  f"coverage {osm_cov}/{osm_tot} = {cov_pct}%"
                  + ("   ← too sparse to trust" if cov_pct < 60 else ""))
            # Out-and-back round-trip check: stored gain is one-way ASCENT only.
            # A hiker's real gain on a there-and-back is ascent + descent.
            for b in (3.0, 8.0):
                up, down = _ascent_descent(seqs_v, b)
                print(f"    shape={str(row['trail_shape']):<13} @band{b:>2.0f}: "
                      f"ascent {up:>5.0f} + descent {down:>5.0f} = round-trip {up + down:>5.0f} m")
            # Noise-robust proxy: elevation RANGE (max-min) uses two altitude
            # readings, not a sum of noisy deltas — for a monotonic out-and-back
            # this IS the round-trip gain (drop in, climb out).
            _flat = [e for seq in seqs_v for e in seq if e is not None]
            if _flat:
                rng = max(_flat) - min(_flat)
                print(f"    elev range (max-min): {rng:>5.0f} m   "
                      f"(min {min(_flat):.0f}, max {max(_flat):.0f})")
            print(f"    {'min_delta':>9} | {'vertices':>12} | {'densified':>12} | {'smoothed':>12}")
            for md in SWEEP_MIN_DELTAS:
                g_v = _hysteresis_gain(seqs_v, md)[0]
                g_d = _hysteresis_gain(seqs_d, md)[0]
                g_s = _hysteresis_gain(seqs_s, md)[0]
                print(f"    {md:>9.0f} | {g_v:>10.0f} m | {g_d:>10.0f} m | {g_s:>10.0f} m")
    tiles.close()
    if tiles.missing:
        print(f"\n  (missing DEM tiles: {sorted(tiles.missing)} — "
              "supply --dem-dir or check network for /vsicurl)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only elevation diagnostics + DEM calibration.")
    ap.add_argument("--dem-dir", default=None, help="Directory of local Copernicus GLO-30 .tif tiles.")
    ap.add_argument("--dem-url-base", default=DEFAULT_DEM_URL_BASE, help="S3 base for /vsicurl tiles.")
    ap.add_argument("--no-vsicurl", action="store_true", help="Local tiles only; no network reads.")
    ap.add_argument("--no-calibrate", action="store_true", help="Part A (DB distribution) only.")
    args = ap.parse_args()
    try:
        distribution()
        if not args.no_calibrate:
            url_base = None if args.no_vsicurl else args.dem_url_base
            calibrate(args.dem_dir, url_base)
    finally:
        close_pool()


if __name__ == "__main__":
    main()
