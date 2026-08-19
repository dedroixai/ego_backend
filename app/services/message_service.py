"""Business logic for MESSAGE (chat).

Source: app/models/message.py, docs/database-design.md Section 1.7.

Business rules implemented:
- The sender is always the requester (an identity, not a business rule per
  se, but enforced here so the caller can't spoof it - see
  api-schema-design.md's exclusion of `sender_id` from `MessageCreate`).
- A user cannot message themselves.
- The receiver must be a real user.
- A **job-scoped** message (`job_id` given) requires the job to exist AND
  requires an *accepted* `JobMatch` between the two parties for that job -
  "the owner accepts an application, that's a match, and a chat option
  unlocks" (the explicit product request this was built for). Checked
  both directions (`get_accepted_match(job_id, sender_id)` or
  `(job_id, receiver_id)`) since either party could be the worker.
- A **job-less** message (`job_id` omitted) has none of that gating - this
  is the "contact a worker directly" case (e.g. from browsing Nearby
  Workers, before any application exists) - see app/models/message.py's
  doc comment for why `job_id` became nullable to support this.
"""

import uuid
from collections.abc import Sequence

from app.models.message import Message
from app.repositories.exceptions import RepositoryError
from app.repositories.job_match_repository import JobMatchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.services.exceptions import BusinessRuleViolationError, ResourceNotFoundError, UnauthorizedOperationError


class MessageService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._messages = MessageRepository(session)
        self._jobs = JobRepository(session)
        self._users = UserRepository(session)
        self._job_matches = JobMatchRepository(session)

    async def list_for_job(self, job_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> Sequence[Message]:
        return await self._messages.list_by_job(job_id, limit=limit, offset=offset)

    async def list_thread(
        self,
        requester_id: uuid.UUID,
        other_user_id: uuid.UUID,
        *,
        job_id: uuid.UUID | None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[Message]:
        """No extra authorization check needed beyond the query itself -
        it only ever returns messages between `requester_id` and
        `other_user_id`, so a requester can't read anyone else's thread
        no matter what `other_user_id` they pass."""
        return await self._messages.list_thread(requester_id, other_user_id, job_id=job_id, limit=limit, offset=offset)

    async def list_conversations(self, requester_id: uuid.UUID, *, limit: int = 500) -> list[dict]:
        """Groups this user's recent messages into distinct (counterpart,
        job) threads, most-recently-active first - the inbox/thread-list
        view. Returns plain dicts (`ConversationSummary` validates from
        either an object or a dict via `from_attributes=True`) since this
        shape - a bare `other_user_id` plus a nested `Message` - has no
        single ORM row to build it from."""
        messages = await self._messages.list_for_user(requester_id, limit=limit)

        seen: set[tuple[uuid.UUID, uuid.UUID | None]] = set()
        conversations: list[dict] = []
        for message in messages:
            other_user_id = message.receiver_id if message.sender_id == requester_id else message.sender_id
            key = (other_user_id, message.job_id)
            if key in seen:
                continue
            seen.add(key)
            conversations.append({"other_user_id": other_user_id, "job_id": message.job_id, "last_message": message})
        return conversations

    async def send_message(
        self,
        sender_id: uuid.UUID,
        receiver_id: uuid.UUID,
        content: str,
        job_id: uuid.UUID | None = None,
    ) -> Message:
        if sender_id == receiver_id:
            raise BusinessRuleViolationError("You cannot send a message to yourself.")

        if await self._users.get_by_id(receiver_id) is None:
            raise ResourceNotFoundError("User", receiver_id)

        if job_id is not None:
            if await self._jobs.get_by_id(job_id) is None:
                raise ResourceNotFoundError("Job", job_id)

            has_accepted_match = (
                await self._job_matches.get_accepted_match(job_id, sender_id) is not None
                or await self._job_matches.get_accepted_match(job_id, receiver_id) is not None
            )
            if not has_accepted_match:
                raise UnauthorizedOperationError(
                    "You can only message about a job once the application has been accepted."
                )

        try:
            message = await self._messages.create(
                job_id=job_id, sender_id=sender_id, receiver_id=receiver_id, content=content
            )
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return message
