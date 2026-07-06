import json
from uuid import UUID
from typing import List, Optional

from DBConnection import get_connection
from PyObjects.Trip import Trip, TripStop, TripGearItem, HikeCompletion


class TripRepository:

    # ── Trips ──────────────────────────────────────────────────────────────────

    def create(self, trip: Trip) -> Trip:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trips (id, user_id, title, goal, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (str(trip.id), str(trip.user_id), trip.title,
                     trip.goal, trip.status, trip.created_at, trip.updated_at)
                )
        return trip

    def update_status(self, trip_id: UUID, status: str) -> None:
        """Bumps updated_at alongside status — every status transition in the
        lifecycle (saved/completed/reviewed) should go through this so
        GET /chats's updated_at-desc ordering stays meaningful."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE trips SET status = %s, updated_at = now() WHERE id = %s",
                    (status, str(trip_id))
                )

    def mark_completed(self, trip_id: UUID) -> None:
        """'Mark as done' — status=completed and stamps completed_at, which
        the needs_review background job anchors off of (see
        flip_needs_review). Separate from update_status since it's the only
        transition that also sets a timestamp column."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trips
                    SET status = 'completed', completed_at = now(), updated_at = now()
                    WHERE id = %s
                    """,
                    (str(trip_id),)
                )

    def mark_reviewed(self, trip_id: UUID) -> None:
        """status=reviewed once the questionnaire is submitted. needs_review
        is cleared alongside — harmless either way since the background job
        only ever matches status='completed', but keeps the flag meaningful
        if something else ever reads it directly."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trips
                    SET status = 'reviewed', needs_review = false, updated_at = now()
                    WHERE id = %s
                    """,
                    (str(trip_id),)
                )

    def flip_needs_review(self, days: int) -> int:
        """
        Background-job primitive: flips needs_review for every completed
        trip whose completed_at is more than `days` old and isn't already
        flagged. Pure batch UPDATE — no per-row Python loop needed, and
        idempotent to re-run (WHERE needs_review = false means an
        already-flagged row is a no-op on the next pass).

        Returns the number of rows flipped, for logging.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trips
                    SET needs_review = true
                    WHERE status = 'completed'
                      AND needs_review = false
                      AND completed_at <= now() - (%s || ' days')::interval
                    """,
                    (days,)
                )
                return cur.rowcount

    # ── Hike completions ──────────────────────────────────────────────────────

    def add_completion(self, completion: HikeCompletion) -> HikeCompletion:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hike_completions (
                        trip_id, went, difficulty_felt, elevation_felt, rating, notes, reviewed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trip_id) DO UPDATE SET
                        went            = EXCLUDED.went,
                        difficulty_felt = EXCLUDED.difficulty_felt,
                        elevation_felt  = EXCLUDED.elevation_felt,
                        rating          = EXCLUDED.rating,
                        notes           = EXCLUDED.notes,
                        reviewed_at     = EXCLUDED.reviewed_at
                    """,
                    (
                        str(completion.trip_id), completion.went, completion.difficulty_felt,
                        completion.elevation_felt, completion.rating, completion.notes,
                        completion.reviewed_at,
                    )
                )
        return completion

    def get_completion(self, trip_id: UUID) -> Optional[HikeCompletion]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM hike_completions WHERE trip_id = %s", (str(trip_id),))
                row = cur.fetchone()
                return HikeCompletion.from_dict(dict(row)) if row else None

    def get_ratings(self, trip_ids: List[UUID]) -> dict:
        """
        {trip_id_str: rating} for whichever of these ids have a rated
        hike_completions row. Used by GET /chats so the Past Hikes card grid
        can show a rating without fetching each trip's full record —
        keeps Trip/list_by_user() clean rather than baking a
        hike_completions join into the trips query.
        """
        if not trip_ids:
            return {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT trip_id, rating FROM hike_completions WHERE trip_id = ANY(%s) AND rating IS NOT NULL",
                    ([str(t) for t in trip_ids],)
                )
                return {str(row["trip_id"]): row["rating"] for row in cur.fetchall()}

    def get_by_id(self, trip_id: UUID) -> Optional[Trip]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM trips WHERE id = %s", (str(trip_id),))
                row = cur.fetchone()
                if not row:
                    return None
                trip = Trip.from_dict(dict(row))
                trip.stops = self._get_stops(cur, trip_id)
                trip.gear  = self._get_gear(cur, trip_id)
                return trip

    def list_by_user(
        self,
        user_id: UUID,
        statuses: Optional[List[str]] = None,
        hydrate: bool = True,
    ) -> List[Trip]:
        """
        statuses filters to just those lifecycle states (e.g. ["saved",
        "completed", "reviewed"] for GET /chats); None (default) returns
        everything, preserving the existing GET /trips/ behavior.

        hydrate=False skips the per-trip stops/gear lookups — GET /chats
        only needs title/status/timestamps for the list view, so there's no
        reason to pay for N+1 stop/gear queries there.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                query  = "SELECT * FROM trips WHERE user_id = %s"
                params: list = [str(user_id)]
                if statuses:
                    query += " AND status = ANY(%s)"
                    params.append(list(statuses))
                query += " ORDER BY updated_at DESC"

                cur.execute(query, params)
                rows = cur.fetchall()
                trips = []
                for row in rows:
                    trip = Trip.from_dict(dict(row))
                    if hydrate:
                        trip.stops = self._get_stops(cur, trip.id)
                        trip.gear  = self._get_gear(cur, trip.id)
                    trips.append(trip)
                return trips

    def delete(self, trip_id: UUID) -> None:
        # trip_stops and trip_gear cascade via FK ON DELETE CASCADE
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM trips WHERE id = %s", (str(trip_id),))

    # ── Stops ──────────────────────────────────────────────────────────────────

    def add_stop(self, stop: TripStop) -> TripStop:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trip_stops (
                        id, trip_id, stop_order, destination, lat, lng,
                        duration_days, activity_type,
                        itinerary, trail_data, camping, cost_estimate, travel_from_prev,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                              %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                              %s)
                    """,
                    (
                        str(stop.id), str(stop.trip_id), stop.stop_order,
                        stop.destination, stop.lat, stop.lng,
                        stop.duration_days, stop.activity_type,
                        json.dumps(stop.itinerary)        if stop.itinerary        else None,
                        json.dumps(stop.trail_data)       if stop.trail_data       else None,
                        json.dumps(stop.camping)          if stop.camping          else None,
                        json.dumps(stop.cost_estimate)    if stop.cost_estimate    else None,
                        json.dumps(stop.travel_from_prev) if stop.travel_from_prev else None,
                        stop.created_at,
                    )
                )
        return stop

    def get_stop_by_id(self, stop_id: UUID) -> Optional[TripStop]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM trip_stops WHERE id = %s", (str(stop_id),))
                row = cur.fetchone()
                return TripStop.from_dict(dict(row)) if row else None

    def update_stop(self, stop: TripStop) -> TripStop:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trip_stops SET
                        duration_days    = %s,
                        activity_type    = %s,
                        itinerary        = %s::jsonb,
                        trail_data       = %s::jsonb,
                        camping          = %s::jsonb,
                        cost_estimate    = %s::jsonb,
                        travel_from_prev = %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        stop.duration_days, stop.activity_type,
                        json.dumps(stop.itinerary)        if stop.itinerary        else None,
                        json.dumps(stop.trail_data)       if stop.trail_data       else None,
                        json.dumps(stop.camping)          if stop.camping          else None,
                        json.dumps(stop.cost_estimate)    if stop.cost_estimate    else None,
                        json.dumps(stop.travel_from_prev) if stop.travel_from_prev else None,
                        str(stop.id),
                    )
                )
        return stop

    def delete_stop(self, stop_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM trip_stops WHERE id = %s", (str(stop_id),))

    # ── Gear ───────────────────────────────────────────────────────────────────

    def add_gear(self, gear: TripGearItem) -> TripGearItem:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trip_gear (trip_id, item_id, status)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (trip_id, item_id) DO UPDATE SET status = EXCLUDED.status
                    """,
                    (str(gear.trip_id), str(gear.item_id), gear.status)
                )
        return gear

    def remove_gear(self, trip_id: UUID, item_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM trip_gear WHERE trip_id = %s AND item_id = %s",
                    (str(trip_id), str(item_id))
                )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_stops(self, cur, trip_id: UUID) -> List[TripStop]:
        cur.execute(
            "SELECT * FROM trip_stops WHERE trip_id = %s ORDER BY stop_order",
            (str(trip_id),)
        )
        return [TripStop.from_dict(dict(r)) for r in cur.fetchall()]

    def _get_gear(self, cur, trip_id: UUID) -> List[TripGearItem]:
        cur.execute(
            "SELECT trip_id, item_id, status FROM trip_gear WHERE trip_id = %s",
            (str(trip_id),)
        )
        return [
            TripGearItem(
                trip_id=UUID(str(r["trip_id"])),
                item_id=UUID(str(r["item_id"])),
                status=r.get("status", "owned"),
            )
            for r in cur.fetchall()
        ]