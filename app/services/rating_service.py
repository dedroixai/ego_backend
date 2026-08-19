"""Business logic for RATING.

Source: app/models/rating.py, docs/database-design.md Section 1.10.

Business rules implemented:
- The rater is always the requester (`from_user_id == requester_id`).
- A user cannot rate themselves.
- A user cannot submit more than one rating for the same (job, from_user,
  to_user) triple - the DB has no UNIQUE constraint for this (deliberately
  left out in Task 3: docs/database-design.md Section 7.11 flags it as only
  "possibly" intended, not stated by either diagram), but "don't let someone
  rate the same job twice" is a clearly-justified, self-contained business
  rule that doesn't depend on any undefined vocabulary - checked explicitly
  here rather than at the DB layer.
- The referenced job must exist.

NOT implemented: restricting ratings to actual job participants (same
undefined-"participant" gap as MessageService/JobMatchService) - documented
in docs/service-layer.md.
"""

import uuid
from collections.abc import Sequence

from app.models.rating import Rating
from app.repositories.exceptions import RepositoryError
from app.repositories.job_repository import JobRepository
from app.repositories.rating_repository import RatingRepository
from app.services.base import BaseService
from app.services.exceptions import (
    BusinessRuleViolationError,
    DuplicateOperationError,
    ResourceNotFoundError,
    UnauthorizedOperationError,
)


class RatingService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._ratings = RatingRepository(session)
        self._jobs = JobRepository(session)

    async def list_for_job(self, job_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> Sequence[Rating]:
        return await self._ratings.list_by_job(job_id, limit=limit, offset=offset)

    async def list_received_by_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Rating]:
        return await self._ratings.list_received_by_user(user_id, limit=limit, offset=offset)

    async def submit_rating(
        self,
        job_id: uuid.UUID,
        from_user_id: uuid.UUID,
        requester_id: uuid.UUID,
        *,
        to_user_id: uuid.UUID,
        score: int,
        comment: str | None = None,
    ) -> Rating:
        if requester_id != from_user_id:
            raise UnauthorizedOperationError("You can only submit ratings as yourself.")

        if from_user_id == to_user_id:
            raise BusinessRuleViolationError("You cannot rate yourself.")

        if await self._jobs.get_by_id(job_id) is None:
            raise ResourceNotFoundError("Job", job_id)

        existing = await self._ratings.list_by_job(job_id, limit=1000)
        if any(r.from_user_id == from_user_id and r.to_user_id == to_user_id for r in existing):
            raise DuplicateOperationError("You have already rated this user for this job.")

        try:
            rating = await self._ratings.create(
                job_id=job_id, from_user_id=from_user_id, to_user_id=to_user_id, score=score, comment=comment
            )
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return rating
