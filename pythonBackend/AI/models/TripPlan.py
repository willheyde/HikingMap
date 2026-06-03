from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DayPlan:
    day_number: int
    title: str                        # e.g. "Trailhead to Mirror Lake"
    distance_miles: Optional[float]
    elevation_gain_ft: Optional[int]
    campsite: Optional[str]
    notes: str
    waypoints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "day_number":       self.day_number,
            "title":            self.title,
            "distance_miles":   self.distance_miles,
            "elevation_gain_ft":self.elevation_gain_ft,
            "campsite":         self.campsite,
            "notes":            self.notes,
            "waypoints":        self.waypoints,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DayPlan":
        return cls(**d)


@dataclass
class GearGap:
    category: str                     # e.g. "sleeping_bag"
    issue: str                        # e.g. "missing" | "marginal"
    detail: str                       # e.g. "Rated 20°F but overnight lows hit 12°F"
    suggestion: Optional[str]         # e.g. "Western Mountaineering Alpinlite"

    def to_dict(self) -> dict:
        return {
            "category":   self.category,
            "issue":      self.issue,
            "detail":     self.detail,
            "suggestion": self.suggestion,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GearGap":
        return cls(**d)


@dataclass
class TripPlan:
    # Core trip info (filled during destination phase)
    hike_name: Optional[str]          = None
    hike_id: Optional[str]            = None    # your DB hike ID if matched
    destination_full: Optional[str]   = None
    lat: Optional[float]              = None
    lng: Optional[float]              = None
    activity_type: Optional[str]      = None    # day_hike | overnight | backpacking | ...
    duration_days: Optional[int]      = None
    difficulty: Optional[str]         = None    # easy | moderate | hard

    # Gear (filled during gear_review phase)
    gear_selected: list[str]          = field(default_factory=list)   # item IDs user confirmed
    gear_gaps: list[GearGap]          = field(default_factory=list)
    gear_finalized: bool              = False

    # Itinerary (filled during itinerary phase)
    days: list[DayPlan]               = field(default_factory=list)
    itinerary_approved: bool          = False

    # Meta
    notes: str                        = ""      # any free-form notes accumulated

    # ── Helpers ───────────────────────────────────────────────────────────────

    def is_destination_set(self) -> bool:
        return all([self.destination_full, self.lat, self.lng, self.duration_days])

    def to_dict(self) -> dict:
        return {
            "hike_name":          self.hike_name,
            "hike_id":            self.hike_id,
            "destination_full":   self.destination_full,
            "lat":                self.lat,
            "lng":                self.lng,
            "activity_type":      self.activity_type,
            "duration_days":      self.duration_days,
            "difficulty":         self.difficulty,
            "gear_selected":      self.gear_selected,
            "gear_gaps":          [g.to_dict() for g in self.gear_gaps],
            "gear_finalized":     self.gear_finalized,
            "days":               [d.to_dict() for d in self.days],
            "itinerary_approved": self.itinerary_approved,
            "notes":              self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TripPlan":
        plan = cls(
            hike_name          = d.get("hike_name"),
            hike_id            = d.get("hike_id"),
            destination_full   = d.get("destination_full"),
            lat                = d.get("lat"),
            lng                = d.get("lng"),
            activity_type      = d.get("activity_type"),
            duration_days      = d.get("duration_days"),
            difficulty         = d.get("difficulty"),
            gear_selected      = d.get("gear_selected", []),
            gear_finalized     = d.get("gear_finalized", False),
            itinerary_approved = d.get("itinerary_approved", False),
            notes              = d.get("notes", ""),
        )
        plan.gear_gaps = [GearGap.from_dict(g) for g in d.get("gear_gaps", [])]
        plan.days      = [DayPlan.from_dict(day) for day in d.get("days", [])]
        return plan