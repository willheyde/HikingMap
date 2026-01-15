# Controllers/HikeController.py
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
    """Gear requirement for hike_gear_requirements table"""
    gear_tag: str
    importance: str = "required"  # 'required', 'optional'

class HikeCreateSchema(BaseModel):
    source_id: str
    name: str
    geometry: Dict[str, Any]
    difficulty: str  # "EASY", "MODERATE", "DIFFICULT", "EXPERT"
    length_km: float = Field(gt=0)
    elevation_gain_m: float = Field(ge=0)
    min_altitude_m: float
    max_altitude_m: float
    region: str
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
    geometry: Dict[str, Any]  # Add this
    difficulty: str
    length_km: float
    elevation_gain_m: float
    min_altitude_m: float  # Add this
    max_altitude_m: float  # Add this
    region: str
    season_start_month: int  # Add this
    season_end_month: int  # Add this
    required_gear_tags: List[str]
    permits_required: bool  # Add this
    nearest_airport_code: Optional[str] = None  # Add this
    parking_coordinates: Optional[Dict[str, float]] = None  # Add this
    last_synced_at: str  # Add this (as ISO string)
    # Optional computed fields for convenience
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class HikeUpdateSchema(BaseModel):
    name: Optional[str] = None
    difficulty: Optional[str] = None
    length_km: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    region: Optional[str] = None

# =========================
# Endpoints (Matching JS API)
# =========================

@router.post("/create", response_model=HikeResponseSchema)
def create_hike(payload: HikeCreateSchema):
    """Create a new hike with gear requirements"""
    
    # Convert difficulty string to enum
    try:
        difficulty_enum = DifficultyLevel[payload.difficulty.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid difficulty: {payload.difficulty}")
    
    # Extract gear tags
    gear_tags = [req.gear_tag for req in payload.gear_requirements]
    
    # Create Hike object
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
        season_start_month=payload.season_start_month,
        season_end_month=payload.season_end_month,
        required_gear_tags=gear_tags,
        permits_required=payload.permits_required,
        nearest_airport_code=payload.nearest_airport_code,
        parking_coordinates=payload.parking_coordinates,
        last_synced_at=datetime.utcnow()
    )
    
    try:
        created_hike = hike_service.create_hike(hike)
        
        # Create hike_gear_requirements entries
        _create_gear_requirements(created_hike.id, payload.gear_requirements)
        
        return HikeResponseSchema(
            id=str(created_hike.id),
            source_id=created_hike.source_id,
            name=created_hike.name,
            geometry=created_hike.geometry,  # Add
            difficulty=created_hike.difficulty.name,
            length_km=created_hike.length_km,
            elevation_gain_m=created_hike.elevation_gain_m,
            min_altitude_m=created_hike.min_altitude_m,  # Add
            max_altitude_m=created_hike.max_altitude_m,  # Add
            region=created_hike.region,
            season_start_month=created_hike.season_start_month,  # Add
            season_end_month=created_hike.season_end_month,  # Add
            required_gear_tags=created_hike.required_gear_tags,
            permits_required=created_hike.permits_required,  # Add
            nearest_airport_code=created_hike.nearest_airport_code,  # Add
            parking_coordinates=created_hike.parking_coordinates,  # Add
            last_synced_at=created_hike.last_synced_at.isoformat()  # Add
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create hike: {str(e)}")

@router.get("/get/{hike_id}", response_model=HikeResponseSchema)
def get_hike(hike_id: UUID):
    """Get hike by ID"""
    hike = hike_service.get_hike(hike_id)
    if not hike:
        raise HTTPException(status_code=404, detail="Hike not found")
    
    return HikeResponseSchema(
        id=str(hike.id),
        source_id=hike.source_id,
        name=hike.name,
        geometry=hike.geometry,
        difficulty=hike.difficulty.name,
        length_km=hike.length_km,
        elevation_gain_m=hike.elevation_gain_m,
        min_altitude_m=hike.min_altitude_m,
        max_altitude_m=hike.max_altitude_m,
        region=hike.region,
        season_start_month=hike.season_start_month,
        season_end_month=hike.season_end_month,
        required_gear_tags=hike.required_gear_tags, # This is the array we need for the frontend
        permits_required=hike.permits_required,
        nearest_airport_code=hike.nearest_airport_code,
        parking_coordinates=hike.parking_coordinates,
        last_synced_at=hike.last_synced_at.isoformat(),
        # --- ADDED FIELDS ---
        latitude=hike.latitude,
        longitude=hike.longitude
    )

@router.get("/list", response_model=List[HikeResponseSchema])
def list_hikes():
    """List all hikes"""
    hikes = hike_service.list_hikes()
    return [
        HikeResponseSchema(
            id=str(h.id),
            source_id=h.source_id,
            name=h.name,
            geometry=h.geometry,  # ADD THIS
            difficulty=h.difficulty.name,
            length_km=h.length_km,
            elevation_gain_m=h.elevation_gain_m,
            min_altitude_m=h.min_altitude_m,  # ADD THIS
            max_altitude_m=h.max_altitude_m,  # ADD THIS
            region=h.region,
            season_start_month=h.season_start_month,  # ADD THIS
            season_end_month=h.season_end_month,  # ADD THIS
            required_gear_tags=h.required_gear_tags,
            permits_required=h.permits_required,  # ADD THIS
            nearest_airport_code=h.nearest_airport_code,  # ADD THIS
            parking_coordinates=h.parking_coordinates,  # ADD THIS
            last_synced_at=h.last_synced_at.isoformat()  # ADD THIS
        )
        for h in hikes
    ]

@router.put("/update/{hike_id}", response_model=HikeResponseSchema)
def update_hike(hike_id: UUID, payload: HikeUpdateSchema):
    """Update hike"""
    existing = hike_service.get_hike(hike_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Hike not found")
    
    # Update fields
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
    
    updated = hike_service.update_hike(existing)
    
    return HikeResponseSchema(
        id=str(updated.id),
        source_id=updated.source_id,
        name=updated.name,
        geometry=updated.geometry,  # ADD THIS
        difficulty=updated.difficulty.name,
        length_km=updated.length_km,
        elevation_gain_m=updated.elevation_gain_m,
        min_altitude_m=updated.min_altitude_m,  # ADD THIS
        max_altitude_m=updated.max_altitude_m,  # ADD THIS
        region=updated.region,
        season_start_month=updated.season_start_month,  # ADD THIS
        season_end_month=updated.season_end_month,  # ADD THIS
        required_gear_tags=updated.required_gear_tags,
        permits_required=updated.permits_required,  # ADD THIS
        nearest_airport_code=updated.nearest_airport_code,  # ADD THIS
        parking_coordinates=updated.parking_coordinates,  # ADD THIS
        last_synced_at=updated.last_synced_at.isoformat()  # ADD THIS
    )

@router.delete("/delete/{hike_id}", status_code=204)
def delete_hike(hike_id: UUID):
    """Delete hike"""
    hike_service.delete_hike(hike_id)

@router.get("/search", response_model=List[HikeResponseSchema])
def search_hikes(
    min_length_km: Optional[float] = None,
    min_elevation_gain_m: Optional[float] = None,
    difficulty: Optional[str] = None,
    region: Optional[str] = None,
    month: Optional[int] = None
):
    """Search hikes with filters"""
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
        month=month
    )
    
    response = []
    for h in hikes:
        # Extract Lat/Long from GeoJSON
        latitude = None
        longitude = None
        
        if h.geometry and 'coordinates' in h.geometry:
            coords = h.geometry['coordinates']
            
            if isinstance(coords[0], list):
                longitude = coords[0][0]
                latitude = coords[0][1]
            else:
                longitude = coords[0]
                latitude = coords[1]

        response.append(
            HikeResponseSchema(
                id=str(h.id),
                source_id=h.source_id,
                name=h.name,
                geometry=h.geometry,  # ADD THIS
                difficulty=h.difficulty.name,
                length_km=h.length_km,
                elevation_gain_m=h.elevation_gain_m,
                min_altitude_m=h.min_altitude_m,  # ADD THIS
                max_altitude_m=h.max_altitude_m,  # ADD THIS
                region=h.region,
                season_start_month=h.season_start_month,  # ADD THIS
                season_end_month=h.season_end_month,  # ADD THIS
                required_gear_tags=h.required_gear_tags,
                permits_required=h.permits_required,  # ADD THIS
                nearest_airport_code=h.nearest_airport_code,  # ADD THIS
                parking_coordinates=h.parking_coordinates,  # ADD THIS
                last_synced_at=h.last_synced_at.isoformat(),  # ADD THIS
                latitude=latitude,
                longitude=longitude
            )
        )
        
    return response

# =========================
# Helper Functions
# =========================

def _create_gear_requirements(hike_id: UUID, requirements: List[GearRequirementSchema]):
    """Create entries in hike_gear_requirements table"""
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
                    (uuid4(), hike_id, req.gear_tag, req.importance)
                )