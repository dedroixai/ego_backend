"""Data access for MESSAGE.

Source: app/models/message.py, docs/database-design.md Section 1.7.

No update/delete - messages are not described as editable/removable in
either diagram (see docs/api-schema-design.md).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import and_, or_, select

from app.models.message import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_by_job(self, job_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> Sequence[Message]:
        result = await self.session.execute(
            select(Message).where(Message.job_id == job_id).order_by(Message.timestamp).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def list_thread(
        self,
        user_a: uuid.UUID,
        user_b: uuid.UUID,
        *,
        job_id: uuid.UUID | None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[Message]:
        """Every message between exactly these two users for one specific
        thread - `job_id=None` means the general (no-job) thread with this
        person, not "any job" - a job-scoped and a job-less thread with the
        same two people are deliberately separate conversations (see
        app/models/message.py's doc comment). `Message.job_id == None`
        correctly compiles to `IS NULL` (SQLAlchemy's `Column == None`
        special case), so this one query serves both cases."""
        stmt = (
            select(Message)
            .where(
                Message.job_id == job_id,
                or_(
                    and_(Message.sender_id == user_a, Message.receiver_id == user_b),
                    and_(Message.sender_id == user_b, Message.receiver_id == user_a),
                ),
            )
            .order_by(Message.timestamp)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_user(self, user_id: uuid.UUID, *, limit: int = 500) -> Sequence[Message]:
        """Every message this user sent or received, most recent first -
        the raw material `MessageService.list_conversations` groups into
        distinct (counterpart, job) threads. Grouping happens in the
        service layer, not a `DISTINCT ON` here - simpler and more
        portable for the message volume an MVP actually has, at the cost
        of being O(n) in this user's total message count rather than
        O(thread count); revisit if that ever matters."""
        stmt = (
            select(Message)
            .where(or_(Message.sender_id == user_id, Message.receiver_id == user_id))
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
