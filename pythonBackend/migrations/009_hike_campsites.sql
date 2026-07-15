-- 009_hike_campsites.sql
--
-- Adds a per-hike list of known campsites/shelters near the route.
--
-- Why: the AI itinerary was inventing campsite names (telling users to camp at
-- places that don't exist / aren't legal). The Overpass enrichment query already
-- pulls tourism=camp_site / wilderness_hut and amenity=shelter elements near each
-- trail — it just collapsed them into the boolean can_camp / a bare "shelter"
-- tag and discarded their names + coordinates. This column captures them
-- structurally so the itinerary prompt can name REAL camps (and say "no mapped
-- site — verify a legal site/permit" where OSM has none).
--
-- Shape: a JSON array of
--   {"name": text, "lat": float, "lng": float,
--    "type": "shelter" | "camp_site", "dist_off_trail_m": number}
-- Populated by ingestion/overpass_enrichment.py (a --force re-enrichment pass,
-- NOT a full re-ingest). Defaults to '[]' so existing rows are valid immediately.
--
-- NOTE: hikes.from_dict() builds a Hike from SELECT * via cls(**row), so the
-- matching `campsites` field was added to PyObjects/Hike.py in the same change,
-- and HikeRepository.create/update now list the column explicitly.

ALTER TABLE hikes
    ADD COLUMN IF NOT EXISTS campsites jsonb DEFAULT '[]'::jsonb NOT NULL;
