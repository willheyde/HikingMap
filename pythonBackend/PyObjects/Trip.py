
from ast import Dict
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any, List
from uuid import UUID

from attr import dataclass
from attrs import asdict


class TravelMode(Enum):
    DRIVE = "drive"
    FLY = "fly"
    MIXED = "mixed"


@dataclass
class Trip:
    id: UUID
    user_id: UUID
    hike_id: UUID
    start_date: datetime
    end_date: datetime
    origin_point: Dict[str, float]  # {"lat": float, "lng": float}
    travel_mode: TravelMode
    travel_estimate: Dict[str, Any] = field(default_factory=dict)  # {"drive_hours": float, "flight_price_est": float, ...}
    missing_gear: List[str] = field(default_factory=list)
    shopping_estimate: Dict[str, Any] = field(default_factory=dict)  # detailed breakdown
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.id)
        d["user_id"] = str(self.user_id)
        d["hike_id"] = str(self.hike_id)
        d["start_date"] = self.start_date.isoformat()
        d["end_date"] = self.end_date.isoformat()
        d["travel_mode"] = self.travel_mode.value
        d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trip":
        data_copy = data.copy()
        if isinstance(data_copy.get("id"), str):
            data_copy["id"] = UUID(data_copy["id"])
        if isinstance(data_copy.get("user_id"), str):
            data_copy["user_id"] = UUID(data_copy["user_id"])
        if isinstance(data_copy.get("hike_id"), str):
            data_copy["hike_id"] = UUID(data_copy["hike_id"])
        if isinstance(data_copy.get("start_date"), str):
            data_copy["start_date"] = datetime.fromisoformat(data_copy["start_date"])
        if isinstance(data_copy.get("end_date"), str):
            data_copy["end_date"] = datetime.fromisoformat(data_copy["end_date"])
        if isinstance(data_copy.get("travel_mode"), str):
            data_copy["travel_mode"] = TravelMode(data_copy["travel_mode"])
        if isinstance(data_copy.get("created_at"), str):
            data_copy["created_at"] = datetime.fromisoformat(data_copy["created_at"])
        return cls(**data_copy)
