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
    # In ItemService
    def list_by_user(self, user_id: UUID) -> List[Item]:
        return self.repo.list_by_user(user_id)
    def create_item_for_user(self, item: Item, user_id: UUID) -> UUID:
        return self.repo.create_item_for_user(item, user_id)

    def create_user_gear(
        self,
        user_id: UUID,
        name: str,
        gear_category: str,
        level: Optional[str] = None,
        weight: float = 0.0,
        cost: float = 0.0,
        temp_rating_f: Optional[float] = None,
    ) -> Item:
        """Create a free-text 'I have this' gear item (functional category +
        optional level) and link it to the user."""
        return self.repo.create_user_gear(
            user_id=user_id, name=name, gear_category=gear_category,
            level=level, weight=weight, cost=cost, temp_rating_f=temp_rating_f,
        )