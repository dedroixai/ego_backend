"""JOB_CATEGORY entity - lookup table for job categories.

Source: diagrams/er_diagram.mermaid (JOB_CATEGORY), docs/database-design.md Section 1.4.

Deviation: `customFields` (class diagram only) is NOT implemented - see
docs/database-design.md Section 7.8 and docs/model-implementation.md.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class JobCategory(Base):
    __tablename__ = "job_categories"

    category_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    jobs: Mapped[list["Job"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"JobCategory(category_id={self.category_id!r}, name={self.name!r})"
