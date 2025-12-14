# repositories/hike_repo.py
from uuid import UUID
from typing import List, Optional
from PyObjects.Hike import Hike
from Repos.RepositoryBase import BaseRepository
from DBConnection import get_connection

class HikeRepository(BaseRepository[Hike]):

    def create(self, hike: Hike) -> Hike:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hikes VALUES (
                        %(id)s, %(source_id)s, %(name)s, %(geometry)s,
                        %(difficulty)s, %(length_km)s, %(elevation_gain_m)s,
                        %(min_altitude_m)s, %(max_altitude_m)s,
                        %(region)s, %(season_start_month)s, %(season_end_month)s,
                        %(required_gear_tags)s, %(permits_required)s,
                        %(nearest_airport_code)s, %(parking_coordinates)s,
                        %(last_synced_at)s
                    )
                    """,
                    hike.to_dict()
                )
        return hike

    def get_by_id(self, hike_id: UUID) -> Optional[Hike]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM hikes WHERE id=%s", (hike_id,))
                row = cur.fetchone()
                return Hike.from_dict(row) if row else None

    def list_all(self) -> List[Hike]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM hikes")
                return [Hike.from_dict(r) for r in cur.fetchall()]

    def update(self, hike: Hike) -> Hike:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE hikes SET
                        name=%(name)s,
                        geometry=%(geometry)s,
                        difficulty=%(difficulty)s,
                        length_km=%(length_km)s,
                        elevation_gain_m=%(elevation_gain_m)s,
                        region=%(region)s
                    WHERE id=%(id)s
                    """,
                    hike.to_dict()
                )
        return hike

    def delete(self, hike_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM hikes WHERE id=%s", (hike_id,))
