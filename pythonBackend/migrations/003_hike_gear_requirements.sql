-- 003_hike_gear_requirements.sql
--
-- Adds a catalog-independent, per-hike REQUIRED gear structure: a jsonb map of
-- category -> {min_level | min_temp_f, importance}. Populated by
-- GearInferenceEngine.infer_gear_levels() at ingestion and, for hikes already
-- in the table, by ingestion/backfill_gear_levels.py (no re-ingest needed).
--
-- Distinct from the hike_items table (which resolves requirements to specific
-- catalog rows and is therefore only as complete as the catalog): this column
-- is derived straight from the hike's physical stats + tags, so it's always
-- fully populated and drives the adequacy checks in GearGapAnalyzer.

ALTER TABLE hikes
    ADD COLUMN IF NOT EXISTS gear_requirements jsonb NOT NULL DEFAULT '{}'::jsonb;
