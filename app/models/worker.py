"""WORKER entity - worker-specific profile, one-to-one extension of USER.

Source: diagrams/er_diagram.mermaid (WORKER), docs/database-design.md Section 1.2.

Deviation: `portfolioUrl` (class diagram only, absent from the ER diagram) is
NOT implemented - see docs/database-design.md Section 7.8 and
docs/model-implementation.md.

`profile_image_url` (Task 20) - present in NEITHER diagram (a step further
than `portfolioUrl`, which is at least in one). Added on this task's
explicit instruction ("implement profile images... document as an
equivalent field if one does not already exist"), following the same
"adopt provisionally, flag clearly, don't block on an undiagrammed field"
precedent already used for `Job.status`/application status vocabulary -
see docs/storage-architecture.md for the full reasoning. Stores a Firebase
Storage download URL, never the image binary itself.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.connection import Connection
    from app.models.job_match import JobMatch
    from app.models.user import User
    from app.models.withdrawal import Withdrawal


class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (CheckConstraint("experience >= 0", name="experience_non_negative"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # skills/service_locations: ER diagram types these as plain `string`, class
    # diagram types them as List<String> - implemented as arrays per the
    # design document's recommendation. See docs/database-design.md Section 7.5.
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    experience: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    expected_wage: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    availability: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Numeric(3, 2)'s Postgres round-trip always yields scale-2 ("0.00"); the
    # Python-side default is written the same way so a freshly-created row's
    # response matches a freshly-read row's response (found during the Task
    # 13 audit - the default previously read back as "0" until refreshed).
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True, default=Decimal("0.00"))
    service_locations: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    bank_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_badge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profile_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    user: Mapped["User"] = relationship(back_populates="worker")
    matches: Mapped[list["JobMatch"]] = relationship(back_populates="worker")
    withdrawals: Mapped[list["Withdrawal"]] = relationship(back_populates="worker")
    connections: Mapped[list["Connection"]] = relationship(back_populates="worker")

    def __repr__(self) -> str:
        return f"Worker(user_id={self.user_id!r}, name={self.name!r})"
