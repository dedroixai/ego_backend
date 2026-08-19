"""Base class for services.

Unlike repositories (which only `flush()` - see docs/repository-layer.md),
**services own the transaction boundary**: a service method that writes
data commits on success and rolls back on failure. This is "the
appropriate service/database-session level" Step 7 of this task refers to
- a future API layer just calls a service method and gets back either a
result or a `ServiceError`; it never touches the session directly.
"""

from typing import NoReturn

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.exceptions import RepositoryError
from app.services.exceptions import translate_repository_error


class BaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _commit(self) -> None:
        await self.session.commit()

    async def _rollback_and_raise(self, exc: RepositoryError) -> NoReturn:
        await self.session.rollback()
        raise translate_repository_error(exc) from exc
