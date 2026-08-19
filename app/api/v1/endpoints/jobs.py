"""Job Management API.

    Route -> Pydantic Schema -> JobService -> JobRepository -> SQLAlchemy -> Supabase

Public: `GET /jobs` (listing), `GET /jobs/{job_id}` (detail) - no
authentication at all, matching the product flow's public dashboard.

Protected: `POST /jobs`, `PATCH /jobs/{job_id}` - both depend on
`get_current_business` (Task 10), not `get_current_user`: ownership is
derived as Firebase UID -> EGO User -> Business Profile -> Job, exactly as
Task 11 specifies. A worker (or any user without a Business profile) is
rejected with 403 before ever reaching the service layer. `business.user_id`
becomes the job's `hiring_party_id` - never accepted from the client.

No `DELETE` endpoint - see docs/job-lifecycle.md for why (nothing in the
existing design supports removing a Job row; lifecycle is status-based).

## `GET /jobs/me` (Task 18 - Flutter "My Jobs")

Added because the Flutter Business flow needs "jobs I posted" and no such
endpoint existed - `JobService.list_by_hiring_party` (and its repository
method) have existed since Task 7 but were never wired to a route. This
is a pure exposure of that already-built, already-tested capability via a
properly-scoped route (`get_current_business`, never a client-supplied
`hiring_party_id`) - no new business logic, no schema change. Registered
*before* `GET /{job_id}` in this file specifically because `job_id` is
typed `uuid.UUID`: if `/{job_id}` were registered first, a request to
`/jobs/me` would match that route's pattern first and fail UUID parsing
with a `422` before ever reaching this one - a well-known FastAPI/Starlette
static-vs-dynamic-path-segment ordering pitfall.

## Job Applications (Task 12)

`POST /jobs/{job_id}/applications` and `GET /jobs/{job_id}/applications`
live here (not in app/api/v1/endpoints/applications.py) because they're
scoped by job, matching this router's existing `/jobs/{job_id}` prefix.
"Application" is Task 12's product-facing term for the same `JOB_MATCH`
entity used since Task 5 - see app/services/job_match_service.py.

`GET /jobs/{job_id}/applications` returns `JobMatchWithWorkerResponse`
(Task 19 - see app/schemas/job_match.py's doc comment), not the plain
`JobMatchResponse` `POST` returns - a business reviewing applicants needs
to see who they are, not just an opaque `worker_id`.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession
from app.auth.dependencies import get_current_business, get_current_worker
from app.models.business import HiringParty
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.worker import Worker
from app.schemas.job import JobCreate, JobListResponse, JobPatchRequest, JobResponse
from app.schemas.job_match import JobMatchResponse, JobMatchWithWorkerResponse
from app.services.job_match_service import JobMatchService
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobListResponse])
async def list_jobs(
    session: DBSession,
    category_id: uuid.UUID | None = None,
    location: str | None = None,
    search: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Job]:
    """Public - powers the dashboard's job browsing. Defaults to `status=open`
    (see JobService.list_public_jobs); `search` is a plain title
    substring match, not ranked/fuzzy search."""
    jobs = await JobService(session).list_public_jobs(
        status=status_filter, category_id=category_id, location=location, search=search, limit=limit, offset=offset
    )
    return list(jobs)


@router.get("/me", response_model=list[JobListResponse])
async def list_my_jobs(
    business: Annotated[HiringParty, Depends(get_current_business)],
    session: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Job]:
    """Business-only. Every job the authenticated business posted,
    regardless of status (draft/open/closed) - unlike the public listing,
    which defaults to `status=open` only. Ownership is derived the same
    way every other business-scoped endpoint here derives it -
    `business.user_id` from `get_current_business`, never a client-supplied
    ID (Step 6/11's "must NOT be manually entered or trusted from
    Flutter")."""
    jobs = await JobService(session).list_by_hiring_party(business.user_id, limit=limit, offset=offset)
    return list(jobs)


@router.get("/{job_id}", response_model=JobResponse)
async def read_job(job_id: uuid.UUID, session: DBSession) -> Job:
    """Public - job detail view. Returns any job regardless of status (a
    direct-ID lookup, unlike the listing default) - 404 if it doesn't exist."""
    return await JobService(session).get_job(job_id)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    business: Annotated[HiringParty, Depends(get_current_business)],
    session: DBSession,
) -> Job:
    return await JobService(session).create_job(
        business.user_id,
        business.user_id,
        **payload.model_dump(),
    )


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: uuid.UUID,
    payload: JobPatchRequest,
    business: Annotated[HiringParty, Depends(get_current_business)],
    session: DBSession,
) -> Job:
    service = JobService(session)
    data = payload.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)

    # Always route through update_job (even with an empty `data`), since it
    # performs the ownership check (requester_id == job.hiring_party_id).
    # A prior version skipped straight to an unauthenticated-equivalent
    # `get_job` when the body had no updatable fields, letting a non-owner
    # business bypass the 403 with an empty PATCH `{}` - found during the
    # Task 13 audit and fixed here.
    job = await service.update_job(job_id, business.user_id, **data)
    if new_status is not None:
        job = await service.update_status(job_id, business.user_id, status=new_status)
    return job


@router.post(
    "/{job_id}/applications", response_model=JobMatchResponse, status_code=status.HTTP_201_CREATED
)
async def apply_to_job(
    job_id: uuid.UUID,
    worker: Annotated[Worker, Depends(get_current_worker)],
    session: DBSession,
) -> JobMatch:
    """Worker-only. No request body - the job comes from the URL, the
    applicant is derived from the authenticated Worker profile, and the
    status is always "pending" at creation (see docs/application-api.md)."""
    return await JobMatchService(session).apply_to_job(job_id, worker.user_id, worker.user_id)


@router.get("/{job_id}/applications", response_model=list[JobMatchWithWorkerResponse])
async def list_job_applications(
    job_id: uuid.UUID,
    business: Annotated[HiringParty, Depends(get_current_business)],
    session: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobMatch]:
    """Business-owner-only - only applications for a job this business posted."""
    applications = await JobMatchService(session).list_applications_for_job(
        job_id, business.user_id, limit=limit, offset=offset
    )
    return list(applications)
