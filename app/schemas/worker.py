"""API schemas for WORKER.

Source: app/models/worker.py, docs/database-design.md Section 1.2.

`rating` and `verified_badge` are server/aggregate-controlled (see
docs/database-design.md Section 7.6) and are excluded from Create/Update -
a worker cannot self-assign a rating or a verified badge.

`bank_details` is flagged as sensitive financial data
(docs/database-design.md Section 7.7) and is excluded from the general
`WorkerResponse`. `WorkerWithBankDetails` is the internal/backend-only
variant that includes it - never return it from a general-purpose endpoint.

`user_id` is intentionally excluded from `WorkerCreate`/`WorkerUpdate` - it
identifies which existing USER this profile belongs to, which is an
ownership concern that belongs in a URL path or auth context in a later
task, not a client-supplied request-body field.

`profile_image_url` (Task 20) - a Firebase Storage download URL, set by
the client only AFTER a successful Storage upload (see
docs/storage-architecture.md's upload flow) - accepted here like any
other profile field because ownership is already enforced the same way
every other Worker field is: this endpoint only ever writes to
`current_user.user_id`'s own profile (app/api/v1/endpoints/workers.py),
never a client-supplied one, so there is no path for setting another
user's image reference through this schema.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import Field, StringConstraints

from app.schemas.base import ORMModel, RequestModel

SkillStr = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]


class WorkerCreate(RequestModel):
    name: str = Field(min_length=1, max_length=255)
    skills: list[SkillStr] = Field(default_factory=list, max_length=50)
    experience: int | None = Field(default=None, ge=0, le=32767)
    expected_wage: Decimal | None = Field(default=None, ge=0)
    availability: str | None = Field(default=None, max_length=30)
    service_locations: list[SkillStr] = Field(default_factory=list, max_length=50)
    bank_details: str | None = Field(default=None, max_length=500)
    profile_image_url: str | None = Field(default=None, max_length=2048)


class WorkerUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    skills: list[SkillStr] | None = Field(default=None, max_length=50)
    experience: int | None = Field(default=None, ge=0, le=32767)
    expected_wage: Decimal | None = Field(default=None, ge=0)
    availability: str | None = Field(default=None, max_length=30)
    service_locations: list[SkillStr] | None = Field(default=None, max_length=50)
    bank_details: str | None = Field(default=None, max_length=500)
    profile_image_url: str | None = Field(default=None, max_length=2048)


class WorkerResponse(ORMModel):
    user_id: uuid.UUID
    name: str
    skills: list[str]
    experience: int | None
    expected_wage: Decimal | None
    availability: str | None
    rating: Decimal | None
    service_locations: list[str]
    verified_badge: bool
    profile_image_url: str | None


class WorkerSummary(ORMModel):
    """Lighter shape for list views (e.g. search/browse results)."""

    user_id: uuid.UUID
    name: str
    skills: list[str]
    rating: Decimal | None
    verified_badge: bool
    availability: str | None


class WorkerListResponse(ORMModel):
    """Public browse/nearby-workers listing shape (`GET /api/v1/workers`) -
    a separate schema from `WorkerSummary` (used for applicant lists,
    a different privacy context - a business already reviewing a real
    application) rather than reusing/extending it, so each schema's
    field set stays scoped to what its own endpoint actually needs.
    Deliberately excludes `bank_details` and `experience`/`availability`
    internals - this is a public listing anyone can hit with no auth at
    all, same exposure level as `JobListResponse`. Includes
    `service_locations`/`expected_wage` (unlike `WorkerSummary`) since
    this listing exists specifically for location/price-based discovery.
    """

    user_id: uuid.UUID
    name: str
    skills: list[str]
    service_locations: list[str]
    expected_wage: Decimal | None
    rating: Decimal | None
    verified_badge: bool
    profile_image_url: str | None


class WorkerWithBankDetails(WorkerResponse):
    """Internal/backend-only - includes sensitive bank details.

    Never return this from a general-purpose API endpoint; only for
    backend processes that legitimately need it (e.g. payout processing).
    """

    bank_details: str | None
