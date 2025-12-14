from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List
from uuid import UUID

from PyObjects.Items import Item
from Repos.ItemRepo import ItemRepository
from Services.ItemService import ItemService

# =========================
# Schemas (Top of file)
# =========================

class ItemCreateSchema(BaseModel):
    name: str = Field(..., example="Hiking Backpack")
    weight: float = Field(..., ge=0, example=2.5)
    cost: float = Field(..., ge=0, example=120.00)


class ItemResponseSchema(ItemCreateSchema):
    id: UUID


# =========================
# Controller
# =========================

router = APIRouter(prefix="/items", tags=["Items"])

repo = ItemRepository()
service = ItemService(repo)


@router.post("/", response_model=ItemResponseSchema)
def create_item(payload: ItemCreateSchema):
    try:
        item = Item(
            name=payload.name,
            weight=payload.weight,
            cost=payload.cost
        )
        item_id = service.create_item(item)
        return ItemResponseSchema(id=item_id, **payload.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{item_id}", response_model=ItemResponseSchema)
def get_item(item_id: UUID):
    try:
        item = service.get_item(item_id)
        return ItemResponseSchema(
            id=item_id,
            name=item.name,
            weight=item.weight,
            cost=item.cost
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found")


@router.get("/", response_model=List[ItemResponseSchema])
def list_items():
    items = service.list_items()
    return [
        ItemResponseSchema(
            id=item_id,
            name=item.name,
            weight=item.weight,
            cost=item.cost
        )
        for item_id, item in zip(repo._items.keys(), items)
    ]


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: UUID):
    service.delete_item(item_id)
