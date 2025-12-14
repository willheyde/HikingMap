# Controllers/hike_controller.py
from fastapi import APIRouter, HTTPException
from uuid import UUID, uuid4

from PyObjects.Hike import Hike
from Repos.HikeRepo import HikeRepository
from Services.HikeService import HikeService

router = APIRouter()

# Dependency wiring (manual for now, clean + explicit)
repo = HikeRepository()
service = HikeService(repo)
@router.post("/", response_model=dict)
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
@router.get("/{hike_id}", response_model=dict)
def get_hike(hike_id: UUID):
    hike = service.get_hike(hike_id)
    if not hike:
        raise HTTPException(status_code=404, detail="Hike not found")
    return hike.to_dict()
@router.get("/", response_model=list[dict])
def list_hikes():
    return [h.to_dict() for h in service.list_hikes()]
@router.put("/{hike_id}", response_model=dict)
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
@router.delete("/{hike_id}")
def delete_hike(hike_id: UUID):
    service.delete_hike(hike_id)
    return {"status": "deleted"}
