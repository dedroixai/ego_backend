"""COMPLETION_VERIFICATION entity - how a job's completion was verified.

Mandatory one-to-one with JOB.

Source: diagrams/er_diagram.mermaid (COMPLETION_VERIFICATION),
docs/database-design.md Section 1.12.

Deviation: `otpCode` and `verifiedAt` (class diagram only) are NOT
implemented - see docs/database-design.md Section 7.8 and
docs/model-implementation.md.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class CompletionVerification(Base):
    __tablename__ = "completion_verifications"

    verification_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # UNIQUE enforces the diagrammed mandatory one-to-one with JOB.
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=False, unique=True
    )

    method: Mapped[str] = mapped_column(String(20), nullable=False)
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hiring_party_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    job: Mapped["Job"] = relationship(back_populates="completion_verification")

    def __repr__(self) -> str:
        return f"CompletionVerification(verification_id={self.verification_id!r}, job_id={self.job_id!r})"
