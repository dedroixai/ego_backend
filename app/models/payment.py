"""PAYMENT entity - escrow/payment record for a job (mandatory one-to-one with JOB).

Source: diagrams/er_diagram.mermaid (PAYMENT), docs/database-design.md Section 1.8.

Deviation: `paymentMethod` (class diagram only) is NOT implemented - see
docs/database-design.md Section 7.8 and docs/model-implementation.md.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("platform_fee >= 0", name="platform_fee_non_negative"),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # UNIQUE enforces the diagrammed mandatory one-to-one with JOB.
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=False, unique=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    escrow_status: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped["Job"] = relationship(back_populates="payment")

    def __repr__(self) -> str:
        return f"Payment(payment_id={self.payment_id!r}, job_id={self.job_id!r}, amount={self.amount!r})"
