"""DISPUTE entity - a dispute raised about a job.

Source: diagrams/er_diagram.mermaid (DISPUTE), docs/database-design.md Section 1.15.

Deviation: `reason` and `resolution` (class diagram only) are NOT
implemented - see docs/database-design.md Section 7.8 and
docs/model-implementation.md.

Important: `job_id` is nullable here because the ER diagram draws
`JOB |o--o| DISPUTE` as optional on both sides, which - per the derivation
rule in docs/database-design.md Section 2 - implies a dispute is not
required to reference a job. This is flagged as counter-intuitive and
UNRESOLVED in docs/database-design.md Section 7.14; implemented literally
per the diagram rather than "fixed" silently. Confirm before relying on
this in application code.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


class Dispute(Base):
    __tablename__ = "disputes"

    dispute_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=True, index=True
    )
    raised_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")

    job: Mapped["Job | None"] = relationship(back_populates="dispute")
    raised_by_user: Mapped["User"] = relationship(back_populates="disputes_raised")

    def __repr__(self) -> str:
        return f"Dispute(dispute_id={self.dispute_id!r}, job_id={self.job_id!r}, status={self.status!r})"
