"""WITHDRAWAL entity - a worker's request to withdraw earnings.

Source: diagrams/er_diagram.mermaid (WITHDRAWAL), docs/database-design.md Section 1.9.

Deviation: `type` (class diagram only) is NOT implemented - see
docs/database-design.md Section 7.8 and docs/model-implementation.md.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.worker import Worker


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    withdrawal_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workers.user_id"), nullable=False, index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    worker: Mapped["Worker"] = relationship(back_populates="withdrawals")

    def __repr__(self) -> str:
        return f"Withdrawal(withdrawal_id={self.withdrawal_id!r}, worker_id={self.worker_id!r}, amount={self.amount!r})"
