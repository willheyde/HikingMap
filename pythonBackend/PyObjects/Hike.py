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
    geometry: Dict[str, Any]  # GeoJSON: {"type": "Point/MultiPoint/LineString", "coordinates": [...]}
    difficulty: DifficultyLevel
    length_km: float
    elevation_gain_m: float
    min_altitude_m: float
    max_altitude_m: float
    region: str
    season_start_month: int  # 1-12
    season_end_month: int    # 1-12
    required_gear_tags: List[str] = field(default_factory=list)  # ["microspikes", "iceaxe", ...]
    permits_required: bool = False
    nearest_airport_code: Optional[str] = None
    parking_coordinates: Optional[Dict[str, float]] = None  # {"lat": float, "lng": float}
    last_synced_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if self.length_km < 0:
            raise ValueError("length_km must be non-negative")
        if self.elevation_gain_m < 0:
            raise ValueError("elevation_gain_m must be non-negative")
        if not (1 <= self.season_start_month <= 12):
            raise ValueError("season_start_month must be between 1 and 12")
        if not (1 <= self.season_end_month <= 12):
            raise ValueError("season_end_month must be between 1 and 12")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.id)
        d["difficulty"] = self.difficulty.name
        d["last_synced_at"] = self.last_synced_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hike":
        data_copy = data.copy()
        if isinstance(data_copy.get("id"), str):
            data_copy["id"] = UUID(data_copy["id"])
        if isinstance(data_copy.get("difficulty"), str):
            data_copy["difficulty"] = DifficultyLevel[data_copy["difficulty"]]
        if isinstance(data_copy.get("last_synced_at"), str):
            data_copy["last_synced_at"] = datetime.fromisoformat(data_copy["last_synced_at"])
        return cls(**data_copy)