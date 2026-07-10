import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict, List, Union
from uuid import UUID

class DifficultyLevel(Enum):
    EASY = 1
    MODERATE = 2
    DIFFICULT = 3
    EXPERT = 4

@dataclass
class Hike:
    id: UUID
    source_id: str
    name: str
    geometry: Dict[str, Any]
    difficulty: DifficultyLevel
    length_km: float
    elevation_gain_m: float
    min_altitude_m: float
    max_altitude_m: float
    region: str
    season_start_month: int
    season_end_month: int
    lat: float = 0.0
    lng: float = 0.0
    state: Optional[str] = None          # ← ADD THIS
    required_gear_tags: List[str] = field(default_factory=list)
    permits_required: bool = False
    nearest_airport_code: Optional[str] = None
    parking_coordinates: Optional[Dict[str, float]] = None
    last_synced_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    can_camp: bool = False
    # Catalog-independent required gear, keyed by category → {min_level |
    # min_temp_f, importance}. Derived from this hike's stats + tags by
    # GearInferenceEngine.infer_gear_levels(); consumed by GearGapAnalyzer for
    # adequacy checks. Empty until backfilled/ingested. See gear_levels.py.
    gear_requirements: Dict[str, Any] = field(default_factory=dict)
    # Inferred geometry shape: 'loop' | 'out_and_back' | None. None = not yet
    # classified (existing rows before migration 005 / the distance backfill).
    # Set at ingest and by ingestion/backfill_trail_distances.py; also the
    # idempotency gate that stops an out-and-back's length being doubled twice.
    trail_shape: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        
        # Ensure numbers are floats (handles string numbers from DB)
        self.length_km = float(self.length_km)
        self.elevation_gain_m = float(self.elevation_gain_m)

        # AUTO-CALCULATE LAT/LNG IF MISSING
        # If lat/lng are 0, try to extract start point from geometry (GeoJSON)
        if (self.lat == 0.0 or self.lng == 0.0) and self.geometry:
            try:
                # GeoJSON format: {"type": "LineString", "coordinates": [[lon, lat], [lon, lat]]}
                coords = self.geometry.get("coordinates")
                if coords and isinstance(coords, list) and len(coords) > 0:
                    # Get the first point (start of hike)
                    # Handle both Point ([lon, lat]) and LineString ([[lon, lat], ...])
                    first_point = coords[0] if isinstance(coords[0], list) else coords
                    
                    # GeoJSON is [longitude, latitude]
                    self.lng = float(first_point[0])
                    self.lat = float(first_point[1])
            except (IndexError, TypeError, ValueError):
                pass

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.id)
        d["difficulty"] = self.difficulty.name
        d["last_synced_at"] = self.last_synced_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hike":
        tags = data.get("required_gear_tags")
        if isinstance(tags, str):
            data["required_gear_tags"] = json.loads(tags)
        elif tags is None:
            data["required_gear_tags"] = []
        data_copy = data.copy()
        
        # 1. Handle ID
        if isinstance(data_copy.get("id"), str):
            data_copy["id"] = UUID(data_copy["id"])
            
        # 2. Handle Difficulty Enum
        if isinstance(data_copy.get("difficulty"), str):
            try:
                data_copy["difficulty"] = DifficultyLevel[data_copy["difficulty"]]
            except KeyError:
                data_copy["difficulty"] = DifficultyLevel.MODERATE

        # 3. Handle JSON Fields
        _dict_defaults = {"geometry", "gear_requirements"}
        for field_name in ["geometry", "required_gear_tags", "parking_coordinates", "gear_requirements"]:
            val = data_copy.get(field_name)
            if isinstance(val, str):
                try:
                    data_copy[field_name] = json.loads(val)
                except json.JSONDecodeError:
                    data_copy[field_name] = {} if field_name in _dict_defaults else []

        # 3b. Derive required_gear_tags from gear_requirements.
        # There is no required_gear_tags column; it used to be synthesized from
        # the legacy hike_items join. Now that per-trail needs live in the
        # catalog-independent gear_requirements jsonb, expose the *required*
        # categories from there so every read path (search, get_by_id) has it
        # without hike_items.
        gr = data_copy.get("gear_requirements")
        if isinstance(gr, dict) and not data_copy.get("required_gear_tags"):
            data_copy["required_gear_tags"] = [
                cat for cat, spec in gr.items()
                if isinstance(spec, dict) and spec.get("importance") == "required"
            ]

        # 4. Handle Datetime
        if isinstance(data_copy.get("last_synced_at"), str):
            data_copy["last_synced_at"] = datetime.fromisoformat(data_copy["last_synced_at"])

        # 5. Handle lat/lng strings (if DB returns them as strings)
        if "lat" in data_copy:
            data_copy["lat"] = float(data_copy["lat"])
        if "lng" in data_copy:
            data_copy["lng"] = float(data_copy["lng"])

        return cls(**data_copy)