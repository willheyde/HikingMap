from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from uuid import UUID, uuid4

from PyObjects.Items import (
    Item, Backpack, Footwear, Shelter, SleepingBag, SleepingPad,
    Clothing, WaterSystem, Kitchen, NavigationTool, Lighting,
    SafetyGear, TechnicalGear, TrekkingPoles, ItemType
)
from Repos.ItemRepo import ItemRepository
from Services.ItemService import ItemService

router = APIRouter(tags=["Items"])
repo   = ItemRepository()
service = ItemService(repo)


# =============================================================================
# Response schema (flat, all optional type-specific fields)
# =============================================================================

class ItemResponseSchema(BaseModel):
    id:                 UUID
    name:               str
    weight:             float
    cost:               float
    item_type:          str
    image_url:          Optional[str]   = None
    # Backpack
    capacity_liters:    Optional[float] = None
    frame_type:         Optional[str]   = None
    # Footwear
    waterproof:         Optional[bool]  = None
    crampon_compatible: Optional[bool]  = None
    ankle_support:      Optional[str]   = None
    # Shelter
    capacity_persons:   Optional[int]   = None
    season_rating:      Optional[str]   = None
    shelter_type:       Optional[str]   = None
    # Sleeping bag
    temp_rating_f:      Optional[int]   = None
    fill_type:          Optional[str]   = None
    # Sleeping pad
    r_value:            Optional[float] = None
    pad_type:           Optional[str]   = None
    # Clothing
    layer_type:         Optional[str]   = None
    min_temp_f:         Optional[int]   = None
    # Water
    system_type:        Optional[str]   = None
    flow_rate_lpm:      Optional[float] = None
    # Kitchen
    stove_type:         Optional[str]   = None
    cookware_included:  Optional[bool]  = None
    boil_time_min:      Optional[float] = None
    # Navigation
    nav_type:           Optional[str]   = None
    # Lighting
    lumens:             Optional[int]   = None
    lighting_type:      Optional[str]   = None
    # Safety
    safety_type:        Optional[str]   = None
    avalanche_rated:    Optional[bool]  = None
    # Technical
    technical_type:     Optional[str]   = None
    # Trekking poles
    adjustable:         Optional[bool]  = None
    material:           Optional[str]   = None


class ImageUpdateSchema(BaseModel):
    image_url: str


# =============================================================================
# Create schemas — one per type
# =============================================================================

class BackpackCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    capacity_liters: float = Field(ge=0)
    frame_type: str = "internal"

class FootwearCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    waterproof: bool = False
    crampon_compatible: bool = False
    ankle_support: str = "low"

class ShelterCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    capacity_persons: int = 1
    season_rating: str = "3_season"
    shelter_type: str = "tent"

class SleepingBagCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    temp_rating_f: int = 32
    fill_type: str = "synthetic"

class SleepingPadCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    r_value: float = 2.0
    pad_type: str = "foam"

class ClothingCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    layer_type: str = "mid"
    waterproof: bool = False
    min_temp_f: int = 32

class WaterSystemCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    system_type: str = "filter"
    flow_rate_lpm: float = 1.0

class KitchenCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    stove_type: Optional[str] = None
    cookware_included: bool = False
    boil_time_min: float = 0.0

class NavigationCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    nav_type: str = "map"

class LightingCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    lumens: int = 0
    lighting_type: str = "headlamp"

class SafetyCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    safety_type: str = "first_aid"
    avalanche_rated: bool = False

class TechnicalCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    technical_type: str = "ice_axe"

class TrekkingPolesCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost:   float = Field(ge=0)
    adjustable: bool = True
    material: str = "aluminum"


# =============================================================================
# Serializer — Item subclass → response dict
# =============================================================================

def item_to_response(item: Item) -> ItemResponseSchema:
    base: dict[str, Any] = {
        "id":        item.id,
        "name":      item.name,
        "weight":    item.weight,
        "cost":      item.cost,
        "item_type": item.item_type,
        "image_url": item.image_url,
    }
    if isinstance(item, Backpack):
        base.update(capacity_liters=item.capacity_liters, frame_type=item.frame_type)
    elif isinstance(item, Footwear):
        base.update(waterproof=item.waterproof, crampon_compatible=item.crampon_compatible, ankle_support=item.ankle_support)
    elif isinstance(item, Shelter):
        base.update(capacity_persons=item.capacity_persons, season_rating=item.season_rating, shelter_type=item.shelter_type)
    elif isinstance(item, SleepingBag):
        base.update(temp_rating_f=item.temp_rating_f, fill_type=item.fill_type)
    elif isinstance(item, SleepingPad):
        base.update(r_value=item.r_value, pad_type=item.pad_type)
    elif isinstance(item, Clothing):
        base.update(layer_type=item.layer_type, waterproof=item.waterproof, min_temp_f=item.min_temp_f)
    elif isinstance(item, WaterSystem):
        base.update(system_type=item.system_type, flow_rate_lpm=item.flow_rate_lpm)
    elif isinstance(item, Kitchen):
        base.update(stove_type=item.stove_type, cookware_included=item.cookware_included, boil_time_min=item.boil_time_min)
    elif isinstance(item, NavigationTool):
        base.update(nav_type=item.nav_type)
    elif isinstance(item, Lighting):
        base.update(lumens=item.lumens, lighting_type=item.lighting_type)
    elif isinstance(item, SafetyGear):
        base.update(safety_type=item.safety_type, avalanche_rated=item.avalanche_rated)
    elif isinstance(item, TechnicalGear):
        base.update(technical_type=item.technical_type)
    elif isinstance(item, TrekkingPoles):
        base.update(adjustable=item.adjustable, material=item.material)
    return ItemResponseSchema(**base)


# =============================================================================
# Routes
# =============================================================================

# ── List / single reads ────────────────────────────────────────────────────────

@router.get("/", response_model=List[ItemResponseSchema])
def list_items(item_type: Optional[str] = Query(None, description="Filter by item_type, e.g. 'backpack'")):
    """List all items, optionally filtered by item_type."""
    return [item_to_response(i) for i in service.list_items(item_type=item_type)]

@router.get("/by-name/{name}", response_model=ItemResponseSchema)
def get_item_by_name(name: str):
    item = service.get_item_by_name(name)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_to_response(item)

@router.get("/{item_id}", response_model=ItemResponseSchema)
def get_item(item_id: UUID):
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_to_response(item)

# ── Image update ───────────────────────────────────────────────────────────────

@router.patch("/{item_id}/image", response_model=ItemResponseSchema)
def update_item_image(item_id: UUID, payload: ImageUpdateSchema):
    if not service.get_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    repo.update_item_image(item_id, payload.image_url)
    return item_to_response(service.get_item(item_id))

# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: UUID):
    if not service.get_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    service.delete_item(item_id)

# ── Create — one route per type ────────────────────────────────────────────────

def _create(item: Item) -> ItemResponseSchema:
    item_id = service.create_item(item)
    item.id = item_id
    return item_to_response(item)

@router.post("/backpacks", response_model=ItemResponseSchema)
def create_backpack(p: BackpackCreateSchema):
    return _create(Backpack(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                            capacity_liters=p.capacity_liters, frame_type=p.frame_type))

@router.post("/footwear", response_model=ItemResponseSchema)
def create_footwear(p: FootwearCreateSchema):
    return _create(Footwear(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                            waterproof=p.waterproof, crampon_compatible=p.crampon_compatible,
                            ankle_support=p.ankle_support))

@router.post("/shelters", response_model=ItemResponseSchema)
def create_shelter(p: ShelterCreateSchema):
    return _create(Shelter(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                           capacity_persons=p.capacity_persons, season_rating=p.season_rating,
                           shelter_type=p.shelter_type))

@router.post("/sleeping-bags", response_model=ItemResponseSchema)
def create_sleeping_bag(p: SleepingBagCreateSchema):
    return _create(SleepingBag(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                               temp_rating_f=p.temp_rating_f, fill_type=p.fill_type))

@router.post("/sleeping-pads", response_model=ItemResponseSchema)
def create_sleeping_pad(p: SleepingPadCreateSchema):
    return _create(SleepingPad(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                               r_value=p.r_value, pad_type=p.pad_type))

@router.post("/clothing", response_model=ItemResponseSchema)
def create_clothing(p: ClothingCreateSchema):
    return _create(Clothing(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                            layer_type=p.layer_type, waterproof=p.waterproof, min_temp_f=p.min_temp_f))

@router.post("/water", response_model=ItemResponseSchema)
def create_water_system(p: WaterSystemCreateSchema):
    return _create(WaterSystem(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                               system_type=p.system_type, flow_rate_lpm=p.flow_rate_lpm))

@router.post("/kitchen", response_model=ItemResponseSchema)
def create_kitchen(p: KitchenCreateSchema):
    return _create(Kitchen(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                           stove_type=p.stove_type, cookware_included=p.cookware_included,
                           boil_time_min=p.boil_time_min))

@router.post("/navigation", response_model=ItemResponseSchema)
def create_navigation(p: NavigationCreateSchema):
    return _create(NavigationTool(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                                  nav_type=p.nav_type))

@router.post("/lighting", response_model=ItemResponseSchema)
def create_lighting(p: LightingCreateSchema):
    return _create(Lighting(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                            lumens=p.lumens, lighting_type=p.lighting_type))

@router.post("/safety", response_model=ItemResponseSchema)
def create_safety(p: SafetyCreateSchema):
    return _create(SafetyGear(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                              safety_type=p.safety_type, avalanche_rated=p.avalanche_rated))

@router.post("/technical", response_model=ItemResponseSchema)
def create_technical(p: TechnicalCreateSchema):
    return _create(TechnicalGear(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                                 technical_type=p.technical_type))

@router.post("/trekking-poles", response_model=ItemResponseSchema)
def create_trekking_poles(p: TrekkingPolesCreateSchema):
    return _create(TrekkingPoles(id=uuid4(), name=p.name, weight=p.weight, cost=p.cost,
                                 adjustable=p.adjustable, material=p.material))