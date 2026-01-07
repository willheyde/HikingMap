from uuid import UUID
from typing import List, Optional
from PyObjects.User import User
from PyObjects.Items import Item
from Repos.RepositoryBase import BaseRepository
from DBConnection import get_connection
import json

class UserRepository(BaseRepository[User]):

    def create(self, user: User) -> User:
        user_data = user.to_dict()
        
        # FIX: We no longer store items in the JSON blob.
        # We assume the user is created with 0 items initially.
        user_data['home_location'] = json.dumps(user_data['home_location']) if user_data['home_location'] else None

        # Note: We removed 'items' from the INSERT logic below
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, email, hashed_password, name, avatar_url, home_location, timezone, created_at)
                    VALUES (
                        %(id)s, %(email)s, %(hashed_password)s, %(name)s,
                        %(avatar_url)s, %(home_location)s, %(timezone)s,
                        %(created_at)s
                    )
                    """,
                    user_data
                )
        return user

    def update(self, user: User) -> User:
        user_data = user.to_dict()
        user_data['home_location'] = json.dumps(user_data['home_location']) if user_data['home_location'] else None

        # FIX: Removed 'items' from the SET clause
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET email=%(email)s,
                        hashed_password=%(hashed_password)s,
                        name=%(name)s,
                        avatar_url=%(avatar_url)s,
                        home_location=%(home_location)s,
                        timezone=%(timezone)s
                    WHERE id=%(id)s
                    """,
                    user_data
                )
        return user

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # JOIN users -> user_items -> items
                query = """
                    SELECT 
                        u.id, u.email, u.hashed_password, u.name, u.avatar_url, 
                        u.home_location, u.timezone, u.created_at,
                        i.id as item_id, i.name as item_name, i.weight, i.cost, i.item_type, i.image_url
                    FROM users u
                    LEFT JOIN user_items ui ON u.id = ui.user_id
                    LEFT JOIN items i ON ui.item_id = i.id
                    WHERE u.id = %s
                """
                cur.execute(query, (str(user_id),))
                rows = cur.fetchall()
                
                if not rows:
                    return None

                # 1. Initialize User from the first row
                first_row = rows[0]
                user_dict = {
                    "id": first_row['id'],
                    "email": first_row['email'],
                    "hashed_password": first_row['hashed_password'],
                    "name": first_row['name'],
                    "avatar_url": first_row['avatar_url'],
                    "home_location": first_row['home_location'],
                    "timezone": first_row['timezone'],
                    "created_at": str(first_row['created_at']),
                    "items": []
                }

                # 2. Loop through all rows to collect items
                items_list = []
                for row in rows:
                    if row['item_id']: # Check if there is actually an item (LEFT JOIN can be null)
                        items_list.append({
                            "id": row['item_id'],
                            "name": row['item_name'],
                            "weight": row['weight'],
                            "cost": row['cost'],
                            "item_type": row['item_type'],
                            "image_url": row['image_url']
                        })
                print(f"DEBUGGING STARTING HERE_________")
                for item in items_list:
                    print(f"Item data: {item}")  # Debug: see what data is being passed

                user_dict["items"] = items_list
                return User.from_dict(user_dict)
                
    def add_user_items_links(self, user_id: UUID, item_ids: List[str]):
        """Inserts relationships into the junction table."""
        if not item_ids: return

        query = "INSERT INTO user_items (user_id, item_id) VALUES (%s, %s) ON CONFLICT DO NOTHING"
        data_tuples = [(str(user_id), str(iid)) for iid in item_ids]
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(query, data_tuples)

    def remove_user_item_link(self, user_id: UUID, item_id: str):
        """Removes a relationship from the junction table."""
        query = "DELETE FROM user_items WHERE user_id = %s AND item_id = %s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (str(user_id), str(item_id)))

    # ... keep get_by_email, delete, and list_all (list_all might need similar JOIN logic if you list items there) ...
    # For brevity, standard methods like 'delete' remain unchanged except ensuring cascade handles the links.
    def get_by_email(self, email: str) -> Optional[User]:
        # NOTE: You should replicate the JOIN logic from get_by_id here if you want items on login
        # For now, sticking to simple fetch to prevent huge code block
        with get_connection() as conn:
             with conn.cursor() as cur:
                 cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                 row = cur.fetchone()
                 # Warning: This won't load items unless you add the JOIN logic
                 return User.from_dict(row) if row else None
    
    def list_all(self) -> List[User]:
        # Basic list without items for performance
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users")
                return [User.from_dict(r) for r in cur.fetchall()]

    def delete(self, user_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (str(user_id),))