"""MESSAGE entity - a message sent between two users, optionally in the
context of a job.

Source: diagrams/er_diagram.mermaid (MESSAGE), docs/database-design.md Section 1.7.

Deviation: `attachments` (class diagram only) is NOT implemented - see
docs/database-design.md Section 7.8 and docs/model-implementation.md.

Deviation: `job_id` is nullable - both diagrams draw MESSAGE as always
belonging to a JOB (`jobId FK`, no "optional" annotation). Changed on
explicit product request (chat feature): a business browsing workers
needs to be able to message one directly, before any job/application
connects them - there is no job to attach that conversation to. A
`job_id`-scoped message stays a real job-context conversation (and, per
`MessageService.send_message`'s docstring, is now gated on an *accepted*
JobMatch between the two parties); `job_id IS NULL` means "general
contact," never assumed to be about any particular job.

Note: `receiverId` has no drawn relationship line in the ER diagram (only
`senderId`'s "sends" relationship is drawn) - implemented as NOT NULL per
the design document's recommendation. See docs/database-design.md Section 7.12.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=True, index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    job: Mapped["Job | None"] = relationship(back_populates="messages")
    # Two FKs to USER on this table - foreign_keys= disambiguates which
    # column each relationship uses.
    sender: Mapped["User"] = relationship(back_populates="sent_messages", foreign_keys=[sender_id])
    receiver: Mapped["User"] = relationship(back_populates="received_messages", foreign_keys=[receiver_id])

    def __repr__(self) -> str:
        return f"Message(message_id={self.message_id!r}, job_id={self.job_id!r})"
