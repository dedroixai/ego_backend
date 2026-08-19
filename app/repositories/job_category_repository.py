"""Data access for JOB_CATEGORY.

Source: app/models/job_category.py, docs/database-design.md Section 1.4.
"""

from sqlalchemy import select

from app.models.job_category import JobCategory
from app.repositories.base import BaseRepository


class JobCategoryRepository(BaseRepository[JobCategory]):
    model = JobCategory

    async def get_by_name(self, name: str) -> JobCategory | None:
        result = await self.session.execute(select(JobCategory).where(JobCategory.name == name))
        return result.scalar_one_or_none()
