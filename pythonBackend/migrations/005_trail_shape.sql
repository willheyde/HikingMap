-- 005_trail_shape.sql
--
-- Records each hike's inferred geometric shape: 'loop' | 'out_and_back'.
--
-- Why: OSM stores an out-and-back trail's physical path ONCE (trailhead →
-- turnaround), so the stitched geometry — and the length_km derived from it — is
-- one-way and reads at ~half the real round-trip distance. Loops (start ≈ end)
-- are already full-length. (Elevation gain is unaffected: the climb is all on the
-- outbound leg, so one-way positive gain already ≈ the round-trip gain.)
--
-- This column serves two purposes:
--   1. captures the classification for downstream use, and
--   2. is the idempotency gate for the one-shot distance backfill
--      (ingestion/backfill_trail_distances.py): NULL = not yet classified /
--      corrected. Once stamped — by the backfill OR by a fresh ingest, both of
--      which set it whenever they set/correct length_km — neither path re-doubles
--      the row.
--
-- Nullable with no default on purpose: existing rows stay NULL until the backfill
-- runs; new ingests stamp it at insert time.
--
-- NOTE: hikes.from_dict() builds a Hike from SELECT * via cls(**row), so the
-- matching `trail_shape` field was added to PyObjects/Hike.py in the same change.

ALTER TABLE hikes
    ADD COLUMN IF NOT EXISTS trail_shape text;
