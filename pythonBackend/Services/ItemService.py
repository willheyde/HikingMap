from uuid import UUID
from typing import List, Optional

from PyObjects.Items import Item
from Repos.ItemRepo import ItemRepository


class ItemService:
    """Business logic layer for items."""

    def __init__(self, repo: ItemRepository) -> None:
        self.repo = repo

    def create_item(self, item: Item) -> UUID:
        return self.repo.create_item(item)

    def get_item(self, item_id: UUID) -> Optional[Item]:
        return self.repo.get_item(item_id)

    def get_item_by_name(self, name: str) -> Optional[Item]:
        return self.repo.get_item_by_name(name)

    def list_items(self, item_type: Optional[str] = None) -> List[Item]:
        """Pass an item_type string to filter (e.g. 'backpack', 'footwear')."""
        return self.repo.list_items(item_type=item_type)

    def delete_item(self, item_id: UUID) -> None:
        self.repo.delete_item(item_id)