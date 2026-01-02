# Controllers/hike_controller.py
from fastapi import APIRouter, HTTPException
from uuid import UUID, uuid4

from PyObjects.Hike import Hike
from Repos.HikeRepo import HikeRepository
from Services.HikeService import HikeService
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum
from typing import Dict, Any

class DifficultyLevelSchema(str,Enum):
    EASY = "EASY"
    MODERATE = "MODERATE"
    DIFFICULT = "DIFFICULT"
    EXPERT = "EXPERT"


class HikeCreateRequest(BaseModel):
    source_id: str
    name: str
    geometry: Dict[str, Any]
    difficulty: DifficultyLevelSchema
    length_km: float = Field(ge=0)
    elevation_gain_m: float = Field(ge=0)
    min_altitude_m: float
    max_altitude_m: float
    region: str
    season_start_month: int = Field(ge=1, le=12)
    season_end_month: int = Field(ge=1, le=12)
    required_gear_tags: List[str] = []
    permits_required: bool = False
    nearest_airport_code: Optional[str] = None
    parking_coordinates: Optional[Dict[str, float]] = None
class HikeResponse(BaseModel):
    id: UUID
    source_id: str
    name: str
    geometry: Dict[str, Any]
    difficulty: DifficultyLevelSchema
    length_km: float
    elevation_gain_m: float
    min_altitude_m: float
    max_altitude_m: float
    region: str
    season_start_month: int
    season_end_month: int
    required_gear_tags: List[str]
    permits_required: bool
    nearest_airport_code: Optional[str]
    parking_coordinates: Optional[Dict[str, float]]
    last_synced_at: datetime
class HikeUpdateRequest(BaseModel):
    name: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    difficulty: Optional[DifficultyLevelSchema] = None
    length_km: Optional[float] = Field(default=None, ge=0)
    elevation_gain_m: Optional[float] = Field(default=None, ge=0)
    region: Optional[str] = None
    required_gear_tags: Optional[List[str]] = None
    permits_required: Optional[bool] = None
    nearest_airport_code: Optional[str] = None
    parking_coordinates: Optional[Dict[str, float]] = None

router = APIRouter()

# Dependency wiring (manual for now, clean + explicit)
repo = HikeRepository()
service = HikeService(repo)
@router.post("/create", response_model=dict)
def create_hike(hike_data: dict):
    try:
        hike = Hike.from_dict({
            **hike_data,
            "id": uuid4()
        })
        created = service.create_hike(hike)
        return created.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.get("/get/{hike_id}", response_model=dict)
def get_hike(hike_id: UUID):
    hike = service.get_hike(hike_id)
    if not hike:
        raise HTTPException(status_code=404, detail="Hike not found")
    return hike.to_dict()
@router.get("/list", response_model=list[dict])
def list_hikes():
    return [h.to_dict() for h in service.list_hikes()]
@router.put("/update/{hike_id}", response_model=dict)
def update_hike(hike_id: UUID, hike_data: dict):
    try:
        hike = Hike.from_dict({
            **hike_data,
            "id": hike_id
        })
        updated = service.update_hike(hike)
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.delete("/delete/{hike_id}")
def delete_hike(hike_id: UUID):
    service.delete_hike(hike_id)
    return {"status": "deleted"}

@router.get("/search", response_model=List[HikeResponse])
def searchHikes(
    min_length_km: float | None = None,
    min_elevation_gain_m: float | None = None,
    farthest_hike_latitude_m: float | None = None,
    farthest_hike_longitude_m: float | None = None,
    difficulty: DifficultyLevelSchema | None = None,
    region: str | None = None,
    month: int | None = None,
):
    hikes = service.search_hikes(
        min_length_km=min_length_km,
        min_elevation_gain_m=min_elevation_gain_m,
        farthest_hike_latitude_m=farthest_hike_latitude_m,
        farthest_hike_longitude_m=farthest_hike_longitude_m,
        difficulty=difficulty,
        region=region,
        month=month,
    )
    return [h.to_dict() for h in hikes]  # Convert to dicts

