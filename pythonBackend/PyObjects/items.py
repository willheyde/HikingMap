from dataclasses import dataclass
from uuid import UUID
from enum import Enum
from typing import Optional


# ---------------------------------------------------------
# Enums
# ---------------------------------------------------------

class ItemType(str, Enum):
    BACKPACK        = "backpack"
    FOOTWEAR        = "footwear"
    SHELTER         = "shelter"
    SLEEPING_BAG    = "sleeping_bag"
    SLEEPING_PAD    = "sleeping_pad"
    CLOTHING        = "clothing"
    WATER           = "water"
    KITCHEN         = "kitchen"
    NAVIGATION      = "navigation"
    LIGHTING        = "lighting"
    SAFETY          = "safety"
    TREKKING_POLES  = "trekking_poles"
    TECHNICAL       = "technical"
    MISC            = "misc"

class Season(str, Enum):
    SUMMER       = "summer"        # 32°F+ / 0°C+
    THREE_SEASON = "3_season"      # 15°F+ / -9°C+
    FOUR_SEASON  = "4_season"      # 0°F+ / -18°C+
    WINTER       = "winter"        # below 0°F / -18°C

class ActivityLevel(str, Enum):
    DAY_HIKE        = "day_hike"
    OVERNIGHT       = "overnight"
    BACKPACKING     = "backpacking"
    EXTENDED        = "extended"
    MOUNTAINEERING  = "mountaineering"

class LayerType(str, Enum):
    BASE  = "base"   # moisture wicking next to skin
    MID   = "mid"    # insulation (fleece, down)
    SHELL = "shell"  # wind/rain protection


# ---------------------------------------------------------
# Base Item
# ---------------------------------------------------------

@dataclass
class Item:
    id: UUID
    name: str
    weight: float       # grams
    cost: float         # USD
    item_type: str
    image_url: Optional[str] = None

    def __post_init__(self):
        if self.weight < 0:
            raise ValueError("Weight must be non-negative")
        if self.cost < 0:
            raise ValueError("Cost must be non-negative")

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(
            id=data["id"] if isinstance(data["id"], UUID) else UUID(str(data["id"])),
            name=data["name"],
            weight=float(data["weight"]),
            cost=float(data["cost"]),
            item_type=data.get("item_type", ItemType.MISC.value),
            image_url=data.get("image_url"),
        )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "weight": float(self.weight),
            "cost": float(self.cost),
            "item_type": self.item_type,
            "image_url": self.image_url,
        }


# ---------------------------------------------------------
# Subclasses — all use __post_init__ only, no manual __init__
# ---------------------------------------------------------

@dataclass
class Backpack(Item):
    capacity_liters: float = 0.0
    frame_type: str = "internal"    # internal | external | frameless

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.BACKPACK.value
        if self.capacity_liters < 0:
            raise ValueError("Capacity must be non-negative")


@dataclass
class Footwear(Item):
    """Replaces Shoes. No longer inherits Clothing."""
    waterproof: bool = False
    crampon_compatible: bool = False
    ankle_support: str = "low"      # low | mid | high

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.FOOTWEAR.value


@dataclass
class Shelter(Item):
    capacity_persons: int = 1
    season_rating: str = Season.THREE_SEASON.value
    shelter_type: str = "tent"      # tent | tarp | bivy | hammock

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.SHELTER.value


@dataclass
class SleepingBag(Item):
    temp_rating_f: int = 32         # lower limit comfort rating
    fill_type: str = "synthetic"    # down | synthetic

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.SLEEPING_BAG.value


@dataclass
class SleepingPad(Item):
    r_value: float = 2.0            # insulation; 2=summer, 4=3-season, 5+=winter
    pad_type: str = "foam"          # foam | inflatable | self-inflating

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.SLEEPING_PAD.value


@dataclass
class Clothing(Item):
    layer_type: str = LayerType.MID.value
    waterproof: bool = False
    min_temp_f: int = 32            # lowest comfortable temp

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.CLOTHING.value


@dataclass
class WaterSystem(Item):
    system_type: str = "filter"     # filter | purifier | uv | tablets | bottle
    flow_rate_lpm: float = 1.0      # liters per minute (0 for tablets/uv)

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.WATER.value


@dataclass
class Kitchen(Item):
    stove_type: Optional[str] = None    # canister | alcohol | wood | solid_fuel | none
    cookware_included: bool = False
    boil_time_min: float = 0.0          # minutes to boil 1L

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.KITCHEN.value


@dataclass
class NavigationTool(Item):
    nav_type: str = "map"           # map | compass | gps | satellite_communicator

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.NAVIGATION.value


@dataclass
class Lighting(Item):
    lumens: int = 0
    lighting_type: str = "headlamp" # headlamp | lantern | flashlight

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.LIGHTING.value


@dataclass
class SafetyGear(Item):
    safety_type: str = "first_aid"  # first_aid | beacon | probe | shovel | whistle | emergency_blanket | fire
    avalanche_rated: bool = False

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.SAFETY.value


@dataclass
class TechnicalGear(Item):
    """Mountaineering-specific. Not shown in onboarding unless user selects mountaineering."""
    technical_type: str = "ice_axe" # ice_axe | crampons | harness | helmet | rope | carabiner | prusik

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.TECHNICAL.value


@dataclass
class TrekkingPoles(Item):
    adjustable: bool = True
    material: str = "aluminum"      # aluminum | carbon

    def __post_init__(self):
        super().__post_init__()
        self.item_type = ItemType.TREKKING_POLES.value