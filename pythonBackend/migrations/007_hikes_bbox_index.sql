-- 007_hikes_bbox_index.sql
--
-- The map's /hikes/search now filters on the trailhead lat/lng columns with a
-- viewport bounding box (WHERE lat BETWEEN ... AND lng BETWEEN ...) and a
-- LIMIT, instead of streaming the whole table on every pan. This composite
-- btree backs that box query so it stays a range scan rather than a seq scan
-- as the trail table grows.
--
-- lat is the leading column because it's the more selective of the two for
-- the current data footprint; both bounds are always supplied together, so a
-- single composite index covers the AND-ed range predicate.
--
-- Run by hand: psql "$DATABASE_URL" -f migrations/007_hikes_bbox_index.sql

BEGIN;

CREATE INDEX IF NOT EXISTS hikes_lat_lng_idx
    ON hikes (lat, lng);

COMMIT;
