from datetime import datetime
from typing import Any, Optional, Dict, List
from uuid import UUID
from PyObjects.Items import Item


class User:
    def __init__(
        self,
        id: UUID,
        email: str,
        hashed_password: str,
        name: str,
        avatar_url: Optional[str] = None,
        home_location: Optional[Dict[str, Any]] = None,
        timezone: Optional[str] = None,
        items: Optional[List] = None,
        created_at: Optional[datetime] = None,
        google_sub: Optional[str] = None,
        auth_provider: str = "password",
    ):
        if not email:
            raise ValueError("email must not be empty")
        # OAuth users (auth_provider="google") have no local password, so an
        # empty hashed_password is only an error for password accounts.
        if not hashed_password and auth_provider == "password":
            raise ValueError("hashed_password must not be empty")
        if not name:
            raise ValueError("name must not be empty")
        if items is not None and not isinstance(items, list):
            raise ValueError("items must be a list")

        self.id = id
        self.email = email
        self.hashed_password = hashed_password
        self.name = name
        self.avatar_url = avatar_url
        self.home_location = home_location
        self.timezone = timezone
        self.items = items or []
        self.created_at = created_at or datetime.now()
        self.google_sub = google_sub
        self.auth_provider = auth_provider

    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "hashed_password": self.hashed_password,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "home_location": self.home_location,
            "timezone": self.timezone,
            "items": [i.to_dict() for i in self.items] if self.items else [],
            "created_at": self.created_at.isoformat(),
            "google_sub": self.google_sub,
            "auth_provider": self.auth_provider,
        }

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