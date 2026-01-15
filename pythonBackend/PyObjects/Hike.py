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
    # --- New Fields ---
    latitude: float = 0.0
    longitude: float = 0.0
    # ------------------
    required_gear_tags: List[str] = field(default_factory=list)
    permits_required: bool = False
    nearest_airport_code: Optional[str] = None
    parking_coordinates: Optional[Dict[str, float]] = None
    last_synced_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        
        # Ensure numbers are floats (handles string numbers from DB)
        self.length_km = float(self.length_km)
        self.elevation_gain_m = float(self.elevation_gain_m)

        # --- AUTO-CALCULATE LAT/LONG IF MISSING ---
        # If lat/long are 0, try to extract start point from geometry (GeoJSON)
        if (self.latitude == 0.0 or self.longitude == 0.0) and self.geometry:
            try:
                # GeoJSON format: {"type": "LineString", "coordinates": [[lon, lat], [lon, lat]]}
                coords = self.geometry.get("coordinates")
                if coords and isinstance(coords, list) and len(coords) > 0:
                    # Get the first point (Start of hike)
                    # Handle both Point ([lon, lat]) and LineString ([[lon, lat], ...])
                    first_point = coords[0] if isinstance(coords[0], list) else coords
                    
                    # GeoJSON is [Longitude, Latitude]
                    self.longitude = float(first_point[0])
                    self.latitude = float(first_point[1])
            except (IndexError, TypeError, ValueError):
                # Keep as 0.0 if extraction fails
                pass

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.id)
        d["difficulty"] = self.difficulty.name
        d["last_synced_at"] = self.last_synced_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hike":
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
        for field_name in ["geometry", "required_gear_tags", "parking_coordinates"]:
            val = data_copy.get(field_name)
            if isinstance(val, str):
                try:
                    data_copy[field_name] = json.loads(val)
                except json.JSONDecodeError:
                    data_copy[field_name] = {} if field_name == "geometry" else []

        # 4. Handle Datetime
        if isinstance(data_copy.get("last_synced_at"), str):
            data_copy["last_synced_at"] = datetime.fromisoformat(data_copy["last_synced_at"])

        # 5. Handle Lat/Long strings (if DB returns them as strings)
        if "latitude" in data_copy:
            data_copy["latitude"] = float(data_copy["latitude"])
        if "longitude" in data_copy:
            data_copy["longitude"] = float(data_copy["longitude"])

        return cls(**data_copy)