# api/schemas/trip.py
from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID
from pydantic import BaseModel
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from Services.TripService import TripService
from Repos.TripRepo import TripRepository
from PyObjects.Trip import TravelMode


class TravelModeSchema(str, Enum):
    drive = "drive"
    fly = "fly"
    mixed = "mixed"


class TripCreateRequest(BaseModel):
    hike_id: UUID
    start_date: datetime
    end_date: datetime
    origin_point: Dict[str, float]
    travel_mode: TravelModeSchema


class TripResponse(BaseModel):
    id: UUID
    user_id: UUID
    hike_id: UUID
    start_date: datetime
    end_date: datetime
    origin_point: Dict[str, float]
    travel_mode: TravelModeSchema
    travel_estimate: Dict[str, Any]
    missing_gear: List[str]
    shopping_estimate: Dict[str, Any]
    created_at: datetime
# api/controllers/trip_controller.py


router = APIRouter(prefix="/trips", tags=["Trips"])


def get_trip_service() -> TripService:
    repo = TripRepository()
    return TripService(repo)


@router.post("/", response_model=TripResponse)
def create_trip(
    req: TripCreateRequest,
    user_id: UUID,  # eventually from auth
    service: TripService = Depends(get_trip_service),
):
    try:
        trip = service.create_trip(
            user_id=user_id,
            hike_id=req.hike_id,
            start_date=req.start_date,
            end_date=req.end_date,
            origin_point=req.origin_point,
            travel_mode=TravelMode(req.travel_mode.value),
        )
        return trip.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: UUID,
    service: TripService = Depends(get_trip_service),
):
    try:
        return service.get_trip(trip_id).to_dict()
    except ValueError:
        raise HTTPException(status_code=404, detail="Trip not found")


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: UUID,
    service: TripService = Depends(get_trip_service),
):
    service.delete_trip(trip_id)
    return {"status": "deleted"}
@router.get("/", response_model = TripResponse)
def createTrip(req: TripCreateRequest, user_id: UUID, service: TripService = Depends(get_trip_service)):
    try:
        trip = service.create_trip(
            user_id=user_id,
            hike_id=req.hike_id,
            start_date=req.start_date,
            end_date=req.end_date,
            origin_point=req.origin_point,
            travel_mode=TravelMode(req.travel_mode.value),
        )
        return trip.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))