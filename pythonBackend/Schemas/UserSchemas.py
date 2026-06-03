# File: Schemas/UserSchemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# Ensure your UserUpdate looks like this
class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    # CRITICAL: This must be Dict or Any to accept the JSON object from React
    home_location: Optional[Dict[str, Any]] = None 
    timezone: Optional[str] = None

class ItemLink(BaseModel):
    item_id: str
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str