import json  # <--- NEW: Required for serializing dicts to JSON
from uuid import UUID
from typing import List, Optional
from PyObjects.Hike import Hike
from Repos.RepositoryBase import BaseRepository
from DBConnection import get_connection

class HikeRepository(BaseRepository[Hike]):

    def create(self, hike: Hike) -> Hike:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Convert hike to a dictionary
                params = hike.to_dict()

                # 2. Serialize complex fields to JSON strings for the DB
                # 'geometry' is a dict, so we dump it to a string
                params["geometry"] = json.dumps(params["geometry"])
                
                # 'required_gear_tags' is a list, dump it to string
                params["required_gear_tags"] = json.dumps(params["required_gear_tags"])
                
                # 'parking_coordinates' is a dict or None
                if params.get("parking_coordinates"):
                    params["parking_coordinates"] = json.dumps(params["parking_coordinates"])
                else:
                    params["parking_coordinates"] = None

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
                    params
                )
        return hike

    def get_by_id(self, hike_id: UUID) -> Optional[Hike]:
        with get_connection() as conn:
            # NOTE: Ideally, ensure your DBConnection returns DictRows.
            # If standard cursor, row is a tuple and this might fail.
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM hikes WHERE id=%s", (hike_id,))
                row = cur.fetchone()
                # If row is a tuple, you will need a row_factory or manual mapping here.
                # Assuming your DBConnection is configured to return RealDictCursor or similar.
                return Hike.from_dict(row) if row else None

    def list_all(self) -> List[Hike]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM hikes")
                return [Hike.from_dict(r) for r in cur.fetchall()]

    def update(self, hike: Hike) -> Hike:
        with get_connection() as conn:
            with conn.cursor() as cur:
                params = hike.to_dict()
                
                # Serialize geometry for update as well
                params["geometry"] = json.dumps(params["geometry"])

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
                    params
                )
        return hike

    def delete(self, hike_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM hikes WHERE id=%s", (hike_id,))

    def search(
        self,
        min_length_km=None,
        min_elevation_gain_m=None,
        difficulty=None,
        region=None,
        month=None,
    ):
        with get_connection() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM hikes WHERE 1=1"
                params = {}

                if min_length_km is not None:
                    query += " AND length_km >= %(min_length_km)s"
                    params["min_length_km"] = min_length_km

                if min_elevation_gain_m is not None:
                    query += " AND elevation_gain_m >= %(min_elevation_gain_m)s"
                    params["min_elevation_gain_m"] = min_elevation_gain_m

                if difficulty is not None:
                    query += " AND difficulty = %(difficulty)s"
                    params["difficulty"] = difficulty.name

                if region is not None:
                    query += " AND region = %(region)s"
                    params["region"] = region

                if month is not None:
                    query += """
                        AND season_start_month <= %(month)s
                        AND season_end_month >= %(month)s
                    """
                    params["month"] = month

                cur.execute(query, params)
                rows = cur.fetchall()

                return [Hike.from_dict(row) for row in rows]