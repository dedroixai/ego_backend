"""Data access for JOB_MATCH ("Job Application" in Task 12's product
language - same entity, see app/services/job_match_service.py).

Source: app/models/job_match.py, docs/database-design.md Section 1.6.

`get_by_job_and_worker` backs the Task 12 duplicate-application check.
**No UNIQUE constraint exists on `(job_id, worker_id)` in the actual
database** (verified directly against Supabase; also already flagged as
unconfirmed in docs/database-design.md Section 7.11 and
docs/model-implementation.md) - this method is the ONLY thing preventing
a duplicate application, which means it is subject to a race condition
under concurrent requests. See "APPLICATION UNIQUENESS SCHEMA DECISION
REQUIRED" in docs/application-api.md - not silently fixed here.

`get_by_id`/`list_by_job` are overridden (not just inherited from
`BaseRepository`) to eager-load the `worker` relationship
(`selectinload`, one extra batched query, not N+1) - Task 19's
`JobMatchWithWorkerResponse` needs `match.worker` populated, and
`AsyncSession` cannot lazy-load a relationship after the fact without it
(`MissingGreenlet`). Every existing caller of these two methods (worker
withdraw, business review, both `JobMatchResponse`-only routes) is
unaffected - they simply never read the now-also-loaded `.worker`
attribute, and `JobMatchResponse` has no such field to accidentally leak
it through.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.job_match import JobMatch
from app.repositories.base import BaseRepository


class JobMatchRepository(BaseRepository[JobMatch]):
    model = JobMatch

    async def get_by_id(self, id_value: uuid.UUID) -> JobMatch | None:
        result = await self.session.execute(
            select(JobMatch).options(selectinload(JobMatch.worker)).where(JobMatch.match_id == id_value)
        )
        return result.scalars().first()

    async def list_by_job(self, job_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> Sequence[JobMatch]:
        result = await self.session.execute(
            select(JobMatch)
            .options(selectinload(JobMatch.worker))
            .where(JobMatch.job_id == job_id)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def list_by_worker(
        self, worker_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[JobMatch]:
        result = await self.session.execute(
            select(JobMatch).where(JobMatch.worker_id == worker_id).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def get_by_job_and_worker(self, job_id: uuid.UUID, worker_id: uuid.UUID) -> JobMatch | None:
        # .first(), not .scalar_one_or_none(): with no UNIQUE constraint on
        # this pair (see module docstring), more than one row could exist -
        # this method must not raise if that's ever true, just report that
        # at least one application already exists.
        result = await self.session.execute(
            select(JobMatch).where(JobMatch.job_id == job_id, JobMatch.worker_id == worker_id)
        )
        return result.scalars().first()

    async def get_accepted_match(self, job_id: uuid.UUID, worker_id: uuid.UUID) -> JobMatch | None:
        """Same shape as `get_by_job_and_worker`, filtered to `status ==
        "accepted"` - backs `MessageService`'s "chat unlocks once the
        business accepts this worker's application" gate (see its
        docstring). `.first()` for the same no-UNIQUE-constraint reason as
        `get_by_job_and_worker` - only existence matters here, not which
        specific row."""
        result = await self.session.execute(
            select(JobMatch).where(
                JobMatch.job_id == job_id, JobMatch.worker_id == worker_id, JobMatch.status == "accepted"
            )
        )
        return result.scalars().first()
