"""Data access for PAYMENT.

Source: app/models/payment.py, docs/database-design.md Section 1.8.

`create`/`update` remain available via the inherited base methods for a
future financial service process (out of scope here - "do not implement
business logic") - there is no client-facing Create/Update schema for
Payment (see docs/api-schema-design.md).
"""

import uuid

from sqlalchemy import select

from app.models.payment import Payment
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    async def get_by_job(self, job_id: uuid.UUID) -> Payment | None:
        result = await self.session.execute(select(Payment).where(Payment.job_id == job_id))
        return result.scalar_one_or_none()
