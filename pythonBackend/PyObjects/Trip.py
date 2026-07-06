from dataclasses import dataclass, field
import dataclasses
from datetime import date, datetime
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
    status: str = "draft"   # draft | saved | completed | reviewed
    stops: List[TripStop] = field(default_factory=list)
    gear:  List[TripGearItem] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Phase 2 lifecycle fields. planned_date stays null in practice today —
    # nothing in the AI flow extracts a calendar date, only duration — kept
    # for when/if that's added. needs_review is flipped by the background
    # job anchored off completed_at (see TripRepository.flip_needs_review).
    planned_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    needs_review: bool = False

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":            str(self.id),
            "user_id":       str(self.user_id),
            "title":         self.title,
            "goal":          self.goal,
            "status":        self.status,
            "stops":         [s.to_dict() for s in self.stops],
            "gear":          [g.to_dict() for g in self.gear],
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "updated_at":    self.updated_at.isoformat() if self.updated_at else None,
            "planned_date":  self.planned_date.isoformat() if self.planned_date else None,
            "completed_at":  self.completed_at.isoformat() if self.completed_at else None,
            "needs_review":  self.needs_review,
        }


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trip":
        d = data.copy()

        # Coerce types the DB returns as raw strings or primitives
        if isinstance(d.get("id"),       str): d["id"]      = UUID(d["id"])
        if isinstance(d.get("user_id"),  str): d["user_id"] = UUID(d["user_id"])
        if isinstance(d.get("created_at"), str):
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        if isinstance(d.get("updated_at"), str):
            d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        if isinstance(d.get("planned_date"), str):
            d["planned_date"] = date.fromisoformat(d["planned_date"])
        if isinstance(d.get("completed_at"), str):
            d["completed_at"] = datetime.fromisoformat(d["completed_at"])

        # Drop anything the dataclass doesn't declare — covers old DB columns,
        # hydrated relations (stops/gear), and any future schema noise.
        valid = {f.name for f in dataclasses.fields(cls)}
        d = {k: v for k, v in d.items() if k in valid}

        return cls(**d)


@dataclass
class HikeCompletion:
    trip_id:         UUID
    went:             bool
    difficulty_felt:  Optional[str] = None   # EASY|MODERATE|DIFFICULT|EXPERT — matches hikes.difficulty convention
    elevation_felt:   Optional[str] = None
    rating:           Optional[int] = None   # 1-5
    notes:            Optional[str] = None
    reviewed_at:      Optional[datetime] = None

    def __post_init__(self):
        if self.reviewed_at is None:
            self.reviewed_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id":         str(self.trip_id),
            "went":            self.went,
            "difficulty_felt": self.difficulty_felt,
            "elevation_felt":  self.elevation_felt,
            "rating":          self.rating,
            "notes":           self.notes,
            "reviewed_at":     self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HikeCompletion":
        d = data.copy()
        if isinstance(d.get("trip_id"), str): d["trip_id"] = UUID(d["trip_id"])
        if isinstance(d.get("reviewed_at"), str):
            d["reviewed_at"] = datetime.fromisoformat(d["reviewed_at"])
        valid = {f.name for f in dataclasses.fields(cls)}
        d = {k: v for k, v in d.items() if k in valid}
        return cls(**d)