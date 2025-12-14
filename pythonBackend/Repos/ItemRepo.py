from typing import Dict, List
from uuid import UUID

from PyObjects.Items import Item


class ItemRepository:
    """
    Simple in-memory repository.
    Replace with DB-backed repo later.
    """

    def __init__(self) -> None:
        self._items: Dict[UUID, Item] = {}

    def save(self, item_id: UUID, item: Item) -> None:
        self._items[item_id] = item

    def get(self, item_id: UUID) -> Item | None:
        return self._items.get(item_id)

    def delete(self, item_id: UUID) -> None:
        self._items.pop(item_id, None)

    def list_all(self) -> List[Item]:
        return list(self._items.values())
