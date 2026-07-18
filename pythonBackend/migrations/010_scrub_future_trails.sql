-- 010_scrub_future_trails.sql
--
-- One-off data scrub for planned/unbuilt trails that leaked in from OSM with a
-- "Future - …" / "Proposed …" / "Construction …" name (e.g. the user-visible
-- "Future - High Knob Trail"). These aren't walkable routes — OSM mappers tag
-- them for planned corridors — and were being ingested verbatim because
-- parse_hike copied the OSM `name` tag with no proposed/construction filter.
--
-- The ingestion guard is now in place (ingestion/characterizations.is_noise +
-- ingestion/hike_parser.parse_hike) so future re-ingests drop them; this removes
-- the rows already persisted. Matched as a NAME PREFIX (case-insensitive) so a
-- legitimately-named trail is never caught.
--
-- Deletion cascades to hike_gear_requirements (ON DELETE CASCADE). trips.hike_id
-- has no FK to hikes, so a (highly unlikely) saved trip referencing one of these
-- keeps its stored snapshot rather than blocking the delete.
--
-- Run by hand: psql "$DATABASE_URL" -f migrations/010_scrub_future_trails.sql
-- (or via migrate.py up)

BEGIN;

DELETE FROM hikes
WHERE btrim(name) ~* '^(future[ -]|proposed |construction )';

COMMIT;
