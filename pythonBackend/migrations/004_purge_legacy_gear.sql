-- 004_purge_legacy_gear.sql
--
-- Retire the legacy "specific product catalog" gear model in favor of the
-- generalized A+ gear model (functional gear_category + capability level stored
-- in items.attributes; see gear_levels.py). This file covers the *schema* half;
-- the data half (stamping owned catalog items with a gear_category, then
-- deleting the unowned catalog rows) needs the Python resolver and lives in
-- migrations/004_purge_legacy_gear.py — run that first, then apply this.
--
-- hike_items resolved each hike's requirements to specific catalog item rows and
-- was only ever as complete as the catalog. Per-trail needs now live in the
-- catalog-independent hikes.gear_requirements jsonb (migration 003, all hikes
-- backfilled), and HikeRepo derives required_gear_tags from it — so nothing
-- reads hike_items anymore. Drop it.

DROP TABLE IF EXISTS hike_items;
