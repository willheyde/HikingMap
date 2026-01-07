from dataclasses import dataclass
from uuid import UUID, uuid4
from enum import Enum
from typing import Optional

class WeatherConditions(str, Enum):
    FREEZING = "FREEZING"
    COLD = "COLD"
    FINE = "FINE"
    WARM = "WARM"
    HOT = "HOT"

class GearImportance(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"

@dataclass
class Item:
    """Base item class"""
    id: UUID
    name: str
    weight: float
    cost: float
    item_type: str
    image_url: Optional[str] = None 
    
    def __post_init__(self):
        if self.weight < 0:
            raise ValueError("Weight must be non-negative")
        if self.cost < 0:
            raise ValueError("Cost must be non-negative")
    @classmethod
    def from_dict(cls, data: dict):
        # Only extract fields that belong to Item
        return cls(
            id=data["id"] if isinstance(data["id"], UUID) else UUID(data["id"]),
            name=data["name"],
            weight=float(data["weight"]),
            cost=float(data["cost"]),
            item_type=data.get("item_type"),
            image_url=data.get("image_url"),
            # Explicitly DO NOT pass user_id or any other fields
        )
    def to_dict(self) -> dict:
        """Convert Item object to dictionary for JSON serialization"""
        return {
            "id": str(self.id),  # Convert UUID to string for JSON
            "name": self.name,
            "weight": float(self.weight),  # Ensure it's float, not Decimal
            "cost": float(self.cost),  # Ensure it's float, not Decimal
            "item_type": self.item_type,
            "image_url": self.image_url
        }
@dataclass
class Backpack(Item):
    # FIX: Added ' = 0.0' to satisfy inheritance rules
    capacity_liters: float = 0.0 
    
    def __init__(self, id: UUID, name: str, weight: float, cost: float, capacity_liters: float):
        super().__init__(id, name, weight, cost, item_type="backpack")
        self.capacity_liters = capacity_liters
        if self.capacity_liters < 0:
            raise ValueError("Capacity must be non-negative")

@dataclass
class Clothing(Item):
    # FIX: Added default value. Using the first Enum option as a placeholder.
    weather_conditions: WeatherConditions = WeatherConditions.FINE
    
    def __init__(self, id: UUID, name: str, weight: float, cost: float, weather_conditions: WeatherConditions):
        super().__init__(id, name, weight, cost, item_type="clothing")
        self.weather_conditions = weather_conditions

@dataclass
class Shoes(Clothing):
    # FIX: Added ' = False'
    crampons: bool = False
    
    def __init__(self, id: UUID, name: str, weight: float, cost: float, 
                 weather_conditions: WeatherConditions, crampons: bool = False):
        super().__init__(id, name, weight, cost, weather_conditions)
        self.item_type = "shoes"
        self.crampons = crampons