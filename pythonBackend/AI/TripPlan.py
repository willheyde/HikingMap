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
    suggestion: Optional[str] = None        # e.g. "Western Mountaineering Alpinlite"

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
    hike_name:         Optional[str]  = None
    hike_id:           Optional[str]  = None
    destination_full:  Optional[str]  = None
    lat:               Optional[float] = None
    lng:               Optional[float] = None
    state:             Optional[str]  = None
    max_length_km:     Optional[float] = None   # ← NEW
    target_length_km:  Optional[float] = None   # ← NEW
    activity_type:     Optional[str]  = None
    duration_days:     Optional[int]  = None
    difficulty:        Optional[str]  = None
    # Search criteria from the last full destination search — persisted here
    # (not just left in session.phase_data, which is wiped on every phase
    # transition) so TripService can capture them in trail_data at save time
    # for Phase 3's "Go Again" replay.
    required_tags:     list[str]      = field(default_factory=list)
    preferred_tags:    list[str]      = field(default_factory=list)
    priority_tags:     list[str]      = field(default_factory=list)
    gear_selected:     list[str]      = field(default_factory=list)
    gear_gaps:         list[GearGap]  = field(default_factory=list)
    gear_finalized:    bool           = False
    days:              list[DayPlan]  = field(default_factory=list)
    itinerary_approved: bool          = False
    notes:             str            = ""   # any free-form notes accumulated

    # ── Helpers ───────────────────────────────────────────────────────────────

    def is_destination_set(self) -> bool:
        return bool(
            self.destination_full
            and self.lat is not None
            and self.lng is not None
            and self.duration_days
            and self.hike_id          # ← added
        )

    def to_dict(self) -> dict:
        return {
            "hike_name":          self.hike_name,
            "hike_id":            self.hike_id,
            "destination_full":   self.destination_full,
            "lat":                self.lat,
            "lng":                self.lng,
            "state":              self.state,             # ← NEW
            "max_length_km":      self.max_length_km,      # ← NEW
            "target_length_km":   self.target_length_km,
            "activity_type":      self.activity_type,
            "duration_days":      self.duration_days,
            "difficulty":         self.difficulty,
            "required_tags":      self.required_tags,
            "preferred_tags":     self.preferred_tags,
            "priority_tags":      self.priority_tags,
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
            state              = d.get("state"),          # ← NEW
            max_length_km      = d.get("max_length_km"),       # ← NEW
            target_length_km   = d.get("target_length_km"),
            activity_type      = d.get("activity_type"),
            duration_days      = d.get("duration_days"),
            difficulty         = d.get("difficulty"),
            required_tags      = d.get("required_tags", []),
            preferred_tags     = d.get("preferred_tags", []),
            priority_tags      = d.get("priority_tags", []),
            gear_selected      = d.get("gear_selected", []),
            gear_finalized     = d.get("gear_finalized", False),
            itinerary_approved = d.get("itinerary_approved", False),
            notes              = d.get("notes", ""),
        )
        plan.gear_gaps = [GearGap.from_dict(g) for g in d.get("gear_gaps", [])]
        plan.days      = [DayPlan.from_dict(day) for day in d.get("days", [])]
        return plan