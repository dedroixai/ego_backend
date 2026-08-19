"""API schemas for HIRING_PARTY.

Source: app/models/business.py, docs/database-design.md Section 1.3.

`rating` and `verified_badge` are server/aggregate-controlled (see
docs/database-design.md Section 7.6) and excluded from Create/Update.
`verification_level` is likewise excluded - it is assigned through a
verification process, not self-declared by the client.

`user_id` is intentionally excluded from Create/Update for the same reason
as `Worker` - see app/schemas/worker.py.

`profile_image_url` (Task 20) - see app/schemas/worker.py's identical
field for the full rationale (a Firebase Storage download URL, set by the
client only after a successful Storage upload; ownership is inherent
since this endpoint only ever writes to the authenticated business's own
profile).
"""

import uuid
from decimal import Decimal

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class HiringPartyCreate(RequestModel):
    account_type: str = Field(min_length=1, max_length=20)
    business_name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    profile_image_url: str | None = Field(default=None, max_length=2048)


class HiringPartyUpdate(RequestModel):
    account_type: str | None = Field(default=None, min_length=1, max_length=20)
    business_name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    profile_image_url: str | None = Field(default=None, max_length=2048)


class HiringPartyResponse(ORMModel):
    user_id: uuid.UUID
    account_type: str
    business_name: str | None
    address: str | None
    rating: Decimal | None
    verification_level: str | None
    verified_badge: bool
    profile_image_url: str | None


class HiringPartySummary(ORMModel):
    """Lighter shape for list views (e.g. shown alongside a job posting)."""

    user_id: uuid.UUID
    business_name: str | None
    rating: Decimal | None
    verified_badge: bool
