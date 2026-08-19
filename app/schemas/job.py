"""API schemas for JOB.

Source: app/models/job.py, docs/database-design.md Section 1.5.

`hiring_party_id` is an ownership field - excluded from every write
schema; derived server-side from the authenticated business profile
(`get_current_business`, Task 10) - see app/api/v1/endpoints/jobs.py.

`status` is excluded from `JobCreate` (every new job starts as `"draft"`,
set by the service, never client-chosen - see app/services/job_service.py)
and from `JobUpdate` (content-field edits are a different concern from a
lifecycle transition). It's `Optional` on `JobPatchRequest` specifically -
Task 11 doesn't define a separate status-change endpoint, so
`PATCH /api/v1/jobs/{job_id}` accepts both concerns in one request body,
each still routed to its own service method
(`JobService.update_job`/`update_status`) internally. See
docs/job-lifecycle.md for the adopted status vocabulary and why it's
flagged as provisional rather than diagram-confirmed.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class JobCreate(RequestModel):
    category_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    budget: Decimal = Field(ge=0)
    duration: str | None = Field(default=None, max_length=100)
    location: str = Field(min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2048)


class JobUpdate(RequestModel):
    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    budget: Decimal | None = Field(default=None, ge=0)
    duration: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=500)
    image_url: str | None = Field(default=None, max_length=2048)


class JobPatchRequest(JobUpdate):
    """Request body for `PATCH /api/v1/jobs/{job_id}` - all `JobUpdate`
    fields plus an optional lifecycle `status` transition."""

    status: str | None = Field(default=None, min_length=1, max_length=30)


class JobResponse(ORMModel):
    job_id: uuid.UUID
    hiring_party_id: uuid.UUID
    category_id: uuid.UUID
    title: str
    description: str
    budget: Decimal
    duration: str | None
    status: str
    location: str
    image_url: str | None
    created_at: datetime


class JobListResponse(ORMModel):
    """Lighter shape for browse/search results - drops the free-text description."""

    job_id: uuid.UUID
    hiring_party_id: uuid.UUID
    category_id: uuid.UUID
    title: str
    budget: Decimal
    status: str
    location: str
    image_url: str | None
    created_at: datetime
