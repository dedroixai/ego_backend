"""Business logic for JOB_CATEGORY.

Source: app/models/job_category.py, docs/database-design.md Section 1.4.

Minimal - a category has no owner (unlike Job/Worker/HiringParty), so
there's no ownership rule to enforce here. The one real rule: category
names must be unique, translated into a clean `DuplicateOperationError`
rather than letting a raw constraint error propagate. Admin-only
restriction on who may create categories (`Admin.manageCategories()` in
the class diagram) is deferred - there is no Admin entity/auth layer yet
(see docs/database-design.md Section 7.16).
"""

from collections.abc import Sequence
import uuid

from app.models.job_category import JobCategory
from app.repositories.exceptions import RepositoryError
from app.repositories.job_category_repository import JobCategoryRepository
from app.services.base import BaseService
from app.services.exceptions import ResourceNotFoundError


class JobCategoryService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._categories = JobCategoryRepository(session)

    async def get_category(self, category_id: uuid.UUID) -> JobCategory:
        category = await self._categories.get_by_id(category_id)
        if category is None:
            raise ResourceNotFoundError("JobCategory", category_id)
        return category

    async def list_categories(self, *, limit: int = 100, offset: int = 0) -> Sequence[JobCategory]:
        return await self._categories.list(limit=limit, offset=offset)

    async def create_category(self, name: str) -> JobCategory:
        try:
            category = await self._categories.create(name=name)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return category
