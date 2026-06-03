import json
from uuid import UUID
from typing import List, Optional

from DBConnection import get_connection
from PyObjects.Trip import Trip, TripStop, TripGearItem


class TripRepository:

    # ── Trips ──────────────────────────────────────────────────────────────────

    def create(self, trip: Trip) -> Trip:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trips (id, user_id, title, goal, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(trip.id), str(trip.user_id), trip.title,
                     trip.goal, trip.status, trip.created_at)
                )
        return trip

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

    def list_by_user(self, user_id: UUID) -> List[Trip]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM trips WHERE user_id = %s ORDER BY created_at DESC",
                    (str(user_id),)
                )
                rows = cur.fetchall()
                trips = []
                for row in rows:
                    trip = Trip.from_dict(dict(row))
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