"""RATING entity - a rating/review left by one user for another, in the context of a job.

Source: diagrams/er_diagram.mermaid (RATING), docs/database-design.md Section 1.10.

Deviation: `createdAt` (class diagram only) is NOT implemented - see
docs/database-design.md Section 7.8 and docs/model-implementation.md.

Note: `fromUserId`/`toUserId` have no drawn relationship lines in the ER
diagram - implemented as NOT NULL per the design document's recommendation.
See docs/database-design.md Section 7.12. No CHECK constraint on `score`'s
range since the valid range is undefined (Section 7.10).
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


class Rating(Base):
    __tablename__ = "ratings"

    rating_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=False, index=True
    )
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )

    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="ratings")
    # Two FKs to USER on this table - foreign_keys= disambiguates which
    # column each relationship uses.
    from_user: Mapped["User"] = relationship(back_populates="ratings_given", foreign_keys=[from_user_id])
    to_user: Mapped["User"] = relationship(back_populates="ratings_received", foreign_keys=[to_user_id])

    def __repr__(self) -> str:
        return f"Rating(rating_id={self.rating_id!r}, job_id={self.job_id!r}, score={self.score!r})"
