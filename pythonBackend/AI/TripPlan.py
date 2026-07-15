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
    # A+ metadata for the inline gear-entry "blip" form. gear_category is the
    # functional gear_levels category the create_user_gear write path speaks
    # (e.g. "shell"); min_level is the minimum acceptable capability level for
    # this trail (ordinal cats), which the form preselects and won't let the user
    # go below; min_temp_f is the overnight-low target (sleep only); importance
    # is "required" | "recommended". All optional — the legacy analyzer and
    # older serialized sessions leave them None.
    gear_category: Optional[str] = None
    min_level: Optional[str] = None
    min_temp_f: Optional[int] = None
    importance: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "category":      self.category,
            "issue":         self.issue,
            "detail":        self.detail,
            "suggestion":    self.suggestion,
            "gear_category": self.gear_category,
            "min_level":     self.min_level,
            "min_temp_f":    self.min_temp_f,
            "importance":    self.importance,
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
    min_length_km:     Optional[float] = None   # ← NEW: length FLOOR ("at least N mi")
    max_length_km:     Optional[float] = None   # ← NEW
    target_length_km:  Optional[float] = None   # ← NEW
    activity_type:     Optional[str]  = None
    duration_days:     Optional[int]  = None
    difficulty:        Optional[str]  = None
    # Authoritative stats for the selected trail, captured from the DB at hike
    # selection (not the user's search filters or the LLM's guesses). Populated
    # by trip_chat._capture_selected_hike_facts once plan.hike_id is set, and
    # surfaced in the finalize summary + saved trail_data. estimated_duration is
    # a human on-trail-time label (Naismith) — e.g. "~45 min" — distinct from
    # duration_days (the trip's calendar span, used to structure the itinerary).
    hike_length_km:        Optional[float] = None
    hike_elevation_gain_m: Optional[float] = None
    estimated_duration:    Optional[str]   = None
    # Prep-level band (rigor.RIGOR_TIERS) for the selected trail at this trip's
    # duration — casual/standard/serious/expedition. Computed once at selection
    # with the full hike (incl. altitude + tags); drives gear surfacing + prompt
    # tone downstream so they never recompute it from partial plan fields.
    rigor_tier:            Optional[str]   = None
    # Known campsites/shelters near the selected trail, copied from hike.campsites
    # at selection. Fed to the itinerary prompt so day plans name real camps.
    # Each: {name, lat, lng, type, dist_off_trail_m}. See PyObjects/Hike.py.
    campsites:             list[dict]      = field(default_factory=list)
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
            "min_length_km":      self.min_length_km,      # ← NEW
            "max_length_km":      self.max_length_km,      # ← NEW
            "target_length_km":   self.target_length_km,
            "activity_type":      self.activity_type,
            "duration_days":      self.duration_days,
            "difficulty":         self.difficulty,
            "hike_length_km":        self.hike_length_km,
            "hike_elevation_gain_m": self.hike_elevation_gain_m,
            "estimated_duration":    self.estimated_duration,
            "rigor_tier":            self.rigor_tier,
            "campsites":             self.campsites,
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
            min_length_km      = d.get("min_length_km"),       # ← NEW
            max_length_km      = d.get("max_length_km"),       # ← NEW
            target_length_km   = d.get("target_length_km"),
            activity_type      = d.get("activity_type"),
            duration_days      = d.get("duration_days"),
            difficulty         = d.get("difficulty"),
            hike_length_km        = d.get("hike_length_km"),
            hike_elevation_gain_m = d.get("hike_elevation_gain_m"),
            estimated_duration    = d.get("estimated_duration"),
            rigor_tier            = d.get("rigor_tier"),
            campsites             = d.get("campsites", []),
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