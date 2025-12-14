from uuid import UUID, uuid4
from typing import List, Optional

from PyObjects.User import User
from Repos.UserRepo import UserRepository
from PyObjects.Items import Item



class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def create_user(
        self,
        email: str,
        hashed_password: str,
        name: str,
        avatar_url: Optional[str] = None,
        home_location: Optional[dict] = None,
        timezone: Optional[str] = None,
        items: Optional[list] = None,
    ) -> User:
        user = User(
            id=uuid4(),
            email=email,
            hashed_password=hashed_password,
            name=name,
            avatar_url=avatar_url,
            home_location=home_location,
            timezone=timezone,
            items=[Item.from_dict(i) for i in items] if items else [],
        )

        return self.user_repository.create(user)


    def get_user(self, user_id: UUID) -> Optional[User]:
        return self.user_repository.get_by_id(user_id)

    def list_users(self) -> List[User]:
        return self.user_repository.list_all()

    def update_user(self, user: User) -> User:
        """
        Assumes the caller already has a valid User object.
        """
        existing = self.user_repository.get_by_id(user.id)
        if not existing:
            raise ValueError("User not found")

        return self.user_repository.update(user)

    def delete_user(self, user_id: UUID) -> None:
        existing = self.user_repository.get_by_id(user_id)
        if not existing:
            raise ValueError("User not found")

        self.user_repository.delete(user_id)
    def list_items(self, user_id: UUID) -> list[Item]:
        user = self.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        return user.items

    def add_item(self, user_id: UUID, item_data: dict) -> Item:
        user = self.get_user(user_id)
        if not user:
            raise ValueError("User not found")

        item = Item.from_dict(item_data)
        user.items.append(item)

        self.user_repository.update(user)
        return item

    def delete_item(self, user_id: UUID, item_index: int) -> None:
        user = self.get_user(user_id)
        if not user:
            raise ValueError("User not found")

        if item_index < 0 or item_index >= len(user.items):
            raise ValueError("Item not found")

        user.items.pop(item_index)
        self.user_repository.update(user)