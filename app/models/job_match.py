"""JOB_MATCH entity - a candidate match between a job and a worker.

Source: diagrams/er_diagram.mermaid (JOB_MATCH), docs/database-design.md Section 1.6.

Deviation: no uniqueness constraint on (job_id, worker_id) - the design
document flags this as only "possibly" intended, not confirmed. See
docs/database-design.md Section 7.11 and docs/model-implementation.md.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.worker import Worker


class JobMatch(Base):
    __tablename__ = "job_matches"

    match_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=False, index=True
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workers.user_id"), nullable=False, index=True
    )

    # Scale (0-1? 0-100?) is undefined - see docs/database-design.md Section 7.10.
    match_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)

    job: Mapped["Job"] = relationship(back_populates="matches")
    worker: Mapped["Worker"] = relationship(back_populates="matches")

    def __repr__(self) -> str:
        return f"JobMatch(match_id={self.match_id!r}, job_id={self.job_id!r}, worker_id={self.worker_id!r})"
