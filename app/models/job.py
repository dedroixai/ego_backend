"""JOB entity - a job posting created by a hiring party.

Source: diagrams/er_diagram.mermaid (JOB), docs/database-design.md Section 1.5.

Deviation: `videos` (class diagram only) is NOT implemented - see
docs/database-design.md Section 7.8 and docs/model-implementation.md.
`image_url` (single photo, not the class diagram's plural `images`) WAS
later added on explicit product request (job details redesign), following
the same "adopt provisionally, flag clearly" precedent already used for
`Worker.profile_image_url`/`HiringParty.profile_image_url` - a Firebase
Storage download URL, never the image binary itself. Single image, not a
list: matches the scope actually requested and keeps the write path
identical to the existing profile-image upload flow (one file in, one URL
out) rather than inventing a multi-image gallery feature nothing asked for.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.business import HiringParty
    from app.models.completion_verification import CompletionVerification
    from app.models.dispute import Dispute
    from app.models.job_category import JobCategory
    from app.models.job_match import JobMatch
    from app.models.message import Message
    from app.models.payment import Payment
    from app.models.rating import Rating


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hiring_party_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hiring_parties.user_id"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("job_categories.category_id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    hiring_party: Mapped["HiringParty"] = relationship(back_populates="jobs")
    category: Mapped["JobCategory"] = relationship(back_populates="jobs")
    matches: Mapped[list["JobMatch"]] = relationship(back_populates="job")
    messages: Mapped[list["Message"]] = relationship(back_populates="job")
    payment: Mapped["Payment | None"] = relationship(back_populates="job", uselist=False)
    completion_verification: Mapped["CompletionVerification | None"] = relationship(
        back_populates="job", uselist=False
    )
    ratings: Mapped[list["Rating"]] = relationship(back_populates="job")
    dispute: Mapped["Dispute | None"] = relationship(back_populates="job", uselist=False)

    def __repr__(self) -> str:
        return f"Job(job_id={self.job_id!r}, title={self.title!r}, status={self.status!r})"
