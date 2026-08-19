"""Business logic for JOB_MATCH ("Job Application" in Task 12's product
language - same underlying entity as Tasks 5-7's "JobMatch"; no renaming
was done to the model/table, matching the precedent set for
"Business"/"HiringParty" in docs/user-role-architecture.md.

Source: app/models/job_match.py, docs/database-design.md Section 1.6.

## What changed in Task 12 vs. Tasks 5-7

Tasks 5-7 assumed `JobMatch` rows were produced by a future matching
algorithm, with workers only *responding* to matches that already existed
("do not implement matching logic" was read as "do not implement match
*creation* either"). Task 12 clarifies the product flow: a worker
*applies* to a job directly (Dashboard -> Browse -> Apply) - this is a
plain, worker-initiated data-entry action, not a scoring/ranking/matching
algorithm, so implementing it does not conflict with "no matching logic."
`apply_to_job` is new; `respond_to_match` (Task 7) is superseded by the
more specific `withdraw_application`/`review_application` below, which
apply this task's adopted status vocabulary (see next section) instead of
accepting an arbitrary caller-supplied string.

## Application status vocabulary (same pattern as docs/job-lifecycle.md)

`job_matches.status`'s allowed values are undefined anywhere in the ER/
class diagrams (docs/database-design.md Section 7.3) - exactly the same
situation `Job.status` was in before Task 11. Task 12's own instructions
offered `Pending -> Accepted` / `Pending -> Rejected` as its illustrative
example (Step 7), and Step 5 requires a withdraw operation that must not
physically delete the row. This service adopts, as an explicitly
provisional decision (not diagram-confirmed - needs product sign-off):

    "pending"  - set automatically when a worker applies
    "accepted" - business accepts (terminal)
    "rejected" - business rejects (terminal)
    "withdrawn"- worker withdraws (terminal)

Task 12 Step 7 explicitly poses the question "if an application is already
rejected, [can] it be accepted later" and says "do not invent the rule" -
so nothing here allows any transition OUT of accepted/rejected/withdrawn.
Two separate transition tables (not one shared graph) because *who* may
reach which state differs: only the business may set accepted/rejected;
only the worker may set withdrawn.

## Duplicate applications - service-layer only (see repository docstring)

`app/repositories/job_match_repository.py`'s `get_by_job_and_worker` is
used to reject a second application for the same (job, worker) pair
*before* an INSERT is attempted - but there is no UNIQUE constraint
backing this at the database level (confirmed directly against Supabase -
docs/database-design.md Section 7.11 already flagged this as unconfirmed).
This means a race condition exists under concurrent requests for the same
pair. Not silently fixed - see "APPLICATION UNIQUENESS SCHEMA DECISION
REQUIRED" in docs/application-api.md.
"""

import logging
import uuid
from collections.abc import Sequence

from app.models.job_match import JobMatch
from app.repositories.exceptions import RepositoryError
from app.repositories.job_match_repository import JobMatchRepository
from app.repositories.job_repository import JobRepository
from app.services.base import BaseService
from app.services.exceptions import (
    BusinessRuleViolationError,
    DuplicateOperationError,
    InvalidStateTransitionError,
    ResourceNotFoundError,
    UnauthorizedOperationError,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

INITIAL_APPLICATION_STATUS = "pending"

# Task 21 Step 10 - the exact three MVP notification types (Step 7), used
# both as the persisted `Notification.type` and the FCM data payload's
# `type` field.
NOTIFICATION_APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
NOTIFICATION_APPLICATION_ACCEPTED = "APPLICATION_ACCEPTED"
NOTIFICATION_APPLICATION_REJECTED = "APPLICATION_REJECTED"

# See module docstring - a provisional, flagged vocabulary, not diagram-confirmed.
_BUSINESS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"accepted", "rejected"},
    "accepted": set(),
    "rejected": set(),
    "withdrawn": set(),
}
_WORKER_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"withdrawn"},
    "accepted": set(),
    "rejected": set(),
    "withdrawn": set(),
}

# Only jobs in this status accept new applications - directly follows from
# docs/job-lifecycle.md's adopted vocabulary ("open" = published/visible).
_APPLICATION_ELIGIBLE_JOB_STATUS = "open"


class JobMatchService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._matches = JobMatchRepository(session)
        self._jobs = JobRepository(session)
        self._notifications = NotificationService(session)

    async def get_match(self, match_id: uuid.UUID) -> JobMatch:
        match = await self._matches.get_by_id(match_id)
        if match is None:
            raise ResourceNotFoundError("JobMatch", match_id)
        return match

    async def list_for_job(self, job_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> Sequence[JobMatch]:
        return await self._matches.list_by_job(job_id, limit=limit, offset=offset)

    async def list_for_worker(
        self, worker_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[JobMatch]:
        return await self._matches.list_by_worker(worker_id, limit=limit, offset=offset)

    # --- Worker: apply ----------------------------------------------------

    async def apply_to_job(self, job_id: uuid.UUID, worker_id: uuid.UUID, requester_id: uuid.UUID) -> JobMatch:
        if requester_id != worker_id:
            raise UnauthorizedOperationError("You can only apply for yourself.")

        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise ResourceNotFoundError("Job", job_id)

        if job.status != _APPLICATION_ELIGIBLE_JOB_STATUS:
            raise BusinessRuleViolationError("This job is not currently accepting applications.")

        if await self._matches.get_by_job_and_worker(job_id, worker_id) is not None:
            raise DuplicateOperationError("You have already applied to this job.")

        try:
            application = await self._matches.create(
                job_id=job_id, worker_id=worker_id, status=INITIAL_APPLICATION_STATUS
            )
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()

        # Step 9: only AFTER the commit above. Step 18: a notification
        # failure must never undo/fail the application that was already
        # successfully created - the `try/except` here is deliberately
        # broad (not `except AppException`/`except RepositoryError`)
        # because ANY failure past this point (FCM down, a notification
        # DB error) is equally irrelevant to whether the application
        # itself succeeded, which it already has.
        try:
            await self._notifications.notify(
                job.hiring_party_id,
                notification_type=NOTIFICATION_APPLICATION_RECEIVED,
                title="New application received",
                # `job.title` is public information (any signed-out user
                # can browse it via `GET /jobs`) - not the worker's name/
                # identity, which stays out of the payload (Step 7: "do
                # not expose sensitive information").
                message=f'A worker applied to your job "{job.title}".',
                entity_type="job_match",
                entity_id=application.match_id,
            )
        except Exception:
            logger.exception(
                "Failed to send APPLICATION_RECEIVED notification for match %s", application.match_id
            )

        return application

    # --- Worker: view own applications, withdraw ---------------------------

    async def get_own_application(self, match_id: uuid.UUID, requester_id: uuid.UUID) -> JobMatch:
        match = await self.get_match(match_id)
        if requester_id != match.worker_id:
            raise UnauthorizedOperationError("You can only view your own applications.")
        return match

    async def withdraw_application(self, match_id: uuid.UUID, requester_id: uuid.UUID) -> JobMatch:
        match = await self.get_match(match_id)
        if requester_id != match.worker_id:
            raise UnauthorizedOperationError("You can only withdraw your own applications.")

        allowed = _WORKER_TRANSITIONS.get(match.status, set())
        if "withdrawn" not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot withdraw an application in '{match.status}' status."
            )

        try:
            updated = await self._matches.update(match, status="withdrawn")
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return updated

    # --- Business: view applications for a job owned by them, review ------

    async def list_applications_for_job(
        self, job_id: uuid.UUID, requester_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[JobMatch]:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise ResourceNotFoundError("Job", job_id)
        if requester_id != job.hiring_party_id:
            raise UnauthorizedOperationError("You can only view applications for jobs you posted.")
        return await self._matches.list_by_job(job_id, limit=limit, offset=offset)

    async def review_application(self, match_id: uuid.UUID, requester_id: uuid.UUID, *, status: str) -> JobMatch:
        match = await self.get_match(match_id)
        job = await self._jobs.get_by_id(match.job_id)
        if job is None or requester_id != job.hiring_party_id:
            raise UnauthorizedOperationError("You can only review applications for jobs you posted.")

        allowed = _BUSINESS_TRANSITIONS.get(match.status, set())
        if status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition application from '{match.status}' to '{status}'."
            )

        try:
            updated = await self._matches.update(match, status=status)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()

        # Step 9/18 - see `apply_to_job`'s identical comment. `status` is
        # already validated above as one of exactly `accepted`/`rejected`
        # (the only two values `_BUSINESS_TRANSITIONS` allows a business
        # to set), so this mapping can never silently fall through to
        # neither branch.
        if status == "accepted":
            notification_type = NOTIFICATION_APPLICATION_ACCEPTED
            title = "Application accepted"
            message = f'Your application for "{job.title}" was accepted.'
        else:
            notification_type = NOTIFICATION_APPLICATION_REJECTED
            title = "Application status updated"
            message = f'Your application status for "{job.title}" was updated.'

        try:
            await self._notifications.notify(
                updated.worker_id,
                notification_type=notification_type,
                title=title,
                message=message,
                entity_type="job_match",
                entity_id=updated.match_id,
            )
        except Exception:
            logger.exception("Failed to send %s notification for match %s", notification_type, updated.match_id)

        return updated

    # --- Either party: view a single application -----------------------

    async def get_application_for_viewer(self, match_id: uuid.UUID, viewer_user_id: uuid.UUID) -> JobMatch:
        """A worker may view their own application; a business may view any
        application for a job they own. Anyone else - including an
        unrelated worker or a different business - gets 403, whether or
        not the application/job actually exists (Step 8: "do not expose
        applications to unrelated users")."""
        match = await self.get_match(match_id)
        job = await self._jobs.get_by_id(match.job_id)

        is_applicant = viewer_user_id == match.worker_id
        is_job_owner = job is not None and viewer_user_id == job.hiring_party_id

        if not (is_applicant or is_job_owner):
            raise UnauthorizedOperationError("You do not have permission to view this application.")
        return match
