"""Data access for JOB.

Source: app/models/job.py, docs/database-design.md Section 1.5.

The single-filter listing methods below mirror the indexes created for
exactly this purpose in Task 4 (`ix_jobs_hiring_party_id`, `ix_jobs_status`,
`ix_jobs_category_id`) and docs/database-design.md Section 6's own stated
rationale for each index. `list_public` (Task 11) combines status/category/
location filters for the public job-browsing endpoint - the only
"filtering" this project implements (docs/job-api.md): no search engine,
ranking, or matching.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.job import Job
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    model = Job

    async def list_by_hiring_party(
        self, hiring_party_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Job]:
        result = await self.session.execute(
            select(Job).where(Job.hiring_party_id == hiring_party_id).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def list_by_status(self, status: str, *, limit: int = 100, offset: int = 0) -> Sequence[Job]:
        result = await self.session.execute(select(Job).where(Job.status == status).limit(limit).offset(offset))
        return result.scalars().all()

    async def list_by_category(
        self, category_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Job]:
        result = await self.session.execute(
            select(Job).where(Job.category_id == category_id).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def list_public(
        self,
        *,
        status: str | None = None,
        category_id: uuid.UUID | None = None,
        location: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Job]:
        stmt = select(Job)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if category_id is not None:
            stmt = stmt.where(Job.category_id == category_id)
        if location is not None:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if search is not None:
            # Title only, not description - matches what a worker
            # actually scans a job card for (JobCard/JobListResponse both
            # show title, never description in the list view).
            stmt = stmt.where(Job.title.ilike(f"%{search}%"))
        stmt = stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()
