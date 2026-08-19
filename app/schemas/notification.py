"""API schemas for NOTIFICATION.

Source: app/models/notification.py, docs/database-design.md Section 1.14.

No `NotificationCreate` - notifications are server-generated (Task 21:
`NotificationService.notify`, called from other services as a side effect
of a business action), never created directly by a client request body.
`NotificationUpdate` models the one realistic client action (mark
read/unread) - `is_read` is required here (narrow action schema, not
a general partial-update, same reasoning as `JobMatchUpdate`).
"""

import uuid
from datetime import datetime

from app.schemas.base import ORMModel, RequestModel


class NotificationUpdate(RequestModel):
    is_read: bool


class NotificationResponse(ORMModel):
    notification_id: uuid.UUID
    user_id: uuid.UUID
    type: str
    message: str
    is_read: bool
    created_at: datetime
    entity_type: str | None
    entity_id: uuid.UUID | None
