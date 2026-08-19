"""Data access for KYC.

Source: app/models/kyc.py, docs/database-design.md Section 1.11.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.kyc import KYC
from app.repositories.base import BaseRepository


class KYCRepository(BaseRepository[KYC]):
    model = KYC

    async def list_by_user(self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> Sequence[KYC]:
        result = await self.session.execute(select(KYC).where(KYC.user_id == user_id).limit(limit).offset(offset))
        return result.scalars().all()
