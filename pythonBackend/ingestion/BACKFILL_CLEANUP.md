# Backfill receipt & cleanup — elevation / difficulty / forest

One-time data-fix scaffolding added July 2026. **The fixes themselves are written
into Postgres** (corrected `elevation_gain_m` / `min`/`max_altitude_m`, retuned
`difficulty`, refreshed `gear_requirements`, `forest` tags, and `dem_elevation`
provenance markers). Everything below is just the *tooling* used to compute
them — removing it does **not** undo the data fix. Only re-install/re-download
if you re-run the backfills (e.g. after a future re-ingest).

Nothing was added to Docker (I only ran `docker info`/`--version`, never pulled
an image or started a container). No Copernicus DEM was downloaded — elevation
reads it on demand via GDAL `/vsicurl`.

## What was added

| Item | Type | Size | Used by | Needed at app runtime? |
|---|---|---|---|---|
| `rasterio` 1.5.0 | pip package | ~36 MB | `backfill_elevation.py` (DEM /vsicurl), `backfill_forest.py` | **No** — only the backfills import it |
| `affine` 2.4.0 | pip (rasterio dep) | ~0.1 MB | rasterio | No |
| `cligj` 0.7.2 | pip (rasterio dep) | ~0.0 MB | rasterio | No |
| `pyparsing` 3.3.2 | pip (rasterio dep) | ~0.9 MB | rasterio + many other libs | No (but common — leave it) |
| `pythonBackend/worldcover/` (8 GeoTIFFs) | download | ~457 MB | `backfill_forest.py` only | No |
| Copernicus GLO-30 DEM | — | 0 MB | elevation reads via `/vsicurl` | No (nothing on disk) |

**Total on disk: ~494 MB.**

## When each can be removed

- **WorldCover tiles** — needed only while running `backfill_forest.py`. Delete
  after the forest backfill completes.
- **rasterio (+ affine, cligj)** — needed by both `backfill_elevation.py` and
  `backfill_forest.py`. Uninstall after **both** have run.
- Leave **pyparsing** (tiny, widely used as a transitive dep elsewhere).
- `backfill_difficulty.py` added **no** new dependencies (pure DB + existing modules).

## Cleanup commands (run only after all three backfills are done)

PowerShell:
```powershell
python -m pip uninstall -y rasterio affine cligj
Remove-Item -Recurse -Force C:\Coding\HikingMap\pythonBackend\worldcover
```

Git Bash:
```bash
python -m pip uninstall -y rasterio affine cligj
rm -rf /c/Coding/HikingMap/pythonBackend/worldcover
```

## What to KEEP (do not delete)

- `ingestion/backfill_elevation.py`, `backfill_difficulty.py`, `backfill_forest.py`
  and the code edits in `characterizations.py` — these are source, tiny, and
  reusable if you ever re-ingest. Committing them is fine.
- This file.

## To re-run later (if you re-ingest)

```bash
python -m pip install rasterio
# WorldCover tiles back into ./worldcover (NC: N33W084/081/078, N36W084/081/078; RI: N39W072[,N42W072])
#   curl -sS --fail -o worldcover/<file> \
#     https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/<file>
```
