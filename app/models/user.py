"""USER entity - base identity record for every person on the platform.

Source: diagrams/er_diagram.mermaid (USER), docs/database-design.md Section 1.1.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.business import HiringParty
    from app.models.device_token import DeviceToken
    from app.models.dispute import Dispute
    from app.models.kyc import KYC
    from app.models.message import Message
    from app.models.notification import Notification
    from app.models.rating import Rating
    from app.models.worker import Worker


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    # Opaque Firebase Auth identifier - `nullable=True` since a User could in
    # principle exist without a linked Firebase identity (e.g. a
    # future admin-created record), but every self-service sign-in always
    # sets it (see app/auth/dependencies.py's get_current_user, which
    # auto-provisions a User the first time a verified Firebase identity has
    # no matching row here). See docs/authentication.md "AUTHENTICATION
    # SCHEMA DECISION" for why this was deliberately deferred until now.
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    kyc_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)

    # One-to-zero-or-one: USER extends into WORKER / HIRING_PARTY via shared PK
    worker: Mapped["Worker | None"] = relationship(back_populates="user", uselist=False)
    hiring_party: Mapped["HiringParty | None"] = relationship(back_populates="user", uselist=False)

    # One-to-many
    kyc_records: Mapped[list["KYC"]] = relationship(back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")
    sent_messages: Mapped[list["Message"]] = relationship(
        back_populates="sender", foreign_keys="Message.sender_id"
    )
    received_messages: Mapped[list["Message"]] = relationship(
        back_populates="receiver", foreign_keys="Message.receiver_id"
    )
    ratings_given: Mapped[list["Rating"]] = relationship(
        back_populates="from_user", foreign_keys="Rating.from_user_id"
    )
    ratings_received: Mapped[list["Rating"]] = relationship(
        back_populates="to_user", foreign_keys="Rating.to_user_id"
    )
    disputes_raised: Mapped[list["Dispute"]] = relationship(back_populates="raised_by_user")
    device_tokens: Mapped[list["DeviceToken"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id!r}, phone={self.phone!r}, role={self.role!r})"
