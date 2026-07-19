# Runbook — migration 010 + elevation/difficulty backfill (July 2026 batch)

Applies the data half of commit `260693c`. The pushed code fixes *ingestion going
forward*; this runbook fixes the **rows already in the prod DB**. Nothing here is
run by CI — it is a manual, sequenced data operation.

> Run everything from `pythonBackend/` (or `pythonBackend/ingestion/` for the
> backfills — they add the parent dir to `sys.path`). The scripts talk to whatever
> DB `DBConnection` resolves from the environment. **Confirm you are pointed at
> prod** (`echo $HOST` / injected AWS env, not localhost) before any non-dry-run.

---

## 0. Preconditions (do these first)

1. **Snapshot the DB.** This batch mutates `hikes` (difficulty, gain, tags,
   gear_requirements) and DELETEs rows in 010. There is no in-app undo — the
   snapshot is the rollback.
   - RDS: take a manual snapshot, wait for "available".
   - Or a targeted dump of the one table both 010 and the backfills touch:
     ```bash
     pg_dump "$DATABASE_URL" -t hikes --data-only > hikes_pre_batch.sql
     ```
2. **Check the migration runner state:**
   ```bash
   python migrate.py status
   ```
   - If `010` shows **pending** and `001–009` show **applied** → good, proceed.
   - If early migrations (001, etc.) show **pending** on this already-populated
     prod DB → the runner was never baselined here. Run `python migrate.py
     baseline` **once** first (stamps existing `.sql` as applied without running
     them), then re-check `status`. Otherwise `up` re-runs non-idempotent early
     migrations (001's `ADD CONSTRAINT`) and errors. (See CLAUDE.md.)
3. **Verify DEM tiles are available** if you plan to re-run elevation (Step 2):
   `ls ingestion/copernicus_dem/` should list `.tif` tiles. Without them you must
   use `/vsicurl` (remote, slower) or `--http`.

---

## Ordering (why it's strict)

```
010 scrub  →  elevation (--force)  →  [trail_distances]  →  roundtrip_gain  →  difficulty
```

- **elevation before roundtrip_gain**: roundtrip_gain derives out-and-back gain
  from `max_altitude_m − min_altitude_m`, which elevation sets. A later
  `elevation --force` *overwrites* gain with the one-way sum again — so if you
  ever re-run elevation, you must re-run roundtrip_gain after it.
- **gain before difficulty**: `backfill_difficulty` recomputes difficulty, the
  gain-tier tag, and `gear_requirements` from `elevation_gain_m`. It must run
  last so it sees the corrected gain.
- **trail_distances** only matters if `trail_shape` isn't already populated (it
  was set in the earlier distance backfill). roundtrip_gain reads `trail_shape`;
  if yours is already set, this step is a no-op you can skip.

Every backfill has `--dry-run`. **Dry-run each step and read the summary before
the real run.**

---

## Step 1 — Scrub planned/unbuilt trails (migration 010)

Deletes rows whose name starts with `Future -` / `Proposed ` / `Construction `
(e.g. "Future - High Knob Trail"). Name-**prefix** match, so real trails are safe.
Cascades to `hike_gear_requirements`; saved `trips` keep their snapshot.

```bash
# Preview what will be deleted (dry-run — the migration itself has none, so query):
psql "$DATABASE_URL" -c "SELECT id, name FROM hikes WHERE btrim(name) ~* '^(future[ -]|proposed |construction )' ORDER BY name;"

# Apply — either via the runner (tracks it in schema_migrations):
python migrate.py up
#   …or directly (equivalent, self-contained BEGIN/COMMIT):
# psql "$DATABASE_URL" -f migrations/010_scrub_future_trails.sql
```

**Verify:** the count is now 0.
```bash
psql "$DATABASE_URL" -c "SELECT count(*) FROM hikes WHERE btrim(name) ~* '^(future[ -]|proposed |construction )';"
```

---

## Step 2 — Re-measure elevation from the DEM  *(decision point)*

This applies the **new** hysteresis denoise + void-floor (0 m readings treated as
DEM voids). Rows already carry the `dem_elevation` marker from prior runs, so you
must pass `--force` to reprocess them. Heavy (samples the DEM per vertex).

**Decide:** if the prior elevation run predates this diff's `_recompute` rewrite,
run it — inflated gains are exactly what it fixes. If you'd rather do the minimal
fix and only correct the out-and-back artifact, **skip to Step 4** (roundtrip_gain
reads the existing min/max altitude). Use the dry-run delta to decide:

```bash
# Local tiles only (recommended if copernicus_dem/ is populated):
python ingestion/backfill_elevation.py --dry-run --force --dem-dir ingestion/copernicus_dem --no-vsicurl

# If deltas look right, run for real (drop --dry-run). Resumable via --batch N:
python ingestion/backfill_elevation.py --force --dem-dir ingestion/copernicus_dem --no-vsicurl
```

- `--min-delta` defaults to 8.0 m (the noise band); leave it unless a dry-run
  shows real gentle climbs being zeroed.
- No local tiles? Drop `--no-vsicurl` (reads Copernicus COGs over `/vsicurl`), or
  `--http --sleep 1.0` against an opentopodata endpoint.

---

## Step 3 — trail_shape (skip if already populated)

Only needed if `trail_shape` is NULL for many rows. Idempotent by `trail_shape`
(already-stamped rows are skipped), so a re-run won't reclassify old rows.

```bash
psql "$DATABASE_URL" -c "SELECT trail_shape, count(*) FROM hikes GROUP BY 1 ORDER BY 2 DESC;"
# If a large 'unknown'/NULL bucket exists:
python ingestion/backfill_trail_distances.py --dry-run
python ingestion/backfill_trail_distances.py
```

---

## Step 4 — Correct out-and-back gain (round-trip range)

Sets `elevation_gain_m = max_altitude_m − min_altitude_m` for
`trail_shape = out_and_back` trails ≤ 30 km round-trip (the "strenuous trail
labelled flat / 65 m" fix). Idempotent. Skips degenerate (≤0) ranges.

```bash
python ingestion/backfill_roundtrip_gain.py --dry-run
python ingestion/backfill_roundtrip_gain.py
```

**Verify** against the calibration trails from the script docstring:
- Spence Ridge ≈ 266 m (was ~65, "flat")
- McMullen greenway ≈ 22 m (was ~92, canopy-inflated)
- Rattlesnake ≈ 227 m (stays accurate)

```bash
psql "$DATABASE_URL" -c "SELECT name, length_km, elevation_gain_m, trail_shape FROM hikes WHERE name ILIKE ANY (ARRAY['%spence%','%mcmullen%','%rattlesnake%']);"
```

---

## Step 5 — Re-derive difficulty + gain-tier tag + gear

Recomputes difficulty (with the grade-feel cap/bump), swaps the gain-tier tag, and
rewrites `gear_requirements` from the corrected gain. Processes all rows,
idempotent. New CLI defaults come from `characterizations` (single source).

```bash
python ingestion/backfill_difficulty.py --dry-run   # prints the difficulty move table
python ingestion/backfill_difficulty.py
```

**Sanity-check the distribution** (flat rail-trails should no longer be Expert;
short steep walls no longer Easy):
```bash
psql "$DATABASE_URL" -c "SELECT difficulty, count(*) FROM hikes GROUP BY 1 ORDER BY 1;"
```

---

## Post-batch

- Trip-planner reads this data live — no cache to bust, but if you keep a warm
  process, a restart is harmless.
- Spot-check in the app: a search that previously surfaced a "Future -" trail, a
  known strenuous out-and-back (should now read its real gain), and a long flat
  greenway (should read Moderate, not Expert).

## Rollback

There is no per-script undo — restore from the Step 0 snapshot/dump:
```bash
# Targeted (data-only dump of hikes):
psql "$DATABASE_URL" -c "TRUNCATE hike_gear_requirements;"   # if restoring cascade children
psql "$DATABASE_URL" < hikes_pre_batch.sql
# Or restore the whole RDS snapshot.
```
Note: 010's DELETE is only recoverable from backup or a fresh OSM re-ingest.
Because the backfills are idempotent, a *partial* failure is safe to simply
re-run from the failed step forward — you don't need to roll back for that.
