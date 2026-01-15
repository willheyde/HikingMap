from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from uuid import UUID, uuid4

from PyObjects.Items import Item, Backpack, Clothing, Shoes, WeatherConditions
from Repos.ItemRepo import ItemRepository
from Services.ItemService import ItemService

# =========================
# Schemas
# =========================

class BackpackCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost: float = Field(ge=0)
    capacity_liters: float = Field(ge=0)

class ClothingCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost: float = Field(ge=0)
    weather_conditions: WeatherConditions

class ShoesCreateSchema(BaseModel):
    name: str
    weight: float = Field(ge=0)
    cost: float = Field(ge=0)
    weather_conditions: WeatherConditions
    crampons: bool = False

class ImageUpdateSchema(BaseModel):
    image_url: str

class ItemResponseSchema(BaseModel):
    id: UUID
    name: str
    weight: float
    cost: float
    item_type: str
    image_url: Optional[str] = None  # Ensure this is here
    capacity_liters: Optional[float] = None
    weather_conditions: Optional[WeatherConditions] = None
    crampons: Optional[bool] = None

# =========================
# Controller
# =========================

router = APIRouter(tags=["Items"])

repo = ItemRepository()
service = ItemService(repo)

def item_to_response(item: Item) -> ItemResponseSchema:
    """Convert any Item subtype to response schema"""
    base = {
        "id": item.id,
        "name": item.name,
        "weight": item.weight,
        "cost": item.cost,
        "item_type": item.item_type,
        "image_url": item.image_url  # UPDATED: Map the image url
    }
    
    if isinstance(item, Shoes):
        return ItemResponseSchema(**base, 
            weather_conditions=item.weather_conditions,
            crampons=item.crampons)
    elif isinstance(item, Clothing):
        return ItemResponseSchema(**base,
            weather_conditions=item.weather_conditions)
    elif isinstance(item, Backpack):
        return ItemResponseSchema(**base,
            capacity_liters=item.capacity_liters)
    
    return ItemResponseSchema(**base)

@router.post("/backpacks", response_model=ItemResponseSchema)
def create_backpack(payload: BackpackCreateSchema):
    item = Backpack(
        id=uuid4(),
        name=payload.name,
        weight=payload.weight,
        cost=payload.cost,
        capacity_liters=payload.capacity_liters
    )
    item_id = service.create_item(item)
    item.id = item_id
    return item_to_response(item)

@router.post("/clothing", response_model=ItemResponseSchema)
def create_clothing(payload: ClothingCreateSchema):
    item = Clothing(
        id=uuid4(),
        name=payload.name,
        weight=payload.weight,
        cost=payload.cost,
        weather_conditions=payload.weather_conditions
    )
    item_id = service.create_item(item)
    item.id = item_id
    return item_to_response(item)

@router.post("/shoes", response_model=ItemResponseSchema)
def create_shoes(payload: ShoesCreateSchema):
    item = Shoes(
        id=uuid4(),
        name=payload.name,
        weight=payload.weight,
        cost=payload.cost,
        weather_conditions=payload.weather_conditions,
        crampons=payload.crampons
    )
    item_id = service.create_item(item)
    item.id = item_id
    return item_to_response(item)

@router.patch("/{item_id}/image", response_model=ItemResponseSchema)
def update_item_image(item_id: UUID, payload: ImageUpdateSchema):
    """
    Updates the image URL for an existing item.
    """
    # 1. Check if item exists
    existing_item = service.get_item(item_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Item not found")

    # 2. Update the image in the Repo
    # Note: Ideally add this method to your Service, but calling repo directly works for now
    repo.update_item_image(item_id, payload.image_url)

    # 3. Fetch fresh item to return
    updated_item = service.get_item(item_id)
    return item_to_response(updated_item)

@router.get("/{item_id}", response_model=ItemResponseSchema)
def get_item(item_id: UUID):
    item = service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_to_response(item)

@router.get("/", response_model=List[ItemResponseSchema])
def list_items():
    items = service.list_items()
    return [item_to_response(item) for item in items]

@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: UUID):
    service.delete_item(item_id)


@router.get("/by-name/{name}", response_model=ItemResponseSchema)
def get_item_by_name(name: str):
    """
    Retrieve a single item by its exact name.
    Note: this returns the first matching item. Consider making a
    case-insensitive or fuzzy search if you want multiple/more flexible matches.
    """
    item = service.get_item_by_name(name)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_to_response(item)