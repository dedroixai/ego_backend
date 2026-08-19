"""KYC entity - an individual KYC document submission for a user.

Source: diagrams/er_diagram.mermaid (KYC), docs/database-design.md Section 1.11.

Deviation: `documentNumber` and `verifiedAt` (class diagram only) are NOT
implemented - see docs/database-design.md Section 7.8 and
docs/model-implementation.md. `documentNumber` is also flagged there as
sensitive PII that would need protection if added later.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class KYC(Base):
    __tablename__ = "kyc"

    kyc_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )

    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    user: Mapped["User"] = relationship(back_populates="kyc_records")

    def __repr__(self) -> str:
        return f"KYC(kyc_id={self.kyc_id!r}, user_id={self.user_id!r}, status={self.status!r})"
