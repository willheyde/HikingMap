from ast import Dict
from dataclasses import dataclass, field
import datetime
from typing import Any, Optional
from uuid import UUID

from attrs import asdict


@dataclass
class User:
    id: UUID
    email: str
    hashed_password: str
    name: str
    avatar_url: Optional[str] = None
    home_location: Optional[Dict[str, float]] = None  # {"lat": float, "lng": float}
    timezone: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.email:
            raise ValueError("email must not be empty")
        if not self.hashed_password:
            raise ValueError("hashed_password must not be empty")
        if not self.name:
            raise ValueError("name must not be empty")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.id)
        d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        data_copy = data.copy()
        if isinstance(data_copy.get("id"), str):
            data_copy["id"] = UUID(data_copy["id"])
        if isinstance(data_copy.get("created_at"), str):
            data_copy["created_at"] = datetime.fromisoformat(data_copy["created_at"])
        return cls(**data_copy)