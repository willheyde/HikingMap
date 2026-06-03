from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from Auth.authentication import get_current_user_id
from Repos.TripRepo import TripRepository
from Services.TripService import TripService

router = APIRouter(tags=["Trips"])


def get_service() -> TripService:
    return TripService(TripRepository())


def _owned_trip(trip_id: UUID, current_user_id: str, service: TripService):
    """Fetch trip and verify the calling user owns it."""
    try:
        trip = service.get_trip(trip_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Trip not found")
    if str(trip.user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return trip


# ── Request schemas ────────────────────────────────────────────────────────────

class TripCreateRequest(BaseModel):
    title: str
    goal: Optional[str] = None


class StopCreateRequest(BaseModel):
    destination: str
    stop_order: int
    lat: Optional[float] = None
    lng: Optional[float] = None
    duration_days: Optional[int] = None
    activity_type: Optional[str] = None


class StopUpdateRequest(BaseModel):
    duration_days:    Optional[int]            = None
    activity_type:    Optional[str]            = None
    itinerary:        Optional[Dict[str, Any]] = None
    trail_data:       Optional[Dict[str, Any]] = None
    camping:          Optional[Dict[str, Any]] = None
    cost_estimate:    Optional[Dict[str, Any]] = None
    travel_from_prev: Optional[Dict[str, Any]] = None


class GearStatusUpdate(BaseModel):
    status: str     # owned | need_to_buy | optional


class GearAddRequest(BaseModel):
    item_id: UUID
    status: str = "owned"


# ── Trip routes ────────────────────────────────────────────────────────────────

@router.post("/", response_model=dict)
def create_trip(
    payload: TripCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    trip = service.create_trip(
        user_id = UUID(current_user_id),
        title   = payload.title,
        goal    = payload.goal,
    )
    return trip.to_dict()


@router.get("/", response_model=list[dict])
def list_trips(
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    return [t.to_dict() for t in service.list_user_trips(UUID(current_user_id))]


@router.get("/{trip_id}", response_model=dict)
def get_trip(
    trip_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    trip = _owned_trip(trip_id, current_user_id, service)
    return trip.to_dict()


@router.delete("/{trip_id}", status_code=204)
def delete_trip(
    trip_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    _owned_trip(trip_id, current_user_id, service)
    service.delete_trip(trip_id)


# ── Stop routes ────────────────────────────────────────────────────────────────

@router.post("/{trip_id}/stops", response_model=dict)
def add_stop(
    trip_id: UUID,
    payload: StopCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    _owned_trip(trip_id, current_user_id, service)
    try:
        stop = service.add_stop(
            trip_id       = trip_id,
            destination   = payload.destination,
            stop_order    = payload.stop_order,
            lat           = payload.lat,
            lng           = payload.lng,
            duration_days = payload.duration_days,
            activity_type = payload.activity_type,
        )
        return stop.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{trip_id}/stops/{stop_id}", response_model=dict)
def update_stop(
    trip_id: UUID,
    stop_id: UUID,
    payload: StopUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    _owned_trip(trip_id, current_user_id, service)
    try:
        stop = service.update_stop(stop_id, payload.model_dump(exclude_none=True))
        return stop.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{trip_id}/stops/{stop_id}", status_code=204)
def delete_stop(
    trip_id: UUID,
    stop_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    _owned_trip(trip_id, current_user_id, service)
    service.delete_stop(stop_id)


# ── Gear routes ────────────────────────────────────────────────────────────────

@router.post("/{trip_id}/gear", response_model=dict)
def add_gear(
    trip_id: UUID,
    payload: GearAddRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    _owned_trip(trip_id, current_user_id, service)
    gear = service.add_gear(trip_id, payload.item_id, payload.status)
    return gear.to_dict()


@router.patch("/{trip_id}/gear/{item_id}", response_model=dict)
def update_gear_status(
    trip_id: UUID,
    item_id: UUID,
    payload: GearStatusUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    """
    Update the status of a gear item already on the trip.
    Useful for marking need_to_buy items as owned after purchase.
    Uses add_gear with ON CONFLICT DO UPDATE — idempotent.
    """
    _owned_trip(trip_id, current_user_id, service)
    from PyObjects.Trip import TripGearItem
    gear = service.repo.add_gear(TripGearItem(
        trip_id = trip_id,
        item_id = item_id,
        status  = payload.status,
    ))
    return gear.to_dict()


@router.delete("/{trip_id}/gear/{item_id}", status_code=204)
def remove_gear(
    trip_id: UUID,
    item_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
    service: TripService = Depends(get_service),
):
    _owned_trip(trip_id, current_user_id, service)
    service.remove_gear(trip_id, item_id)