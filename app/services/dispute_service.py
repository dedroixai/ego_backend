"""Business logic for DISPUTE.

Source: app/models/dispute.py, docs/database-design.md Section 1.15.

Business rule implemented: the raiser is always the requester, and a user
may only list their own disputes. `status` defaults to `'open'` - already
an established literal (docs/model-implementation.md), not guessed - left
to the DB default rather than overridden here.

`job_id` stays optional (matching the model's nullable FK - itself a
direct, deliberately-not-silently-fixed implementation of the ER diagram's
literal notation, see docs/database-design.md Section 7.14): if provided,
the job must exist; if omitted, no job-existence check applies.

No resolution/management logic (`Admin.manageDispute()` in the class
diagram) - no Admin entity or auth layer yet (Section 7.16).
"""

import uuid
from collections.abc import Sequence

from app.models.dispute import Dispute
from app.repositories.dispute_repository import DisputeRepository
from app.repositories.exceptions import RepositoryError
from app.repositories.job_repository import JobRepository
from app.services.base import BaseService
from app.services.exceptions import ResourceNotFoundError, UnauthorizedOperationError


class DisputeService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._disputes = DisputeRepository(session)
        self._jobs = JobRepository(session)

    async def list_for_user(
        self, user_id: uuid.UUID, requester_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Dispute]:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only view your own disputes.")
        return await self._disputes.list_by_raised_by(user_id, limit=limit, offset=offset)

    async def raise_dispute(
        self, raised_by: uuid.UUID, requester_id: uuid.UUID, *, job_id: uuid.UUID | None = None
    ) -> Dispute:
        if requester_id != raised_by:
            raise UnauthorizedOperationError("You can only raise disputes as yourself.")

        if job_id is not None and await self._jobs.get_by_id(job_id) is None:
            raise ResourceNotFoundError("Job", job_id)

        try:
            dispute = await self._disputes.create(raised_by=raised_by, job_id=job_id)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return dispute
