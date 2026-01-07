from fastapi import APIRouter, HTTPException
from uuid import UUID
from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, EmailStr

# Import your internal layers
# Ensure these match your actual folder names
from Services.UserService import UserService
from Repos.UserRepo import UserRepository
from PyObjects.User import User
from PyObjects.Items import Item

# ---------------------------------------------------------
# Pydantic Models (Request/Response Schemas)
# ---------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str

class ItemCreate(BaseModel):
    name: str
    # Add other item fields if your Item.from_dict expects them
    # For now, we assume simple items or you can expand this

class UserCreate(BaseModel):
    email: EmailStr
    hashed_password: str
    name: str
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, float]] = None
    timezone: Optional[str] = None
    items: Optional[List[dict]] = []

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    hashed_password: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, float]] = None
    timezone: Optional[str] = None
    items: Optional[List[dict]] = None

# ---------------------------------------------------------
# Router Setup
# ---------------------------------------------------------

router = APIRouter(prefix="/users", tags=["Users"])

# Dependency Injection
# We create the service here so the endpoints can use it.
user_repo = UserRepository()
user_service = UserService(user_repo)

# ---------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------

@router.post("/login", response_model=dict)
def login(payload: LoginRequest):
    """
    Verifies email and password. Returns user data if successful.
    """
    # Note: verify you added login_user to UserService as discussed!
    user = user_service.login_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user.to_dict()

# ---------------------------------------------------------
# User CRUD
# ---------------------------------------------------------

@router.post("/", response_model=dict)
def create_user(payload: UserCreate):
    try:
        user = user_service.create_user(
            email=payload.email,
            hashed_password=payload.hashed_password,
            name=payload.name,
            avatar_url=payload.avatar_url,
            home_location=payload.home_location,
            timezone=payload.timezone,
            items=payload.items,
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
def update_user(user_id: UUID, payload: UserUpdate):
    # 1. Fetch existing
    existing = user_service.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Merge updates
    # We construct a new User object merging old data with new payload
    updated_user = User(
        id=user_id,
        email=payload.email or existing.email,
        hashed_password=payload.hashed_password or existing.hashed_password,
        name=payload.name or existing.name,
        avatar_url=payload.avatar_url or existing.avatar_url,
        home_location=payload.home_location or existing.home_location,
        timezone=payload.timezone or existing.timezone,
        items=[Item.from_dict(i) for i in payload.items] if payload.items is not None else existing.items,
        created_at=existing.created_at,
    )

    try:
        result = user_service.update_user(updated_user)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: UUID):
    try:
        user_service.delete_user(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

# ---------------------------------------------------------
# Item Sub-Endpoints
# ---------------------------------------------------------

@router.get("/{user_id}/items", response_model=List[dict])
def get_user_items(user_id: UUID):
    try:
        items = user_service.list_items(user_id)
        return [i.to_dict() for i in items]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{user_id}/items", response_model=dict)
def add_user_item(user_id: UUID, payload: ItemCreate):
    try:
        # Convert Pydantic model to dict for the service
        item_data = payload.dict()
        # Ensure default values if your Item object needs them
        if "weight" not in item_data: item_data["weight"] = 0.0
        if "cost" not in item_data: item_data["cost"] = 0.0
        
        item = user_service.add_item(user_id, item_data)
        return item.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{user_id}/items/{item_index}", status_code=204)
def delete_user_item(user_id: UUID, item_index: int):
    try:
        user_service.delete_item(user_id, item_index)
    except ValueError as e:
        # Index out of bounds or user not found
        raise HTTPException(status_code=404, detail=str(e))