"""Business logic for COMPLETION_VERIFICATION.

Source: app/models/completion_verification.py, docs/database-design.md
Section 1.12. Models the `markJobComplete()` (worker) /
`confirmCompletion()` (hiring party) actions from the class diagram.

Business rules implemented:
- Only the job's hiring party may *initiate* verification tracking for
  their own job, and only once (mandatory 1:1 with Job - Section 2
  relationship #12) - a second attempt is a duplicate operation.
- `confirm_completion` determines the caller's role from data that already
  exists (the job's `hiring_party_id`, and any `JobMatch` linking a worker
  to this job) rather than a passed-in role flag, so a caller cannot claim
  a role they don't have.
- **Transactional multi-repository example (Step 7)**: when confirming
  completion causes *both* `worker_confirmed` and `hiring_party_confirmed`
  to become true, this service also records the completed job against the
  Worker<->HiringParty `CONNECTION` (get-or-create the pair, increment
  `jobs_completed`) - CONNECTION's entire documented purpose is "tracking
  their repeat-work history" (docs/database-design.md Section 1.13). Both
  writes are flushed in the same session and committed together; if either
  fails, both roll back.

Deliberately NOT implemented: determining "the assigned worker" via a
confirmed/accepted `JobMatch.status` value, since those values are
undefined (docs/database-design.md Section 7.3). Instead, ANY worker with
*any* `JobMatch` row for this job is treated as eligible to confirm - a
documented approximation, not a guess at the real status vocabulary. See
docs/service-layer.md.
"""

import uuid

from app.models.completion_verification import CompletionVerification
from app.repositories.completion_verification_repository import CompletionVerificationRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.exceptions import RepositoryError
from app.repositories.job_match_repository import JobMatchRepository
from app.repositories.job_repository import JobRepository
from app.services.base import BaseService
from app.services.exceptions import DuplicateOperationError, ResourceNotFoundError, UnauthorizedOperationError


class CompletionVerificationService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._verifications = CompletionVerificationRepository(session)
        self._jobs = JobRepository(session)
        self._matches = JobMatchRepository(session)
        self._connections = ConnectionRepository(session)

    async def get_for_job(self, job_id: uuid.UUID) -> CompletionVerification:
        verification = await self._verifications.get_by_job(job_id)
        if verification is None:
            raise ResourceNotFoundError("CompletionVerification", job_id)
        return verification

    async def initiate_verification(
        self, job_id: uuid.UUID, requester_id: uuid.UUID, *, method: str
    ) -> CompletionVerification:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise ResourceNotFoundError("Job", job_id)
        if requester_id != job.hiring_party_id:
            raise UnauthorizedOperationError("Only the hiring party that posted this job can initiate verification.")

        if await self._verifications.get_by_job(job_id) is not None:
            raise DuplicateOperationError(f"Completion verification already exists for job {job_id}")

        try:
            verification = await self._verifications.create(job_id=job_id, method=method)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return verification

    async def _find_assigned_worker_id(self, job_id: uuid.UUID) -> uuid.UUID | None:
        matches = await self._matches.list_by_job(job_id, limit=1)
        return matches[0].worker_id if matches else None

    async def confirm_completion(self, job_id: uuid.UUID, requester_id: uuid.UUID) -> CompletionVerification:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise ResourceNotFoundError("Job", job_id)

        verification = await self.get_for_job(job_id)

        is_hiring_party = requester_id == job.hiring_party_id
        is_assigned_worker = requester_id == await self._find_assigned_worker_id(job_id)

        if not is_hiring_party and not is_assigned_worker:
            raise UnauthorizedOperationError(
                "Only the hiring party or a worker matched to this job can confirm completion."
            )

        was_already_complete = verification.worker_confirmed and verification.hiring_party_confirmed

        try:
            if is_hiring_party:
                verification = await self._verifications.update(verification, hiring_party_confirmed=True)
            else:
                verification = await self._verifications.update(verification, worker_confirmed=True)

            now_complete = verification.worker_confirmed and verification.hiring_party_confirmed
            if now_complete and not was_already_complete:
                worker_id = await self._find_assigned_worker_id(job_id)
                if worker_id is not None:
                    connection = await self._connections.get_by_pair(worker_id, job.hiring_party_id)
                    if connection is None:
                        await self._connections.create(
                            worker_id=worker_id, hiring_party_id=job.hiring_party_id, jobs_completed=1
                        )
                    else:
                        await self._connections.update(
                            connection, jobs_completed=connection.jobs_completed + 1
                        )
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)

        await self._commit()
        return verification
