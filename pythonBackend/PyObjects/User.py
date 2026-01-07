from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Dict, List
from uuid import UUID

from attrs import asdict
from PyObjects.Items import Item


class User:
    def __init__(
        self,
        id: UUID,
        email: str,
        hashed_password: str,
        name: str,
        avatar_url: Optional[str] = None,
        home_location: Optional[Dict[str, Any]] = None,  # Changed to Any
        timezone: Optional[str] = None,
        items: Optional[List] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.email = email
        self.hashed_password = hashed_password
        self.name = name
        self.avatar_url = avatar_url
        self.home_location = home_location
        self.timezone = timezone
        self.items = items or []
        self.created_at = created_at or datetime.now()
    
    # PyObjects/User.py

    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "hashed_password": self.hashed_password,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "home_location": self.home_location,
            "timezone": self.timezone,
            # FIX: Convert Item objects to dicts, otherwise JSON serialization fails
            "items": [i.to_dict() for i in self.items] if self.items else [],
            "created_at": self.created_at.isoformat()
        }
    def __post_init__(self) -> None:
        if not self.email:
            raise ValueError("email must not be empty")
        if not self.hashed_password:
            raise ValueError("hashed_password must not be empty")
        if not self.name:
            raise ValueError("name must not be empty")
        if self.items is None:
            self.items = []
        if not isinstance(self.items, list):
            raise ValueError("items must be a list")


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        data_copy = data.copy()

        if isinstance(data_copy.get("id"), str):
            data_copy["id"] = UUID(data_copy["id"])

        if isinstance(data_copy.get("created_at"), str):
            data_copy["created_at"] = datetime.fromisoformat(data_copy["created_at"])

        if "items" in data_copy and data_copy["items"] is not None:
            data_copy["items"] = [Item.from_dict(i) for i in data_copy["items"]]
        else:
            data_copy["items"] = []

        return cls(**data_copy)
