-- 002_completion_review.sql
--
-- Adds the completed/reviewed half of the trips lifecycle (Phase 2):
-- "Mark as done" -> completed, non-blocking review nudge, questionnaire -> reviewed.
--
-- Note on planned_date: kept here per the original design, but nothing in
-- the AI flow extracts a calendar date today (TripInputParser only parses
-- duration, e.g. "3 days" -- never "next Saturday" or "July 20th"), so this
-- column will stay null for the foreseeable future. The needs_review job
-- anchors off completed_at (when the user hit "Mark as done") instead --
-- see flip_needs_review() in TripRepo.
--
-- Run by hand: psql "$DATABASE_URL" -f migrations/002_completion_review.sql

BEGIN;

ALTER TABLE trips
    ADD COLUMN IF NOT EXISTS planned_date  date,
    ADD COLUMN IF NOT EXISTS completed_at  timestamptz,
    ADD COLUMN IF NOT EXISTS needs_review  boolean NOT NULL DEFAULT false;

-- Partial index -- the background job's WHERE clause always filters on
-- exactly these two columns together; this is the only query shape that hits it.
CREATE INDEX IF NOT EXISTS trips_needs_review_scan_idx
    ON trips (completed_at)
    WHERE status = 'completed' AND needs_review = false;

CREATE TABLE IF NOT EXISTS hike_completions (
    trip_id         uuid PRIMARY KEY REFERENCES trips(id) ON DELETE CASCADE,
    went            boolean NOT NULL,
    -- Matches hikes.difficulty's storage convention (DifficultyLevel.name as
    -- text: EASY|MODERATE|DIFFICULT|EXPERT) rather than a native enum type.
    difficulty_felt varchar,
    elevation_felt  text,
    rating          integer,
    notes           text,
    reviewed_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hike_completions_rating_check CHECK (rating IS NULL OR rating BETWEEN 1 AND 5)
);

COMMIT;
