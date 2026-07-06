from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from PyObjects.Hike import Hike, DifficultyLevel
from Repos.HikeRepo import HikeRepository
from Services.HikeService import HikeService

router = APIRouter(tags=["Hikes"])

hike_repo = HikeRepository()
hike_service = HikeService(hike_repo)


# =========================
# Schemas
# =========================

class GearRequirementSchema(BaseModel):
    gear_tag: str
    importance: str = "required"

class HikeCreateSchema(BaseModel):
    source_id: str
    name: str
    geometry: Dict[str, Any]
    difficulty: str
    length_km: float = Field(gt=0)
    elevation_gain_m: float = Field(ge=0)
    min_altitude_m: float
    max_altitude_m: float
    region: str
    state: Optional[str] = None          # ← NEW
    season_start_month: int = Field(ge=1, le=12)
    season_end_month: int = Field(ge=1, le=12)
    permits_required: bool = False
    nearest_airport_code: Optional[str] = None
    parking_coordinates: Optional[Dict[str, float]] = None
    gear_requirements: List[GearRequirementSchema] = Field(default_factory=list)

class HikeResponseSchema(BaseModel):
    id: str
    source_id: str
    name: str
    geometry: Dict[str, Any]
    difficulty: str
    length_km: float
    elevation_gain_m: float
    min_altitude_m: float
    max_altitude_m: float
    region: str
    state: Optional[str] = None          # ← NEW
    season_start_month: int
    season_end_month: int
    required_gear_tags: List[str]
    permits_required: bool
    nearest_airport_code: Optional[str] = None
    parking_coordinates: Optional[Dict[str, float]] = None
    last_synced_at: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None

class HikeUpdateSchema(BaseModel):
    name: Optional[str] = None
    difficulty: Optional[str] = None
    length_km: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    region: Optional[str] = None
    state: Optional[str] = None          # ← NEW


# =========================
# Helper: build response
# =========================

def _to_response(h: Hike, **extra) -> HikeResponseSchema:
    """Single place that maps a Hike → HikeResponseSchema."""
    return HikeResponseSchema(
        id=str(h.id),
        source_id=h.source_id,
        name=h.name,
        geometry=h.geometry,
        difficulty=h.difficulty.name,
        length_km=h.length_km,
        elevation_gain_m=h.elevation_gain_m,
        min_altitude_m=h.min_altitude_m,
        max_altitude_m=h.max_altitude_m,
        region=h.region,
        state=h.state,                   # ← NEW
        season_start_month=h.season_start_month,
        season_end_month=h.season_end_month,
        required_gear_tags=h.required_gear_tags,
        permits_required=h.permits_required,
        nearest_airport_code=h.nearest_airport_code,
        parking_coordinates=h.parking_coordinates,
        last_synced_at=h.last_synced_at.isoformat(),
        latitude=h.lat,
        longitude=h.lng,
        distance_km=getattr(h, "distance_km", None),
        **extra,
    )


# =========================
# Endpoints
# =========================

@router.post("/create", response_model=HikeResponseSchema)
def create_hike(payload: HikeCreateSchema):
    try:
        difficulty_enum = DifficultyLevel[payload.difficulty.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid difficulty: {payload.difficulty}")

    hike = Hike(
        id=uuid4(),
        source_id=payload.source_id,
        name=payload.name,
        geometry=payload.geometry,
        difficulty=difficulty_enum,
        length_km=payload.length_km,
        elevation_gain_m=payload.elevation_gain_m,
        min_altitude_m=payload.min_altitude_m,
        max_altitude_m=payload.max_altitude_m,
        region=payload.region,
        state=payload.state,             # ← NEW
        season_start_month=payload.season_start_month,
        season_end_month=payload.season_end_month,
        required_gear_tags=[req.gear_tag for req in payload.gear_requirements],
        permits_required=payload.permits_required,
        nearest_airport_code=payload.nearest_airport_code,
        parking_coordinates=payload.parking_coordinates,
        last_synced_at=datetime.utcnow(),
    )

    try:
        created = hike_service.create_hike(hike)
        _create_gear_requirements(created.id, payload.gear_requirements)
        return _to_response(created)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create hike: {str(e)}")


@router.get("/get/{hike_id}", response_model=HikeResponseSchema)
def get_hike(hike_id: UUID):
    hike = hike_service.get_hike(hike_id)
    if not hike:
        raise HTTPException(status_code=404, detail="Hike not found")
    return _to_response(hike)


@router.get("/list", response_model=List[HikeResponseSchema])
def list_hikes():
    return [_to_response(h) for h in hike_service.list_hikes()]


@router.put("/update/{hike_id}", response_model=HikeResponseSchema)
def update_hike(hike_id: UUID, payload: HikeUpdateSchema):
    existing = hike_service.get_hike(hike_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Hike not found")

    if payload.name:
        existing.name = payload.name
    if payload.difficulty:
        existing.difficulty = DifficultyLevel[payload.difficulty.upper()]
    if payload.length_km:
        existing.length_km = payload.length_km
    if payload.elevation_gain_m:
        existing.elevation_gain_m = payload.elevation_gain_m
    if payload.region:
        existing.region = payload.region
    if payload.state is not None:        # ← NEW (allow clearing with empty string)
        existing.state = payload.state

    return _to_response(hike_service.update_hike(existing))


@router.delete("/delete/{hike_id}", status_code=204)
def delete_hike(hike_id: UUID):
    hike_service.delete_hike(hike_id)


@router.get("/search", response_model=List[HikeResponseSchema])
def search_hikes(
    min_length_km: Optional[float] = None,
    min_elevation_gain_m: Optional[float] = None,
    difficulty: Optional[str] = None,
    region: Optional[str] = None,
    state: Optional[str] = None,        # ← NEW
    month: Optional[int] = None,
    user_lat: Optional[float] = None,
    user_lon: Optional[float] = None,
    max_dist: Optional[float] = None,
    max_length_km: Optional[float] = None,  # ← NEW
):
    difficulty_enum = None
    if difficulty:
        try:
            difficulty_enum = DifficultyLevel[difficulty.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid difficulty: {difficulty}")

    hikes = hike_service.search_hikes(
        min_length_km=min_length_km,
        min_elevation_gain_m=min_elevation_gain_m,
        difficulty=difficulty_enum,
        region=region,
        state=state,                     # ← NEW
        month=month,
        user_lat=user_lat,
        user_lon=user_lon,
        max_distance_km=max_dist,
        max_length_km=max_length_km,    # ← NEW
    )

    return [_to_response(h) for h in hikes]


# =========================
# Helper Functions
# =========================

def _create_gear_requirements(hike_id: UUID, requirements: List[GearRequirementSchema]):
    from DBConnection import get_connection
    if not requirements:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            for req in requirements:
                cur.execute(
                    """
                    INSERT INTO hike_gear_requirements (id, hike_id, gear_tag, importance)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (uuid4(), hike_id, req.gear_tag, req.importance),
                )