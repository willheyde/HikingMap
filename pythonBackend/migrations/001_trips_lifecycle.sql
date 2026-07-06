-- 001_trips_lifecycle.sql
--
-- Extends `trips` to carry the full chat-session lifecycle instead of the
-- new chat_sessions table originally proposed: active (Redis-only, not
-- represented here) -> saved -> completed -> reviewed. `trips.status`
-- already anticipated this ("draft | saved | completed" in the Trip
-- dataclass docstring) but nothing ever moved it past 'draft' -- this
-- finishes that.
--
-- No migration tool in this project yet -- run by hand against the DB:
--   psql "$DATABASE_URL" -f migrations/001_trips_lifecycle.sql
-- (or via `python -c "..."` using DBConnection.get_connection(), same as
-- every other one-off script in this repo).

BEGIN;

-- updated_at drives GET /chats sort order and needs_review scheduling later.
-- No trigger -- bumped explicitly in TripRepository on every write, matching
-- how this codebase already handles timestamps by hand elsewhere.
ALTER TABLE trips
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

UPDATE trips SET updated_at = created_at WHERE created_at IS NOT NULL;

-- 'draft' kept for backward compatibility with the generic POST /trips/
-- creation path (TripService.create_trip default) even though nothing in
-- the frontend currently calls it -- the AI save flow now creates rows
-- directly as 'saved' instead of relying on that default.
ALTER TABLE trips
    ADD CONSTRAINT trips_status_check
    CHECK (status IN ('draft', 'saved', 'completed', 'reviewed'));

-- GET /chats filters + lists by user_id on every call; only trips_pkey (id)
-- existed before this.
CREATE INDEX IF NOT EXISTS trips_user_id_idx ON trips (user_id);

COMMIT;

-- Phase 2 will add: trips.planned_date, trips.needs_review, and the
-- hike_completions table. Not included here to keep this migration scoped
-- to what Phase 1 actually uses.
