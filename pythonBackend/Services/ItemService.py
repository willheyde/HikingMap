from uuid import UUID, uuid4
from typing import List

from PyObjects.Items import Item
from Repos.ItemRepo import ItemRepository


class ItemService:
    """
    Business logic layer.
    """

    def __init__(self, repo: ItemRepository) -> None:
        self.repo = repo

    def create_item(self, item: Item) -> UUID:
        item_id = uuid4()
        self.repo.save(item_id, item)
        return item_id

    def get_item(self, item_id: UUID) -> Item:
        item = self.repo.get(item_id)
        if not item:
            raise ValueError("Item not found")
        return item

    def list_items(self) -> List[Item]:
        return self.repo.list_all()

    def delete_item(self, item_id: UUID) -> None:
        self.repo.delete(item_id)
