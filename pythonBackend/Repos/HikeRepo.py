import json
from uuid import UUID
from typing import List, Optional
from PyObjects.Hike import Hike
from Repos.RepositoryBase import BaseRepository
from DBConnection import get_connection
from Repos.ItemRepo import _row_to_item


class HikeRepository(BaseRepository[Hike]):

    def create(self, hike: Hike) -> Hike:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hikes (
                        id, source_id, name, geometry,
                        difficulty, length_km, elevation_gain_m,
                        min_altitude_m, max_altitude_m,
                        region, season_start_month, season_end_month,
                        permits_required, nearest_airport_code, parking_coordinates,
                        last_synced_at, tags, can_camp
                    ) VALUES (
                        %(id)s, %(source_id)s, %(name)s, %(geometry)s,
                        %(difficulty)s, %(length_km)s, %(elevation_gain_m)s,
                        %(min_altitude_m)s, %(max_altitude_m)s,
                        %(region)s, %(season_start_month)s, %(season_end_month)s,
                        %(permits_required)s, %(nearest_airport_code)s, %(parking_coordinates)s,
                        %(last_synced_at)s, %(tags)s, %(can_camp)s
                    )
                    """,
                    {
                        "id":                   str(hike.id),
                        "source_id":            hike.source_id,
                        "name":                 hike.name,
                        "geometry":             json.dumps(hike.geometry),
                        "difficulty":           hike.difficulty.name,
                        "length_km":            hike.length_km,
                        "elevation_gain_m":     hike.elevation_gain_m,
                        "min_altitude_m":       hike.min_altitude_m,
                        "max_altitude_m":       hike.max_altitude_m,
                        "region":               hike.region,
                        "season_start_month":   hike.season_start_month,
                        "season_end_month":     hike.season_end_month,
                        "permits_required":     hike.permits_required,
                        "nearest_airport_code": hike.nearest_airport_code,
                        "parking_coordinates":  json.dumps(hike.parking_coordinates) if hike.parking_coordinates else None,
                        "last_synced_at":       hike.last_synced_at,
                        "tags":                 hike.tags,    # list → psycopg2 handles text[] natively
                        "can_camp":             hike.can_camp,
                    }
                )
        return hike

    def get_by_source_id(self, source_id: str) -> Optional[Hike]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM hikes WHERE source_id = %s",
                    (source_id,)
                )
                row = cur.fetchone()
        return Hike.from_dict(row) if row else None

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
                params = hike.to_dict()
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

    def get_items_for_hike(self, hike_id: UUID) -> List[tuple]:
        """Returns a list of (Item, importance) tuples for a single hike."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT i.id, i.name, i.weight, i.cost, i.item_type, i.image_url, i.attributes,
                        hi.importance
                    FROM items i
                    JOIN hike_items hi ON hi.item_id = i.id
                    WHERE hi.hike_id = %s
                    ORDER BY hi.importance, i.name
                    """,
                    (str(hike_id),)
                )
                rows = cur.fetchall()

        result = []
        for row in rows:
            row_dict = dict(row)
            importance = row_dict.pop("importance")
            item = _row_to_item(row_dict)
            result.append((item, importance))
        return result

    def _attach_items_to_hikes(self, hikes: List[Hike]) -> None:
        """Batch loads items for a list of hikes and attaches them in-place.
        Avoids N+1 — one query regardless of how many hikes are returned."""
        if not hikes:
            return

        hike_ids = [str(h.id) for h in hikes]

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT hi.hike_id, hi.importance,
                        i.id, i.name, i.weight, i.cost, i.item_type, i.image_url, i.attributes
                    FROM hike_items hi
                    JOIN items i ON i.id = hi.item_id
                    WHERE hi.hike_id::text = ANY(%s)
                    ORDER BY hi.importance, i.name
                    """,
                    (hike_ids,)
                )
                rows = cur.fetchall()

        items_by_hike: dict = {}
        for row in rows:
            row_dict = dict(row)
            hike_id = str(row_dict.pop("hike_id"))
            importance = row_dict.pop("importance")
            item = _row_to_item(row_dict)
            items_by_hike.setdefault(hike_id, []).append((item, importance))

        for hike in hikes:
            hike.items = items_by_hike.get(str(hike.id), [])
            hike.required_gear_tags = [
                item.item_type for item, importance in hike.items
                if importance == "required"
            ]

    # Repos/HikeRepo.py  — updated search() signature
    def search(
        self,
        min_length_km=None,
        min_elevation_gain_m=None,
        difficulty=None,
        region=None,
        month=None,
        user_lat=None,
        user_lon=None,
        max_distance_km=None,
        # ── NEW ────────────────────────────────────────────────
        required_tags: Optional[List[str]] = None,   # tags @> ARRAY[...]
        can_camp: Optional[bool] = None,             # boolean column
        permits_required: Optional[bool] = None,     # boolean column
    ):
        with get_connection() as conn:
            with conn.cursor() as cur:
                LAT_SELECTOR = """
                    CASE
                        WHEN geometry::jsonb->>'type' = 'Point'
                        THEN CAST(geometry::jsonb->'coordinates'->>1 AS FLOAT)
                        ELSE CAST(geometry::jsonb->'coordinates'->0->>1 AS FLOAT)
                    END
                """
                LON_SELECTOR = """
                    CASE
                        WHEN geometry::jsonb->>'type' = 'Point'
                        THEN CAST(geometry::jsonb->'coordinates'->>0 AS FLOAT)
                        ELSE CAST(geometry::jsonb->'coordinates'->0->>0 AS FLOAT)
                    END
                """

                query = "SELECT *"
                params = {}

                if user_lat is not None and user_lon is not None:
                    query += f"""
                        , (
                            6371 * acos(
                                least(1.0, greatest(-1.0,
                                    cos(radians(%(user_lat)s)) * cos(radians({LAT_SELECTOR})) * cos(radians({LON_SELECTOR}) - radians(%(user_lon)s)) +
                                    sin(radians(%(user_lat)s)) * sin(radians({LAT_SELECTOR}))
                                ))
                            )
                        ) as distance_km
                    """
                    params["user_lat"] = user_lat
                    params["user_lon"] = user_lon
                else:
                    query += ", NULL as distance_km"

                query += " FROM hikes WHERE 1=1"

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
                # Hard-filter: hike must have ALL of these tags
                if required_tags:
                    query += " AND tags @> %(required_tags)s"
                    params["required_tags"] = required_tags  # psycopg2 → text[]

                # Hard-filter: boolean columns (not part of the tags array)
                if can_camp is True:
                    query += " AND can_camp = TRUE"

                if permits_required is False:
                    query += " AND permits_required = FALSE"

                if max_distance_km is not None and user_lat is not None:
                    query += f"""
                        AND (
                            6371 * acos(
                                least(1.0, greatest(-1.0,
                                    cos(radians(%(user_lat)s)) * cos(radians({LAT_SELECTOR})) * cos(radians({LON_SELECTOR}) - radians(%(user_lon)s)) +
                                    sin(radians(%(user_lat)s)) * sin(radians({LAT_SELECTOR}))
                                ))
                            )
                        ) <= %(max_distance_km)s
                    """
                    params["max_distance_km"] = max_distance_km

                if user_lat is not None:
                    query += " ORDER BY distance_km ASC"

                cur.execute(query, params)
                rows = cur.fetchall()

                results = []
                for row in rows:
                    row_dict = dict(row)
                    distance_val = row_dict.pop("distance_km", None)
                    hike_obj = Hike.from_dict(row_dict)
                    hike_obj.distance_km = distance_val
                    results.append(hike_obj)

                self._attach_items_to_hikes(results)
                return results