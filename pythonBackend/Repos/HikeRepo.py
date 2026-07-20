import json
from uuid import UUID
from typing import List, Optional
from PyObjects.Hike import Hike
from Repos.RepositoryBase import BaseRepository
from DBConnection import get_connection
from PyObjects.Hike import Hike, DifficultyLevel



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
                        region, state,
                        season_start_month, season_end_month,
                        permits_required, nearest_airport_code, parking_coordinates,
                        last_synced_at, tags, can_camp,
                        lat, lng, gear_requirements, trail_shape, campsites
                    ) VALUES (
                        %(id)s, %(source_id)s, %(name)s, %(geometry)s,
                        %(difficulty)s, %(length_km)s, %(elevation_gain_m)s,
                        %(min_altitude_m)s, %(max_altitude_m)s,
                        %(region)s, %(state)s,
                        %(season_start_month)s, %(season_end_month)s,
                        %(permits_required)s, %(nearest_airport_code)s, %(parking_coordinates)s,
                        %(last_synced_at)s, %(tags)s, %(can_camp)s,
                        %(lat)s, %(lng)s, %(gear_requirements)s, %(trail_shape)s, %(campsites)s
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
                        "state":                hike.state,          # ← NEW
                        "season_start_month":   hike.season_start_month,
                        "season_end_month":     hike.season_end_month,
                        "permits_required":     hike.permits_required,
                        "nearest_airport_code": hike.nearest_airport_code,
                        "parking_coordinates":  json.dumps(hike.parking_coordinates) if hike.parking_coordinates else None,
                        "last_synced_at":       hike.last_synced_at,
                        "tags":                 hike.tags,
                        "can_camp":             hike.can_camp,
                        "lat":                  hike.lat,
                        "lng":                  hike.lng,
                        "gear_requirements":    json.dumps(hike.gear_requirements or {}),
                        "trail_shape":          hike.trail_shape,
                        "campsites":            json.dumps(hike.campsites or []),
                    }
                )
        return hike

    def get_by_source_id(self, source_id: str) -> Optional[Hike]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM hikes WHERE source_id = %s", (source_id,))
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

    # new
    def update(self, hike: Hike) -> Hike:
        with get_connection() as conn:
            with conn.cursor() as cur:
                params = hike.to_dict()
                params["geometry"] = json.dumps(params["geometry"])
                params["gear_requirements"] = json.dumps(params.get("gear_requirements") or {})
                params["campsites"] = json.dumps(params.get("campsites") or [])
                cur.execute(
                    """
                    UPDATE hikes SET
                        source_id=%(source_id)s,
                        name=%(name)s,
                        geometry=%(geometry)s,
                        difficulty=%(difficulty)s,
                        length_km=%(length_km)s,
                        elevation_gain_m=%(elevation_gain_m)s,
                        min_altitude_m=%(min_altitude_m)s,
                        max_altitude_m=%(max_altitude_m)s,
                        region=%(region)s,
                        state=%(state)s,
                        season_start_month=%(season_start_month)s,
                        season_end_month=%(season_end_month)s,
                        permits_required=%(permits_required)s,
                        nearest_airport_code=%(nearest_airport_code)s,
                        last_synced_at=%(last_synced_at)s,
                        tags=%(tags)s,
                        can_camp=%(can_camp)s,
                        lat=%(lat)s,
                        lng=%(lng)s,
                        gear_requirements=%(gear_requirements)s,
                        trail_shape=%(trail_shape)s,
                        campsites=%(campsites)s
                    WHERE id=%(id)s
                    """,
                    params
                )
        return hike

    def delete(self, hike_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM hikes WHERE id=%s", (hike_id,))

    def search_by_name(self, query: str, limit: int = 5) -> List[Hike]:
        """
        Direct trail-name lookup for the trip planner's "I want to hike <name>"
        path (there is no name search in `search()` — that's filter-only).

        Matches containment in EITHER direction, case-insensitively:
          - the trail name contains the user's phrase
            ("sterling" → "Mount Sterling Trail")
          - the user's phrase contains the trail name
            ("the Mount Sterling Trail, please" → "Mount Sterling Trail")

        Results are ordered by MATCH QUALITY, not raw name length: an exact
        (trimmed, case-insensitive) name match first, then forward-containment
        (name contains the query), then the weaker reverse-containment (query
        contains the name) last — with shorter names breaking ties within a
        tier. Ordering by length alone was a real bug: the DB is full of ultra-
        generic OSM names ("Trail", "Rail", "Red"), and the reverse-containment
        clause matches every one of them as a substring of a real query
        ("Weiss Main Trail" contains "Trail" and "rail"). Length-ASC then floated
        that junk to the top and LIMIT truncated the actual trail away before the
        caller ever saw it, so "plan a trip to Weiss Main Trail" resolved to a
        pile of nameless "Trail" rows.

        The reverse-containment clause is additionally guarded to names of >= 5
        chars so the shortest generic tokens ("Red", "Rail") can't hijack a query
        by appearing as an incidental substring; a genuine name the user typed
        still matches forward regardless of length.

        Collapsing several rows into a single confident pick (vs a disambiguation
        set) is the caller's job.
        """
        q = (query or "").strip()
        if not q:
            return []
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM hikes
                    WHERE name ILIKE %(contains)s
                       OR (char_length(name) >= 5 AND %(q)s ILIKE '%%' || name || '%%')
                    ORDER BY
                        CASE
                            WHEN lower(btrim(name)) = lower(btrim(%(q)s)) THEN 0
                            WHEN name ILIKE %(contains)s                  THEN 1
                            ELSE                                               2
                        END ASC,
                        -- Tie-break within a tier: for exact/forward matches the
                        -- SHORTER name is the tighter fit ("Sterling" → prefer
                        -- "Mount Sterling Trail" over "…Ridge Trail"); for a
                        -- reverse match the LONGER name covers more of the query
                        -- and is the better hit, so flip the sign there.
                        CASE WHEN name ILIKE %(contains)s
                             THEN  length(name)
                             ELSE -length(name)
                        END ASC
                    LIMIT %(limit)s
                    """,
                    {"contains": f"%{q}%", "q": q, "limit": limit},
                )
                rows = cur.fetchall()
        return [Hike.from_dict(dict(r)) for r in rows]

    def search(
        self,
        min_length_km=None,
        min_elevation_gain_m=None,
        difficulty=None,
        region=None,
        state=None,                  # ← NEW
        month=None,
        user_lat=None,
        user_lon=None,
        max_distance_km=None,
        required_tags: Optional[List[str]] = None,
        can_camp: Optional[bool] = None,
        permits_required: Optional[bool] = None,
        max_length_km: Optional[float] = None,
        bbox_min_lng: Optional[float] = None,
        bbox_min_lat: Optional[float] = None,
        bbox_max_lng: Optional[float] = None,
        bbox_max_lat: Optional[float] = None,
        limit: Optional[int] = None,
    ):
        with get_connection() as conn:
            with conn.cursor() as cur:

                if user_lat is not None and user_lon is not None:
                    query = """
                        SELECT *,
                            (
                                6371 * acos(
                                    least(1.0, greatest(-1.0,
                                        cos(radians(%(user_lat)s)) * cos(radians(lat))
                                        * cos(radians(lng) - radians(%(user_lon)s))
                                        + sin(radians(%(user_lat)s)) * sin(radians(lat))
                                    ))
                                )
                            ) AS distance_km
                        FROM hikes
                        WHERE 1=1
                    """
                    params = {"user_lat": user_lat, "user_lon": user_lon}
                else:
                    query  = "SELECT *, NULL AS distance_km FROM hikes WHERE 1=1"
                    params = {}

                if min_length_km is not None:
                    query += " AND length_km >= %(min_length_km)s"
                    params["min_length_km"] = min_length_km

                if min_elevation_gain_m is not None:
                    query += " AND elevation_gain_m >= %(min_elevation_gain_m)s"
                    params["min_elevation_gain_m"] = min_elevation_gain_m
                if max_length_km is not None:
                    query += " AND length_km <= %(max_length_km)s"
                    params["max_length_km"] = max_length_km
                if difficulty is not None:
                    query += " AND difficulty = %(difficulty)s"
                    params["difficulty"] = difficulty.name

                if region is not None:
                    query += " AND region = %(region)s"
                    params["region"] = region
                
                if state is not None:
                    query += " AND UPPER(state) = UPPER(%(state)s)"   # was: AND state = %(state)s
                    params["state"] = state

                if month is not None:
                    query += """
                        AND season_start_month <= %(month)s
                        AND season_end_month   >= %(month)s
                    """
                    params["month"] = month

                if required_tags:
                    query += " AND tags @> %(required_tags)s"
                    params["required_tags"] = required_tags

                if can_camp is True:
                    query += " AND can_camp = TRUE"

                if permits_required is False:
                    query += " AND permits_required = FALSE"

                if max_distance_km is not None and user_lat is not None:
                    query += """
                        AND (
                            6371 * acos(
                                least(1.0, greatest(-1.0,
                                    cos(radians(%(user_lat)s)) * cos(radians(lat))
                                    * cos(radians(lng) - radians(%(user_lon)s))
                                    + sin(radians(%(user_lat)s)) * sin(radians(lat))
                                ))
                            )
                        ) <= %(max_distance_km)s
                    """
                    params["max_distance_km"] = max_distance_km

                # Viewport bounding box — filters on the trailhead lat/lng
                # columns. Only applied when all four bounds are present; a
                # partial box is ignored rather than half-filtering. This is
                # what keeps a map pan from refetching the entire hikes table.
                if None not in (bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat):
                    query += """
                        AND lat BETWEEN %(bbox_min_lat)s AND %(bbox_max_lat)s
                        AND lng BETWEEN %(bbox_min_lng)s AND %(bbox_max_lng)s
                    """
                    params["bbox_min_lat"] = bbox_min_lat
                    params["bbox_max_lat"] = bbox_max_lat
                    params["bbox_min_lng"] = bbox_min_lng
                    params["bbox_max_lng"] = bbox_max_lng

                if user_lat is not None:
                    query += " ORDER BY distance_km ASC"

                # Hard cap on rows returned. Without this the map's RESULT_LIMIT
                # was a no-op and every search streamed the full table.
                if limit is not None:
                    query += " LIMIT %(limit)s"
                    params["limit"] = limit

                cur.execute(query, params)
                rows = cur.fetchall()

                results = []
                for row in rows:
                    row_dict = dict(row)
                    distance_val = row_dict.pop("distance_km", None)
                    hike_obj = Hike.from_dict(row_dict)
                    hike_obj.distance_km = distance_val
                    results.append(hike_obj)

                # required_gear_tags is derived from gear_requirements in
                # Hike.from_dict — no legacy hike_items join needed.
                return results