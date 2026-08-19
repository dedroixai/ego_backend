"""HIRING_PARTY entity - hiring-party-specific profile, one-to-one extension of USER.

Source: diagrams/er_diagram.mermaid (HIRING_PARTY), docs/database-design.md Section 1.3.

`profile_image_url` (Task 20) - see app/models/worker.py's identical field
for the full rationale (present in neither diagram, added on this task's
explicit instruction, documented in docs/storage-architecture.md). Used
for a business's logo/profile image, same architecture as Worker's.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.connection import Connection
    from app.models.job import Job
    from app.models.user import User


class HiringParty(Base):
    __tablename__ = "hiring_parties"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True
    )

    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # See app/models/worker.py's `rating` comment - scale-2 default matches
    # Postgres's Numeric(3, 2) round-trip formatting.
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True, default=Decimal("0.00"))
    verification_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    verified_badge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profile_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    user: Mapped["User"] = relationship(back_populates="hiring_party")
    jobs: Mapped[list["Job"]] = relationship(back_populates="hiring_party")
    connections: Mapped[list["Connection"]] = relationship(back_populates="hiring_party")

    def __repr__(self) -> str:
        return f"HiringParty(user_id={self.user_id!r}, business_name={self.business_name!r})"
