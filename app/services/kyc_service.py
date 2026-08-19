"""Business logic for KYC.

Source: app/models/kyc.py, docs/database-design.md Section 1.11.

Business rule implemented: a user may only submit/view their own KYC
documents. `status` defaults to `'pending'` - this literal IS already
established (docs/model-implementation.md: the DB column itself defaults to
`'pending'`), so, unlike Job/Withdrawal/JobMatch status, this one is not
guessed - it's simply not overridden here, letting the DB default apply.

NOT implemented: verification/approval (`Admin.verifyKYC()` in the class
diagram) - there is no Admin entity or auth/authorization layer yet (see
docs/database-design.md Section 7.16). This service only covers submission.
"""

import uuid
from collections.abc import Sequence

from app.models.kyc import KYC
from app.repositories.exceptions import RepositoryError
from app.repositories.kyc_repository import KYCRepository
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.services.exceptions import ResourceNotFoundError, UnauthorizedOperationError


class KYCService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._kyc = KYCRepository(session)
        self._users = UserRepository(session)

    async def list_for_user(
        self, user_id: uuid.UUID, requester_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[KYC]:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only view your own KYC documents.")
        return await self._kyc.list_by_user(user_id, limit=limit, offset=offset)

    async def submit_document(self, user_id: uuid.UUID, requester_id: uuid.UUID, *, document_type: str) -> KYC:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only submit KYC documents for yourself.")

        if await self._users.get_by_id(user_id) is None:
            raise ResourceNotFoundError("User", user_id)

        try:
            document = await self._kyc.create(user_id=user_id, document_type=document_type)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return document
