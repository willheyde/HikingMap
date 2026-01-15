from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from typing import List, Dict, Any
import hashlib

# --- FIX: Import Models from Schemas ---
from Schemas.UserSchemas import UserCreate, LoginRequest, UserUpdate, ItemLink
# ---------------------------------------

from Services.UserService import UserService
from Repos.UserRepo import UserRepository

router = APIRouter(tags=["Users"])
user_service = UserService(UserRepository())

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ... login, create_user, list_users, get_user, update_user, delete_user ... (Unchanged)
# (Copy paste your existing ones here)

@router.post("/login", response_model=dict)
def login(credentials: LoginRequest):
    # ... existing implementation ...
    try:
        user = user_service.get_user_by_email(credentials.email)
        if not user: raise HTTPException(status_code=401, detail="Invalid")
        hashed = hash_password(credentials.password)
        if user.hashed_password != hashed: raise HTTPException(status_code=401, detail="Invalid")
        return user.to_dict()
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@router.post("/", response_model=dict)
def create_user(payload: UserCreate):
    hashed_pw = hash_password(payload.password)
    user = user_service.create_user(
        email=payload.email, hashed_password=hashed_pw, name=payload.name,
        avatar_url=payload.avatar_url, home_location=payload.home_location, timezone=payload.timezone
    )
    return user.to_dict()

@router.get("/{user_id}", response_model=dict)
def get_user(user_id: UUID):
    user = user_service.get_user(user_id)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()

# --- CHANGED ENDPOINTS ---

@router.get("/{user_id}/items", response_model=list[dict])
def get_user_items(user_id: UUID):
    try:
        items = user_service.list_items(user_id)
        return [i.to_dict() for i in items]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# 1. INDIVIDUAL ADD (Expects { "item_id": "..." })
@router.post("/{user_id}/items", response_model=List[dict])
def add_user_item(user_id: UUID, payload: ItemLink):
    try:
        # Returns full list of items after add
        items = user_service.add_item(user_id, payload.item_id)
        return [i.to_dict() for i in items]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# 2. BATCH ADD (Expects [ "id1", "id2" ])
@router.post("/{user_id}/items/batch", response_model=List[dict])
def add_user_items_batch(user_id: UUID, payload: List[str]):
    try:
        # Payload is now just a list of strings (UUIDs)
        items = user_service.add_items_batch(user_id, payload)
        return [i.to_dict() for i in items]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# 3. DELETE (Uses item_id in URL, not index)
@router.delete("/{user_id}/items/{item_id}", status_code=204)
def delete_user_item(user_id: UUID, item_id: str):
    try:
        user_service.delete_item(user_id, item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
# ... existing imports ...

# In Routers/UserRouter.py

@router.put("/{user_id}", response_model=dict)
def update_user(user_id: UUID, payload: UserUpdate):
    """
    Accepts partial updates (like just home_location).
    """
    try:
        # call the method you defined in UserService.py
        updated_user = user_service.update_user_details(user_id, payload)
        return updated_user.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))