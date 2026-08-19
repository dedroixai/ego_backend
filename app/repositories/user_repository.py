"""Data access for USER.

Source: app/models/user.py, docs/database-design.md Section 1.1.
"""

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_phone(self, phone: str) -> User | None:
        result = await self.session.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def get_by_firebase_uid(self, firebase_uid: str) -> User | None:
        result = await self.session.execute(select(User).where(User.firebase_uid == firebase_uid))
        return result.scalar_one_or_none()
