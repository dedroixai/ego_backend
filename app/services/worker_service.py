"""Business logic for WORKER.

Source: app/models/worker.py, docs/database-design.md Section 1.2.

Business rules implemented:
- A worker profile can only be created by the user it belongs to
  (`requester_id == user_id`), for a USER that exists, and only once (the
  shared-PK 1:1 relationship - Section 2 relationship #1). A second attempt
  is a duplicate operation, not a generic 500.
- Only the profile owner may update it (Step 6).

Deliberately NOT enforced (undefined - see docs/database-design.md Section
7.3): that `User.role` must equal some specific literal before a Worker
profile can be created. `role`'s allowed values are undefined anywhere in
the diagrams, so this service cannot check `user.role == "worker"` without
guessing what that literal string actually is. Documented in
docs/service-layer.md as an unresolved decision.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from app.models.worker import Worker
from app.repositories.exceptions import RepositoryError
from app.repositories.user_repository import UserRepository
from app.repositories.worker_repository import WorkerRepository
from app.services.base import BaseService
from app.services.exceptions import (
    DuplicateOperationError,
    ResourceNotFoundError,
    UnauthorizedOperationError,
)


class WorkerService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._workers = WorkerRepository(session)
        self._users = UserRepository(session)

    async def get_profile(self, user_id: uuid.UUID) -> Worker:
        worker = await self._workers.get_by_id(user_id)
        if worker is None:
            raise ResourceNotFoundError("Worker", user_id)
        return worker

    async def list_public_workers(
        self,
        *,
        location: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[Worker]:
        """Public, read-only browse/discovery listing (`GET
        /api/v1/workers`) - no auth required, mirrors
        `JobService.list_public_jobs`'s shape exactly. Nothing here
        checks who's asking; the route's response model
        (`WorkerListResponse`) is what keeps this exposure-safe, not
        this method."""
        return await self._workers.list_public(location=location, search=search, limit=limit, offset=offset)

    async def create_profile(
        self,
        user_id: uuid.UUID,
        requester_id: uuid.UUID,
        *,
        name: str,
        skills: list[str] | None = None,
        experience: int | None = None,
        expected_wage: Decimal | None = None,
        availability: str | None = None,
        service_locations: list[str] | None = None,
        bank_details: str | None = None,
        profile_image_url: str | None = None,
    ) -> Worker:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only create your own worker profile.")

        if await self._users.get_by_id(user_id) is None:
            raise ResourceNotFoundError("User", user_id)

        if await self._workers.get_by_id(user_id) is not None:
            raise DuplicateOperationError(f"Worker profile already exists for user {user_id}")

        try:
            worker = await self._workers.create(
                user_id=user_id,
                name=name,
                skills=skills or [],
                experience=experience,
                expected_wage=expected_wage,
                availability=availability,
                service_locations=service_locations or [],
                bank_details=bank_details,
                profile_image_url=profile_image_url,
            )
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return worker

    async def update_profile(self, user_id: uuid.UUID, requester_id: uuid.UUID, **changes: object) -> Worker:
        if requester_id != user_id:
            raise UnauthorizedOperationError("You can only update your own worker profile.")

        worker = await self.get_profile(user_id)
        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            return worker

        try:
            updated = await self._workers.update(worker, **changes)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return updated
