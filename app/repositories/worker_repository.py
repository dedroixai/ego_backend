"""Data access for WORKER.

Source: app/models/worker.py, docs/database-design.md Section 1.2.

No extra lookups beyond the inherited `get_by_id` (the primary key,
`user_id`, is the shared key with USER - there is no separate "worker id")
and `list_public` (browse/nearby-workers - added alongside the new
`GET /api/v1/workers` public listing endpoint, mirroring
`JobRepository.list_public`).
"""

from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.worker import Worker
from app.repositories.base import BaseRepository


class WorkerRepository(BaseRepository[Worker]):
    model = Worker

    async def list_public(
        self,
        *,
        location: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Worker]:
        stmt = select(Worker)
        if location is not None:
            # `service_locations` is a TEXT[], not a scalar column - no
            # `.ilike()` directly. Flattening to a comma-joined string
            # for a substring match mirrors Job.location's plain
            # substring-match philosophy exactly, without a geo/array
            # query this app has no other need for yet.
            stmt = stmt.where(func.array_to_string(Worker.service_locations, ",").ilike(f"%{location}%"))
        if search is not None:
            stmt = stmt.where(
                Worker.name.ilike(f"%{search}%") | func.array_to_string(Worker.skills, ",").ilike(f"%{search}%")
            )
        stmt = stmt.order_by(Worker.rating.desc().nulls_last()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()
