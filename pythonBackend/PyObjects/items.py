from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID
import math

class WeatherConditions(Enum):
    FREEZING = auto()  # under 25°F
    COLD = auto()      # 25 - 40°F
    FINE = auto()      # 40 - 55°F
    WARM = auto()      # 55 - 70°F
    HOT = auto()       # above 70°F

def temp_to_condition(temp_f: float) -> WeatherConditions:
    """Map a Fahrenheit temperature to a WeatherConditions value."""
    if temp_f < 25:
        return WeatherConditions.FREEZING
    if temp_f < 40:
        return WeatherConditions.COLD
    if temp_f < 55:
        return WeatherConditions.FINE
    if temp_f < 70:
        return WeatherConditions.WARM
    return WeatherConditions.HOT

@dataclass
class Item:
    name: str
    weight: float  # grams or lbs — be consistent in your app
    cost: float    # USD (or currency you choose)

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError("weight must be non-negative")
        if self.cost < 0:
            raise ValueError("cost must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        return cls(**data)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, weight={self.weight}, cost={self.cost})"

@dataclass
class Backpack(Item):
    capacity_liters: float = field(default=0.0)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.capacity_liters < 0:
            raise ValueError("capacity_liters must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Backpack":
        return cls(**data)

@dataclass
class Clothing(Item):
    weatherconditions: WeatherConditions = WeatherConditions.FINE

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["weatherconditions"] = self.weatherconditions.name
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clothing":
        wc = data.get("weatherconditions")
        if isinstance(wc, str):
            data["weatherconditions"] = WeatherConditions[wc]
        return cls(**data)

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(name={self.name!r}, weight={self.weight}, cost={self.cost}, "
                f"weatherconditions={self.weatherconditions.name})")

@dataclass
class Shoes(Clothing):
    crampons: bool = False  # whether the shoes require/are compatible with crampons

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["weatherconditions"] = self.weatherconditions.name
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Shoes":
        wc = data.get("weatherconditions")
        if isinstance(wc, str):
            data["weatherconditions"] = WeatherConditions[wc]
        return cls(**data)

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(name={self.name!r}, weight={self.weight}, cost={self.cost}, "
                f"weatherconditions={self.weatherconditions.name}, crampons={self.crampons})")

# ==================== HikeGearRequirement ====================
class GearImportance(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


@dataclass
class HikeGearRequirement:
    id: UUID
    hike_id: UUID
    gear_tag: str
    importance: GearImportance

    def __post_init__(self) -> None:
        if not self.gear_tag:
            raise ValueError("gear_tag must not be empty")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.id)
        d["hike_id"] = str(self.hike_id)
        d["importance"] = self.importance.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HikeGearRequirement":
        data_copy = data.copy()
        if isinstance(data_copy.get("id"), str):
            data_copy["id"] = UUID(data_copy["id"])
        if isinstance(data_copy.get("hike_id"), str):
            data_copy["hike_id"] = UUID(data_copy["hike_id"])
        if isinstance(data_copy.get("importance"), str):
            data_copy["importance"] = GearImportance(data_copy["importance"])
        return cls(**data_copy)


