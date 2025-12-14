from uuid import UUID
from typing import List, Optional
from PyObjects.User import User
from Repos.RepositoryBase import BaseRepository
from DBConnection import get_connection

class UserRepository(BaseRepository[User]):

    def create(self, user: User) -> User:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users VALUES (
                        %(id)s, %(email)s, %(hashed_password)s, %(name)s,
                        %(avatar_url)s, %(home_location)s, %(timezone)s,
                        %(items)s, %(created_at)s
                    )
                    """,
                    user.to_dict()
                )
        return user


    def get_by_id(self, user_id: UUID) -> Optional[User]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE id = %s",
                    (user_id,)
                )
                row = cur.fetchone()
                return User.from_dict(row) if row else None

    def list_all(self) -> List[User]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users")
                return [User.from_dict(r) for r in cur.fetchall()]

    def update(self, user: User) -> User:
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
                        timezone=%(timezone)s,
                        items=%(items)s
                    WHERE id=%(id)s
                    """,
                    user.to_dict()
                )
        return user

    
    def delete(self, user_id: UUID) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
