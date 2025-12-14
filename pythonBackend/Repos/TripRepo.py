from uuid import UUID
from typing import List, Optional
from PyObjects.Trip import Trip
from Repos.RepositoryBase import BaseRepository
from DBConnection import get_connection

class TripRepository(BaseRepository[Trip]):

    def create(self, trip: Trip) -> Trip:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trips VALUES (
                        %(id)s, %(user_id)s, %(hike_id)s,
                        %(start_date)s, %(end_date)s,
                        %(origin_point)s, %(travel_mode)s,
                        %(travel_estimate)s, %(missing_gear)s,
                        %(shopping_estimate)s, %(created_at)s
                    )
                    """,
                    trip.to_dict()
                )
        return trip

    def get_by_id(self, trip_id: UUID) -> Optional[Trip]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM trips WHERE id=%s", (trip_id,))
                row = cur.fetchone()
                return Trip.from_dict(row) if row else None

    def list_all(self) -> List[Trip]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM trips")
                return [Trip.from_dict(r) for r in cur.fetchall()]

    def update(self, trip: Trip) -> Trip:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trips
                    SET travel_estimate=%(travel_estimate)s,
                        missing_gear=%(missing_gear)s,
                        shopping_estimate=%(shopping_estimate)s
                    WHERE id=%(id)s
                    """,
                    trip.to_dict()
                )
        return trip

    def delete(self, trip_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM trips WHERE id=%s", (trip_id,))
