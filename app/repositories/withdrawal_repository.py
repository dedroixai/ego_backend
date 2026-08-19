"""Data access for WITHDRAWAL.

Source: app/models/withdrawal.py, docs/database-design.md Section 1.9.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.withdrawal import Withdrawal
from app.repositories.base import BaseRepository


class WithdrawalRepository(BaseRepository[Withdrawal]):
    model = Withdrawal

    async def list_by_worker(
        self, worker_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal).where(Withdrawal.worker_id == worker_id).limit(limit).offset(offset)
        )
        return result.scalars().all()
