"""Job Category API - read-only.

    Route -> Pydantic Schema -> JobCategoryService -> JobCategoryRepository -> SQLAlchemy -> Supabase

Added for Task 18 (Flutter Business "Create Job" flow) - `JobCreate`
requires a `category_id`, and there was no way for a client to discover
which categories actually exist. `JobCategoryService.list_categories`
(and its repository/schema) have existed since backend Task 7 but were
never wired to a route - the same situation `GET /jobs/me` was in (see
app/api/v1/endpoints/jobs.py's module docstring).

Public, read-only: categories are shared reference data, not owned by
any user, and every other read-only reference-style lookup in this API
(e.g. the public job listing) is also unauthenticated. No `POST`/`PATCH`/
`DELETE` here - `JobCategoryService`'s own docstring already flags
category management as "Admin-only... deferred - there is no Admin
entity/auth layer yet" (docs/database-design.md Section 7.16) - adding a
public or business-writable category-creation endpoint would invent
authorization the design doesn't define, not just expose an existing
capability.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DBSession
from app.models.job_category import JobCategory
from app.schemas.job_category import JobCategoryResponse
from app.services.job_category_service import JobCategoryService

router = APIRouter(prefix="/job-categories", tags=["job-categories"])


@router.get("", response_model=list[JobCategoryResponse])
async def list_job_categories(
    session: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobCategory]:
    """Public - lets a client (e.g. the Business "Create Job" form) show
    real category names/IDs instead of requiring a raw UUID to be typed
    or guessed."""
    categories = await JobCategoryService(session).list_categories(limit=limit, offset=offset)
    return list(categories)
