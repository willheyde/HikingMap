# File: Services/UserService.py
from uuid import UUID, uuid4
from typing import List, Optional

# --- FIX: Import from Schemas, NOT Router ---
from Schemas.UserSchemas import UserUpdate 
# --------------------------------------------

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

    # --- Google OAuth ---------------------------------------------------------

    def get_user_by_google_sub(self, google_sub: str) -> Optional[User]:
        return self.user_repository.get_by_google_sub(google_sub)

    def create_google_user(self, email, name, google_sub, avatar_url=None) -> User:
        """Create an account from a verified Google identity — no password."""
        user = User(
            id=uuid4(),
            email=email,
            hashed_password=None,          # OAuth account: no local password
            name=name,
            avatar_url=avatar_url,
            google_sub=google_sub,
            auth_provider="google",
            items=[],
        )
        return self.user_repository.create(user)

    def link_google_account(self, user_id: UUID, google_sub: str) -> None:
        """Attach a Google identity to an existing password account."""
        self.user_repository.link_google_sub(user_id, google_sub)

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
    def update_user_details(self, user_id: UUID, updates: 'UserUpdate') -> User:
        """
        Fetches existing user, applies non-null updates, and saves to DB.
        """
        # 1. Fetch existing user
        user = self.get_user(user_id)
        if not user:
            raise ValueError("User not found")

        # 2. Update fields if they are provided in the payload
        # checking "is not None" allows us to clear fields if we pass an empty string/dict if needed, 
        # distinct from just not sending the field.
        if updates.name is not None:
            user.name = updates.name
            
        if updates.avatar_url is not None:
            user.avatar_url = updates.avatar_url
            
        if updates.home_location is not None:
            # The Repo handles the json.dumps conversion
            user.home_location = updates.home_location 
            
        if updates.timezone is not None:
            user.timezone = updates.timezone

        if updates.email is not None:
            # Note: usually you'd want to check if the new email is already taken here
            user.email = updates.email

        # 3. Persist changes
        return self.user_repository.update(user)