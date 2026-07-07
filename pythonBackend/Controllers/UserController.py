import psycopg
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr

from Services.UserService import UserService
from Services.ItemService import ItemService
from Repos.UserRepo import UserRepository
from Repos.ItemRepo import ItemRepository
from PyObjects.User import User
from PyObjects.Items import Item
from Auth.authentication import hash_password, verify_password, create_access_token, get_current_user_id
from Schemas.UserSchemas import TokenResponse
from gear_levels import GEAR_CATEGORIES, is_valid_level, valid_levels

# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    items: Optional[List[dict]] = []

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    hashed_password: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    items: Optional[List[dict]] = None

# FIX 1: Replaces ItemCreate (which had `name: str`).
# Item endpoints work with IDs from the existing items table —
# the client never sends item fields, just the UUID it wants to link.
class ItemAdd(BaseModel):
    item_id: str  # UUID of an existing item in the `items` table

class ItemsBatchAdd(BaseModel):
    item_ids: List[str]  # list of UUIDs

# Free-text "I have this" gear: a functional category (+ optional capability
# level) rather than a catalog item_id. See gear_levels.py for the vocabulary.
class GearAdd(BaseModel):
    name:          str
    gear_category: str
    level:         Optional[str]   = None
    weight:        float           = 0.0   # grams
    cost:          float           = 0.0   # USD
    temp_rating_f: Optional[float] = None  # sleep bags only

# ---------------------------------------------------------
# Router
# ---------------------------------------------------------

router = APIRouter(tags=["Users"])

user_repo = UserRepository()
user_service = UserService(user_repo)
item_service = ItemService(ItemRepository())

# ---------------------------------------------------------
# Auth
# ---------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest):
    user = user_service.get_user_by_email(credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user_id=str(user.id), name=user.name)

# ---------------------------------------------------------
# User CRUD
# ---------------------------------------------------------

# FIX 2: Removed the duplicate @router.post("/") decorator.
@router.post("/", response_model=dict)
def create_user(payload: UserCreate):
    try:
        hashed_pw = hash_password(payload.password)
        user = user_service.create_user(
            email=payload.email,
            hashed_password=hashed_pw,
            name=payload.name,
            avatar_url=payload.avatar_url,
            home_location=payload.home_location,
            timezone=payload.timezone,
        )
        return {"user_id": str(user.id), "name": user.name, "email": user.email}
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{user_id}", response_model=dict)
def get_user(user_id: UUID):
    user = user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = user.to_dict()
    data.pop("hashed_password", None)
    return data

@router.get("/", response_model=List[dict])
def list_users():
    return [u.to_dict() for u in user_service.list_users()]

@router.put("/{user_id}", response_model=dict)
def update_user(user_id: UUID, payload: UserUpdate):
    existing = user_service.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

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
# Item sub-endpoints
# ---------------------------------------------------------

@router.get("/{user_id}/items", response_model=list[dict])
def get_user_items(user_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    items = user_service.list_items(user_id)
    return [i.to_dict() for i in items]

# FIX 3: Schema changed from ItemCreate (name: str) to ItemAdd (item_id: str).
# The service's add_item() expects a string UUID — we now pass payload.item_id directly.
# Response is list[dict] because the service refetches and returns the full updated list.
@router.post("/{user_id}/items", response_model=list[dict])
def add_user_item(
    user_id: UUID,
    payload: ItemAdd,
    current_user_id: str = Depends(get_current_user_id),
):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        updated_items = user_service.add_item(user_id, payload.item_id)
        return [i.to_dict() for i in updated_items]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# FIX 4: Added the batch endpoint the frontend already calls but the router was missing.
@router.post("/{user_id}/items/batch", response_model=list[dict])
def add_user_items_batch(
    user_id: UUID,
    payload: ItemsBatchAdd,
    current_user_id: str = Depends(get_current_user_id),
):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        updated_items = user_service.add_items_batch(user_id, payload.item_ids)
        return [i.to_dict() for i in updated_items]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Free-text gear add: creates a user-owned item from a functional category
# (+ optional capability level) instead of linking an existing catalog item_id.
@router.post("/{user_id}/gear", response_model=dict)
def add_user_gear(
    user_id: UUID,
    payload: GearAdd,
    current_user_id: str = Depends(get_current_user_id),
):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    category = payload.gear_category.strip().lower()
    if category not in GEAR_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid gear_category '{payload.gear_category}'. "
                   f"Must be one of: {', '.join(sorted(GEAR_CATEGORIES))}.",
        )
    if not is_valid_level(category, payload.level):
        allowed = valid_levels(category)
        raise HTTPException(
            status_code=400,
            detail=(f"Invalid level '{payload.level}' for {category}. "
                    + (f"Must be one of: {', '.join(allowed)}." if allowed
                       else f"{category} does not take a level.")),
        )

    try:
        item = item_service.create_user_gear(
            user_id       = user_id,
            name          = payload.name.strip() or category.replace("_", " ").title(),
            gear_category = category,
            level         = payload.level,
            weight        = payload.weight,
            cost          = payload.cost,
            temp_rating_f = payload.temp_rating_f,
        )
        return item.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# FIX 5: Path param renamed item_index: int → item_id: UUID, matching the service
# signature (delete_item expects a string UUID, not a list index).
@router.delete("/{user_id}/items/{item_id}", status_code=204)
def delete_user_item(
    user_id: UUID,
    item_id: UUID,
    current_user_id: str = Depends(get_current_user_id),
):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        user_service.delete_item(user_id, str(item_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))