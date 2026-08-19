"""Business logic for HIRING_PARTY.

Source: app/models/business.py, docs/database-design.md Section 1.3.

Mirrors app/services/worker_service.py's rules exactly (same shared-PK
1:1-with-USER structure): ownership-gated create/update, existence and
duplicate-profile checks. See that file's docstring for the same caveat
about `User.role` not being checked (undefined values).
"""

import uuid

from app.models.business import HiringParty
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.exceptions import RepositoryError
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.services.exceptions import (
    DuplicateOperationError,
    ResourceNotFoundError,
    UnauthorizedOperationError,
)


class HiringPartyService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._hiring_parties = HiringPartyRepository(session)
        self._users = UserRepository(session)

    async def get_profile(self, user_id: uuid.UUID) -> HiringParty:
        hiring_party = await self._hiring_parties.get_by_id(user_id)
        if hiring_party is None:
            raise ResourceNotFoundError("HiringParty", user_id)
        return hiring_party

    async def create_profile(
        self,
        user_id: uuid.UUID,
        requester_id: uuid.UUID,
        *,
        account_type: str,
        business_name: str | None = None,
        address: str | None = None,
        profile_image_url: str | None = None,
    ) -> HiringParty:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only create your own hiring-party profile.")

        if await self._users.get_by_id(user_id) is None:
            raise ResourceNotFoundError("User", user_id)

        if await self._hiring_parties.get_by_id(user_id) is not None:
            raise DuplicateOperationError(f"HiringParty profile already exists for user {user_id}")

        try:
            hiring_party = await self._hiring_parties.create(
                user_id=user_id,
                account_type=account_type,
                business_name=business_name,
                address=address,
                profile_image_url=profile_image_url,
            )
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return hiring_party

    async def update_profile(self, user_id: uuid.UUID, requester_id: uuid.UUID, **changes: object) -> HiringParty:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only update your own hiring-party profile.")

        hiring_party = await self.get_profile(user_id)
        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            return hiring_party

        try:
            updated = await self._hiring_parties.update(hiring_party, **changes)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return updated
