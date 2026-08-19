"""Data access for COMPLETION_VERIFICATION.

Source: app/models/completion_verification.py, docs/database-design.md Section 1.12.
"""

import uuid

from sqlalchemy import select

from app.models.completion_verification import CompletionVerification
from app.repositories.base import BaseRepository


class CompletionVerificationRepository(BaseRepository[CompletionVerification]):
    model = CompletionVerification

    async def get_by_job(self, job_id: uuid.UUID) -> CompletionVerification | None:
        result = await self.session.execute(
            select(CompletionVerification).where(CompletionVerification.job_id == job_id)
        )
        return result.scalar_one_or_none()
