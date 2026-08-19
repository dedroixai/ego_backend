"""Data access for RATING.

Source: app/models/rating.py, docs/database-design.md Section 1.10.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.rating import Rating
from app.repositories.base import BaseRepository


class RatingRepository(BaseRepository[Rating]):
    model = Rating

    async def list_by_job(self, job_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> Sequence[Rating]:
        result = await self.session.execute(
            select(Rating).where(Rating.job_id == job_id).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def list_received_by_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Rating]:
        result = await self.session.execute(
            select(Rating).where(Rating.to_user_id == user_id).limit(limit).offset(offset)
        )
        return result.scalars().all()
