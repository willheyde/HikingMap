from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class TripStop:
    id: UUID
    trip_id: UUID
    stop_order: int
    destination: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    duration_days: Optional[int] = None
    activity_type: Optional[str] = None
    itinerary: Optional[Dict[str, Any]] = None
    trail_data: Optional[Dict[str, Any]] = None
    camping: Optional[Dict[str, Any]] = None
    cost_estimate: Optional[Dict[str, Any]] = None
    travel_from_prev: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":               str(self.id),
            "trip_id":          str(self.trip_id),
            "stop_order":       self.stop_order,
            "destination":      self.destination,
            "lat":              self.lat,
            "lng":              self.lng,
            "duration_days":    self.duration_days,
            "activity_type":    self.activity_type,
            "itinerary":        self.itinerary,
            "trail_data":       self.trail_data,
            "camping":          self.camping,
            "cost_estimate":    self.cost_estimate,
            "travel_from_prev": self.travel_from_prev,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TripStop":
        d = data.copy()
        if isinstance(d.get("id"),       str): d["id"]       = UUID(d["id"])
        if isinstance(d.get("trip_id"),  str): d["trip_id"]  = UUID(d["trip_id"])
        if isinstance(d.get("created_at"), str):
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        return cls(**d)


@dataclass
class TripGearItem:
    trip_id: UUID
    item_id: UUID
    status: str = "owned"   # owned | need_to_buy | optional

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": str(self.trip_id),
            "item_id": str(self.item_id),
            "status":  self.status,
        }


@dataclass
class Trip:
    id: UUID
    user_id: UUID
    title: str
    goal: Optional[str] = None
    status: str = "draft"   # draft | saved | completed
    stops: List[TripStop] = field(default_factory=list)
    gear:  List[TripGearItem] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":         str(self.id),
            "user_id":    str(self.user_id),
            "title":      self.title,
            "goal":       self.goal,
            "status":     self.status,
            "stops":      [s.to_dict() for s in self.stops],
            "gear":       [g.to_dict() for g in self.gear],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trip":
        d = data.copy()
        if isinstance(d.get("id"),       str): d["id"]      = UUID(d["id"])
        if isinstance(d.get("user_id"),  str): d["user_id"] = UUID(d["user_id"])
        if isinstance(d.get("created_at"), str):
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        # stops and gear are hydrated by the repo — not from raw dict
        d.pop("stops", None)
        d.pop("gear",  None)
        return cls(**d)