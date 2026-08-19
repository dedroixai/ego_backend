"""Business logic for JOB.

Source: app/models/job.py, docs/database-design.md Section 1.5.

Business rules implemented:
- Job ownership: only the hiring party who posted a job may update it or
  change its status (Step 6's explicit example - "A business should not
  modify another business's job").
- Creating a job requires the requesting hiring party to actually exist,
  and the referenced category to actually exist - checked explicitly here
  (clean `ResourceNotFoundError`) rather than only relying on the
  repository's FK-violation translation as the sole signal.

## Job status vocabulary and lifecycle (Task 11 decision - read this)

`docs/database-design.md` Section 7.3 and `docs/service-layer.md`
(Task 7) both establish that `Job.status`'s allowed values are undefined
anywhere in the ER/class diagrams - Task 7 deliberately left this
unimplemented rather than guess. Task 11 explicitly needed job creation,
publishing, and lifecycle management to actually work end to end, and
itself offered `DRAFT -> OPEN -> CLOSED` as its own illustrative example
(twice, in its Step 3). This service now adopts exactly that vocabulary
(lowercase, matching this project's existing status-literal convention:
`"draft"`, `"open"`, `"closed"`) as a **flagged, provisional decision**,
not a diagram-confirmed fact - see "JOB STATUS VOCABULARY DECISION
REQUIRED" in docs/job-lifecycle.md for the full reasoning and what should
happen if product confirms a different vocabulary.

Concretely:
- `create_job` no longer takes a `status` parameter - every new job starts
  as `"draft"`, set here, never client-supplied.
- `update_status` now validates the transition against `_VALID_TRANSITIONS`
  below and raises `InvalidStateTransitionError` for anything not listed -
  e.g. `"closed" -> "open"` is rejected, mirroring Task 11's own
  "Completed -> Open should not be possible" example.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from app.models.job import Job
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.exceptions import RepositoryError
from app.repositories.job_category_repository import JobCategoryRepository
from app.repositories.job_repository import JobRepository
from app.services.base import BaseService
from app.services.exceptions import (
    InvalidStateTransitionError,
    ResourceNotFoundError,
    UnauthorizedOperationError,
)

INITIAL_JOB_STATUS = "draft"

# See module docstring - a provisional, flagged vocabulary, not diagram-confirmed.
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"open", "closed"},
    "open": {"closed"},
    "closed": set(),
}


class JobService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._jobs = JobRepository(session)
        self._hiring_parties = HiringPartyRepository(session)
        self._categories = JobCategoryRepository(session)

    async def get_job(self, job_id: uuid.UUID) -> Job:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise ResourceNotFoundError("Job", job_id)
        return job

    async def list_by_hiring_party(
        self, hiring_party_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Job]:
        return await self._jobs.list_by_hiring_party(hiring_party_id, limit=limit, offset=offset)

    async def list_by_status(self, status: str, *, limit: int = 100, offset: int = 0) -> Sequence[Job]:
        return await self._jobs.list_by_status(status, limit=limit, offset=offset)

    async def list_by_category(
        self, category_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Job]:
        return await self._jobs.list_by_category(category_id, limit=limit, offset=offset)

    async def list_public_jobs(
        self,
        *,
        status: str | None = None,
        category_id: uuid.UUID | None = None,
        location: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[Job]:
        """Defaults to `status="open"` - "browse the dashboard" means
        publicly-available jobs, not drafts or closed postings. Callers may
        pass an explicit `status` to see something else (e.g. a client
        that already knows to look for closed jobs); nothing here checks
        who's asking, since this is a public, read-only listing."""
        return await self._jobs.list_public(
            status=status or "open",
            category_id=category_id,
            location=location,
            search=search,
            limit=limit,
            offset=offset,
        )

    async def create_job(
        self,
        hiring_party_id: uuid.UUID,
        requester_id: uuid.UUID,
        *,
        category_id: uuid.UUID,
        title: str,
        description: str,
        budget: Decimal,
        location: str,
        duration: str | None = None,
        image_url: str | None = None,
    ) -> Job:
        if requester_id != hiring_party_id:
            raise UnauthorizedOperationError("You can only post jobs for your own hiring-party profile.")

        if await self._hiring_parties.get_by_id(hiring_party_id) is None:
            raise ResourceNotFoundError("HiringParty", hiring_party_id)

        if await self._categories.get_by_id(category_id) is None:
            raise ResourceNotFoundError("JobCategory", category_id)

        try:
            job = await self._jobs.create(
                hiring_party_id=hiring_party_id,
                category_id=category_id,
                title=title,
                description=description,
                budget=budget,
                location=location,
                status=INITIAL_JOB_STATUS,
                duration=duration,
                image_url=image_url,
            )
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return job

    async def update_job(self, job_id: uuid.UUID, requester_id: uuid.UUID, **changes: object) -> Job:
        job = await self.get_job(job_id)
        if requester_id != job.hiring_party_id:
            raise UnauthorizedOperationError("You can only update jobs you posted.")

        if "category_id" in changes and changes["category_id"] is not None:
            if await self._categories.get_by_id(changes["category_id"]) is None:  # type: ignore[arg-type]
                raise ResourceNotFoundError("JobCategory", changes["category_id"])

        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            return job

        try:
            updated = await self._jobs.update(job, **changes)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return updated

    async def update_status(self, job_id: uuid.UUID, requester_id: uuid.UUID, status: str) -> Job:
        """Ownership-gated AND transition-validated - see module docstring."""
        job = await self.get_job(job_id)
        if requester_id != job.hiring_party_id:
            raise UnauthorizedOperationError("You can only change the status of jobs you posted.")

        allowed = _VALID_TRANSITIONS.get(job.status, set())
        if status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition job from '{job.status}' to '{status}'."
            )

        try:
            updated = await self._jobs.update(job, status=status)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return updated
