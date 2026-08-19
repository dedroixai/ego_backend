"""API schemas for MESSAGE.

Source: app/models/message.py, docs/database-design.md Section 1.7.

`sender_id` is an ownership field - excluded from `MessageCreate`, derived
server-side from the authenticated user (see app/api/v1/endpoints/messages.py).

`job_id` is optional (see app/models/message.py's doc comment for why) -
omit it for a general "contact this person" message with no job context.

No `MessageUpdate` - neither diagram describes messages as editable once sent.
"""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class MessageCreate(RequestModel):
    receiver_id: uuid.UUID
    content: str = Field(min_length=1, max_length=5000)
    job_id: uuid.UUID | None = None


class MessageResponse(ORMModel):
    message_id: uuid.UUID
    job_id: uuid.UUID | None
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    content: str
    timestamp: datetime


class ConversationSummary(ORMModel):
    """One row per distinct (counterpart, job) pair - the inbox/thread-list
    shape. `other_user_id` is whichever of sender/receiver isn't the
    requester. No `unread_count`/read-receipt field: `Message` has no
    `read` column (see app/models/message.py) and no read-tracking is
    implemented anywhere else in this app - inventing one here would be a
    fabricated metric, not a real one."""

    other_user_id: uuid.UUID
    job_id: uuid.UUID | None
    last_message: MessageResponse
