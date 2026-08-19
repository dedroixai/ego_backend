"""Data access for NOTIFICATION.

Source: app/models/notification.py, docs/database-design.md Section 1.14.

`list_by_user`'s `unread_only` filter mirrors the composite
`ix_notifications_user_id_is_read` index created in Task 4 specifically for
this query. Deleting a notification (dismissing it) uses the inherited
`delete` - a reasonable, minimal case for Step 3's "delete where
appropriate" (see docs/repository-layer.md).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return result.scalars().all()
