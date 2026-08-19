"""Data access for DISPUTE.

Source: app/models/dispute.py, docs/database-design.md Section 1.15.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.dispute import Dispute
from app.repositories.base import BaseRepository


class DisputeRepository(BaseRepository[Dispute]):
    model = Dispute

    async def get_by_job(self, job_id: uuid.UUID) -> Dispute | None:
        result = await self.session.execute(select(Dispute).where(Dispute.job_id == job_id))
        return result.scalar_one_or_none()

    async def list_by_raised_by(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Dispute]:
        result = await self.session.execute(
            select(Dispute).where(Dispute.raised_by == user_id).limit(limit).offset(offset)
        )
        return result.scalars().all()
