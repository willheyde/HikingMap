import json  # <--- Make sure this is imported!
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict, List
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
        # Maps "MODERATE" (string from DB) to DifficultyLevel.MODERATE
        if isinstance(data_copy.get("difficulty"), str):
            try:
                data_copy["difficulty"] = DifficultyLevel[data_copy["difficulty"]]
            except KeyError:
                # Fallback if DB has invalid string
                data_copy["difficulty"] = DifficultyLevel.MODERATE

        # 3. Handle JSON Fields (The specific fix for your 126 errors)
        # If geometry comes back as a string '{"type":...}', we parse it to a dict
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

        return cls(**data_copy)