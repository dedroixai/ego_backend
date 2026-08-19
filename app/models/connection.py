"""CONNECTION entity - junction resolving the WORKER <-> HIRING_PARTY many-to-many.

Source: diagrams/er_diagram.mermaid (CONNECTION), docs/database-design.md Section 1.13.

Deviation: `lastHiredDate` (class diagram only) is NOT implemented - see
docs/database-design.md Section 7.8 and docs/model-implementation.md.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.business import HiringParty
    from app.models.worker import Worker


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (
        # A connection is conceptually one record per worker/hiring-party
        # pair - not explicitly stated by either diagram but structurally
        # justified by what CONNECTION represents. See
        # docs/database-design.md Section 7.11.
        UniqueConstraint("worker_id", "hiring_party_id", name="uq_connections_worker_hiring_party"),
        CheckConstraint("jobs_completed >= 0", name="jobs_completed_non_negative"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workers.user_id"), nullable=False, index=True
    )
    hiring_party_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hiring_parties.user_id"), nullable=False, index=True
    )

    jobs_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    worker: Mapped["Worker"] = relationship(back_populates="connections")
    hiring_party: Mapped["HiringParty"] = relationship(back_populates="connections")

    def __repr__(self) -> str:
        return (
            f"Connection(connection_id={self.connection_id!r}, "
            f"worker_id={self.worker_id!r}, hiring_party_id={self.hiring_party_id!r})"
        )
