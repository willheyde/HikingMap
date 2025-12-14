from fastapi import APIRouter, HTTPException
from uuid import UUID
from typing import List, Optional, Dict
from Services.UserService import UserService
from Repos.UserRepo import UserRepository
from PyObjects.User import User
from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime

class ItemCreate(BaseModel):
    name: str
    weight: float
    cost: float


class ItemModel(BaseModel):
    name: str
    weight: float
    cost: float


class UserCreate(BaseModel):
    email: EmailStr
    hashed_password: str
    name: str
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, float]] = None
    timezone: Optional[str] = None
    items: Optional[List[ItemModel]] = []


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: Optional[str]
    home_location: Optional[Dict[str, float]]
    timezone: Optional[str]
    items: List[ItemModel]
    created_at: datetime


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    hashed_password: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, float]] = None
    timezone: Optional[str] = None
    items: Optional[List[ItemModel]] = None


router = APIRouter(prefix="/users", tags=["Users"])

# Dependency wiring (simple version)
user_service = UserService(UserRepository())


@router.post("/", response_model=dict)
def create_user(payload: dict):
    try:
        user = user_service.create_user(
            email=payload["email"],
            hashed_password=payload["hashed_password"],
            name=payload["name"],
            avatar_url=payload.get("avatar_url"),
            home_location=payload.get("home_location"),
            timezone=payload.get("timezone"),
            items=payload.get("items", []),
        )
        return user.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/{user_id}", response_model=dict)
def get_user(user_id: UUID):
    user = user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()


@router.get("/", response_model=List[dict])
def list_users():
    return [u.to_dict() for u in user_service.list_users()]


@router.put("/{user_id}", response_model=dict)
def update_user(user_id: UUID, payload: dict):
    existing = user_service.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = User(
        id=user_id,
        email=payload.get("email", existing.email),
        hashed_password=payload.get("hashed_password", existing.hashed_password),
        name=payload.get("name", existing.name),
        avatar_url=payload.get("avatar_url", existing.avatar_url),
        home_location=payload.get("home_location", existing.home_location),
        timezone=payload.get("timezone", existing.timezone),
        items=payload.get("items", existing.items),
        created_at=existing.created_at,
    )

    try:
        user = user_service.update_user(updated_user)
        return user.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


    try:
        user = user_service.update_user(updated_user)
        return user.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: UUID):
    try:
        user_service.delete_user(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
@router.get("/", response_model = UserResponse)
def createUser(req: UserCreate):
    try:
        user = user_service.create_user(
            email=req.email,
            hashed_password=req.hashed_password,
            name=req.name,
            avatar_url=req.avatar_url,
            home_location=req.home_location,
            timezone=req.timezone,
        )
        return user.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.get("/{user_id}/items", response_model=list[dict])
def get_user_items(user_id: UUID):
    try:
        items = user_service.list_items(user_id)
        return [i.to_dict() for i in items]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
@router.post("/{user_id}/items", response_model=dict)
def add_user_item(user_id: UUID, payload: ItemCreate):
    try:
        item = user_service.add_item(user_id, payload.dict())
        return item.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
@router.delete("/{user_id}/items/{item_index}", status_code=204)
def delete_user_item(user_id: UUID, item_index: int):
    try:
        user_service.delete_item(user_id, item_index)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))