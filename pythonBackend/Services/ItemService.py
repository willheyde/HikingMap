# Services/ItemService.py
from uuid import UUID, uuid4
from typing import List, Optional

from PyObjects.Items import Item
from Repos.ItemRepo import ItemRepository


class ItemService:
    """Business logic layer for items"""

    def __init__(self, repo: ItemRepository) -> None:
        self.repo = repo

    def create_item(self, item: Item) -> UUID:
        """Create an item, returns the item's ID"""
        return self.repo.create_item(item)  # FIXED: was repo.save()

    def get_item(self, item_id: UUID) -> Optional[Item]:
        """Get item by ID"""
        return self.repo.get_item(item_id)
    
    def get_item_by_name(self, name: str) -> Optional[Item]:
        """Get item by name (useful for checking duplicates)"""
        return self.repo.get_item_by_name(name)

    def list_items(self) -> List[Item]:
        """List all items"""
        return self.repo.list_items()

    def delete_item(self, item_id: UUID) -> None:
        """Delete item"""
        self.repo.delete_item(item_id)