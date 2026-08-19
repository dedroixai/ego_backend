"""API schemas for RATING.

Source: app/models/rating.py, docs/database-design.md Section 1.10.

`from_user_id` is an ownership field - excluded from `RatingCreate`, to be
set server-side from the authenticated user (the rater).

No `RatingUpdate` - neither diagram describes ratings as editable once
submitted.

`score`'s valid range is explicitly undefined project-wide
(docs/database-design.md Section 7.10) - deliberately NOT constrained to a
guessed range like 1-5, consistent with the DB layer's own decision not to
add a CHECK constraint for this exact reason. The only bound applied is the
underlying `SmallInteger` column's storage range, which is a technical
limit (prevents a value the DB would reject), not a business rule.
"""

import uuid

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class RatingCreate(RequestModel):
    job_id: uuid.UUID
    to_user_id: uuid.UUID
    score: int = Field(ge=-32768, le=32767)
    comment: str | None = Field(default=None, max_length=2000)


class RatingResponse(ORMModel):
    rating_id: uuid.UUID
    job_id: uuid.UUID
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    score: int
    comment: str | None
