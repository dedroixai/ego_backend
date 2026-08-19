"""DEVICE_TOKEN entity - a Firebase Cloud Messaging device token for a user.

Absent from both the ER and class diagrams - Task 21 requires it
explicitly ("Determine whether the backend already has a device-token
table/model. If not, create an appropriate model."), flagged the same way
every other undiagrammed-but-necessary field/table has been throughout
this project (`Job.status`, `Worker.profile_image_url` - see
docs/storage-architecture.md). See docs/notifications.md for the full
architecture.

ONE USER -> MANY DEVICE TOKENS (Step 3's explicit requirement - a user
signed in on two phones must have both able to receive notifications, not
have the second registration silently replace the first). Enforced by
`user_id` being a plain (non-unique) foreign key, while `token` itself IS
unique - the same physical device/app-install can only ever map to one
row, so re-registering (e.g. after a token refresh, or the same device
logging in again) naturally updates that existing row instead of
accumulating duplicates for the same device.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (
        # Dominant query is "all of this user's tokens" (Step 3/16) - a
        # notification fan-out reads every row for one user_id.
        Index("ix_device_tokens_user_id", "user_id"),
    )

    device_token_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)

    token: Mapped[str] = mapped_column(String(4096), nullable=False, unique=True)
    # Not an enum - Android/iOS/web are the only realistic values today,
    # but (same reasoning as `Job.status`/`User.role`) nothing in this
    # project invents an enum for a field neither diagram defines at all.
    platform: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="device_tokens")

    def __repr__(self) -> str:
        return f"DeviceToken(device_token_id={self.device_token_id!r}, user_id={self.user_id!r}, platform={self.platform!r})"
