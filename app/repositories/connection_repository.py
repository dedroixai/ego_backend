"""Data access for CONNECTION.

Source: app/models/connection.py, docs/database-design.md Section 1.13.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.connection import Connection
from app.repositories.base import BaseRepository


class ConnectionRepository(BaseRepository[Connection]):
    model = Connection

    async def get_by_pair(self, worker_id: uuid.UUID, hiring_party_id: uuid.UUID) -> Connection | None:
        result = await self.session.execute(
            select(Connection).where(
                Connection.worker_id == worker_id,
                Connection.hiring_party_id == hiring_party_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_worker(
        self, worker_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Connection]:
        result = await self.session.execute(
            select(Connection).where(Connection.worker_id == worker_id).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def list_by_hiring_party(
        self, hiring_party_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Connection]:
        result = await self.session.execute(
            select(Connection).where(Connection.hiring_party_id == hiring_party_id).limit(limit).offset(offset)
        )
        return result.scalars().all()
