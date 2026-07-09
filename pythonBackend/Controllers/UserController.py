import logging
import os
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from Services.UserService import UserService
from Services.ItemService import ItemService
from Repos.UserRepo import UserRepository
from Repos.ItemRepo import ItemRepository
from PyObjects.User import User
from PyObjects.Items import Item
from Auth.authentication import hash_password, verify_password, create_access_token, get_current_user_id
from Schemas.UserSchemas import TokenResponse
from gear_levels import GEAR_CATEGORIES, is_valid_level, valid_levels
from rate_limit import auth_rate_limit

# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    # The ID token (a JWT) the Google Identity Services button hands the
    # frontend. We verify it server-side; the client is never trusted to
    # assert its own identity.
    credential: str

class UserCreate(BaseModel):
    email: EmailStr
    # bcrypt only hashes the first 72 bytes, so capping there avoids a silently
    # ignored tail; 8 is a low-friction floor for a hobby app.
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=100)
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    items: Optional[List[dict]] = []

class UserUpdate(BaseModel):
    # NOTE: no password field here on purpose — a client must never be able to
    # set a raw/precomputed hash. Password changes go through a dedicated,
    # authenticated flow (not this generic profile update).
    email: Optional[EmailStr] = None
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Users"])

user_repo = UserRepository()
user_service = UserService(user_repo)
item_service = ItemService(ItemRepository())

# OAuth client ID from the Google Cloud Console. Also the audience the ID token
# must be issued for — verify_oauth2_token rejects tokens minted for any other
# app, so this env var must be set (and match the frontend button's client_id)
# for Google login to work.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# ---------------------------------------------------------
# Auth
# ---------------------------------------------------------

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
def login(credentials: LoginRequest):
    user = user_service.get_user_by_email(credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user_id=str(user.id), name=user.name)

@router.post("/auth/google", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
def google_auth(payload: GoogleAuthRequest):
    """
    "Sign in with Google". The frontend obtains a Google ID token and posts it
    here; we verify it and return one of our own JWTs — identical to /login from
    the rest of the app's perspective.

    Resolution order for the verified Google identity:
      1. Known google_sub          -> returning Google user, log in.
      2. Verified email matches an existing account -> link Google to it.
      3. Otherwise                 -> create a new account (is_new=True).
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google login is not configured.")

    # verify_oauth2_token checks the signature (against Google's public keys),
    # expiry, issuer, and that the audience == our GOOGLE_CLIENT_ID. Any failure
    # raises ValueError -> treat as an invalid credential.
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google credential.")

    google_sub     = idinfo["sub"]
    email          = idinfo.get("email")
    email_verified = idinfo.get("email_verified", False)
    name           = idinfo.get("name") or (email.split("@")[0] if email else "Hiker")
    picture        = idinfo.get("picture")

    is_new = False

    # 1. Returning Google user.
    user = user_service.get_user_by_google_sub(google_sub)

    if not user:
        # 2. Link to an existing account with the same *verified* email. We only
        #    trust email for linking when Google says it's verified — otherwise a
        #    Google account with an unverified, attacker-chosen email could be
        #    used to take over someone else's account.
        if email and email_verified:
            existing = user_service.get_user_by_email(email)
            if existing:
                user_service.link_google_account(existing.id, google_sub)
                user = existing

        # 3. New account.
        if not user:
            if not (email and email_verified):
                raise HTTPException(status_code=401, detail="Google account email is not verified.")
            try:
                user = user_service.create_google_user(
                    email=email, name=name, google_sub=google_sub, avatar_url=picture,
                )
                is_new = True
            except psycopg.errors.UniqueViolation:
                # Rare race: the row appeared between our checks. Re-fetch and
                # continue as a normal login rather than 500.
                user = user_service.get_user_by_google_sub(google_sub) \
                       or user_service.get_user_by_email(email)
                if not user:
                    raise HTTPException(status_code=409, detail="Account conflict, please try again.")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user_id=str(user.id), name=user.name, is_new=is_new)

# ---------------------------------------------------------
# User CRUD
# ---------------------------------------------------------

# FIX 2: Removed the duplicate @router.post("/") decorator.
@router.post("/", response_model=dict, dependencies=[Depends(auth_rate_limit)])
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
    except Exception:
        # Don't leak raw exception text (DB errors, constraint names) to the
        # client — log it server-side and return a generic message.
        logger.exception("create_user failed")
        raise HTTPException(status_code=400, detail="Could not create the account.")

@router.get("/{user_id}", response_model=dict)
def get_user(user_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    # Self-only: a personal planner has no reason to expose one user's email /
    # home_location to another. This also blocks unauthenticated profile enum.
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = user.to_dict()
    data.pop("hashed_password", None)
    data.pop("google_sub", None)
    return data

# NOTE: the old GET /users/ (list every user) was removed — it required no auth
# and serialized hashed_password + google_sub for every account, a full
# credential-hash dump. There is no legitimate client use for it.

@router.put("/{user_id}", response_model=dict)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user_id: str = Depends(get_current_user_id),
):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    existing = user_service.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = User(
        id=user_id,
        email=payload.email or existing.email,
        hashed_password=existing.hashed_password,
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
    except Exception:
        logger.exception("update_user failed for user_id=%s", user_id)
        raise HTTPException(status_code=400, detail="Could not update the account.")

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
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
    except Exception:
        logger.exception("add_user_gear failed for user_id=%s", user_id)
        raise HTTPException(status_code=400, detail="Could not add the gear item.")

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