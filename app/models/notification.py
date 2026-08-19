"""NOTIFICATION entity - a notification sent to a user.

Source: diagrams/er_diagram.mermaid (NOTIFICATION), docs/database-design.md Section 1.14.

`message` and `created_at` were previously flagged as class-diagram-only
and NOT implemented (see docs/database-design.md Section 7.8) - Task 21
resolves that: a push notification's body text has to be stored
SOMEWHERE for `/notifications` (Step 14) to be useful at all, and the
class diagram already names the field `message`, so this adopts that
name rather than inventing a new one. `created_at` the same way -
displaying "when" a notification arrived is table-stakes for a
notification list.

`entity_type`/`entity_id` are new beyond even the class diagram - added
for Step 10/11 (structured payload + tap-to-navigate): a notification
needs to say WHICH application/job it's about so the client can route
there, or gracefully fall back if that entity is gone by the time the
notification is opened. Both nullable - a notification type that isn't
about a specific entity (none exist yet, but nothing requires one to)
isn't forced to fabricate one.

Every field here that isn't in either diagram is flagged inline, per this
project's standing discipline - see docs/notifications.md for the full
reasoning.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # Composite index - the dominant query is "unread notifications for
        # this user". See docs/database-design.md Section 6.
        Index("ix_notifications_user_id_is_read", "user_id", "is_read"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Task 21 - what this notification is about, for tap-to-navigate
    # (Step 11). No FK constraint - deliberately: the referenced
    # application/job may legitimately be gone by the time this is read,
    # and a notification is a historical record, not a live reference
    # that should be invalidated/cascaded when its subject changes.
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="notifications")

    def __repr__(self) -> str:
        return f"Notification(notification_id={self.notification_id!r}, user_id={self.user_id!r}, type={self.type!r})"
