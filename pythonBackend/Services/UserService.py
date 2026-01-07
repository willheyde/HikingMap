from uuid import UUID, uuid4
from typing import List, Optional
from PyObjects.User import User
from Repos.UserRepo import UserRepository
from PyObjects.Items import Item

class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    # ... create_user, get_user, list_users, login_user ... (Unchanged)
    def create_user(self, email, hashed_password, name, avatar_url=None, home_location=None, timezone=None, items=None) -> User:
        user = User(
            id=uuid4(),
            email=email,
            hashed_password=hashed_password,
            name=name,
            avatar_url=avatar_url,
            home_location=home_location,
            timezone=timezone,
            items=[] # Items added separately
        )
        return self.user_repository.create(user)

    def get_user(self, user_id: UUID) -> Optional[User]:
        return self.user_repository.get_by_id(user_id)
    
    def get_user_by_email(self, email: str):
        return self.user_repository.get_by_email(email)

    def list_users(self) -> List[User]:
        return self.user_repository.list_all()
        
    def update_user(self, user: User) -> User:
        return self.user_repository.update(user)
        
    def delete_user(self, user_id: UUID) -> None:
        self.user_repository.delete(user_id)

    # --- CHANGED METHODS ---

    def list_items(self, user_id: UUID) -> list[Item]:
        user = self.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        return user.items

    def add_item(self, user_id: UUID, item_id: str) -> List[Item]:
        """Adds a single item by ID"""
        # 1. Add link
        self.user_repository.add_user_items_links(user_id, [item_id])
        # 2. Refetch user to get updated list
        return self.list_items(user_id)

    def add_items_batch(self, user_id: UUID, item_ids: List[str]) -> List[Item]:
        """Adds multiple items by ID list"""
        # 1. Add links
        self.user_repository.add_user_items_links(user_id, item_ids)
        # 2. Refetch user to get updated list
        return self.list_items(user_id)

    def delete_item(self, user_id: UUID, item_id: str) -> None:
        """Deletes item by ID (not index)"""
        self.user_repository.remove_user_item_link(user_id, item_id)