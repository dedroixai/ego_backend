"""Business logic for USER.

Source: app/models/user.py, docs/database-design.md Section 1.1.

Business rule implemented: a user may only view/update their own profile
(Step 6's explicit example - "A user should not be able to modify another
user's profile"). `requester_id` is the authenticated caller's identity,
supplied by the future API/auth layer - this service never handles tokens.
"""

import uuid
from datetime import date

from app.models.user import User
from app.repositories.exceptions import RepositoryError
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.services.exceptions import ResourceNotFoundError, UnauthorizedOperationError


class UserService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._users = UserRepository(session)

    async def get_profile(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError("User", user_id)
        return user

    async def update_profile(
        self,
        user_id: uuid.UUID,
        requester_id: uuid.UUID,
        *,
        language: str | None = None,
        dob: date | None = None,
    ) -> User:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only update your own profile.")

        user = await self.get_profile(user_id)
        changes = {k: v for k, v in {"language": language, "dob": dob}.items() if v is not None}
        if not changes:
            return user

        try:
            updated = await self._users.update(user, **changes)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return updated
