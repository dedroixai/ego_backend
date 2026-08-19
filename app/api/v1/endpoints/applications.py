"""Job Application API (worker-facing + shared endpoints).

    Route -> Pydantic Schema -> JobMatchService -> JobMatchRepository -> SQLAlchemy -> Supabase

"Application" is Task 12's product-facing term for the same `JOB_MATCH`
entity used since Task 5 (docs/application-api.md documents this naming
bridge, matching the precedent already set for "Business"/"HiringParty").

`GET /applications/{application_id}` uses `get_current_user` (not
`get_current_worker`/`get_current_business`) since either a worker OR a
business may be the legitimate viewer, depending on which one they are for
THIS specific application - `JobMatchService.get_application_for_viewer`
decides which, not the dependency layer. Every other route here is
worker-only. Business-side application management
(`GET /jobs/{job_id}/applications`, review/accept/reject) lives in
app/api/v1/endpoints/jobs.py and here respectively - see below.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DBSession
from app.auth.dependencies import get_current_business, get_current_user, get_current_worker
from app.models.business import HiringParty
from app.models.job_match import JobMatch
from app.models.user import User
from app.models.worker import Worker
from app.schemas.job_match import JobMatchResponse, JobMatchUpdate, JobMatchWithWorkerResponse
from app.services.job_match_service import JobMatchService

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/me", response_model=list[JobMatchResponse])
async def list_my_applications(
    worker: Annotated[Worker, Depends(get_current_worker)],
    session: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobMatch]:
    applications = await JobMatchService(session).list_for_worker(worker.user_id, limit=limit, offset=offset)
    return list(applications)


@router.get("/{application_id}", response_model=JobMatchWithWorkerResponse)
async def read_application(
    application_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> JobMatch:
    """Visible to the applicant (worker) or the owning business - anyone
    else gets 403 (Step 8: "do not expose applications to unrelated users").
    Returns `JobMatchWithWorkerResponse` (Task 19) - harmless when the
    viewer is the applicant themselves (it's just their own summary), and
    what a business viewer needs to see who they're reviewing."""
    return await JobMatchService(session).get_application_for_viewer(application_id, current_user.user_id)


@router.delete("/{application_id}", response_model=JobMatchResponse)
async def withdraw_application(
    application_id: uuid.UUID,
    worker: Annotated[Worker, Depends(get_current_worker)],
    session: DBSession,
) -> JobMatch:
    """Worker-only, own application only. Not a physical delete - the row
    is kept with `status="withdrawn"` (application history is preserved,
    matching how Task 11 handled Job "deletion" - see docs/job-lifecycle.md
    and docs/application-api.md)."""
    return await JobMatchService(session).withdraw_application(application_id, worker.user_id)


@router.patch("/{application_id}", response_model=JobMatchResponse)
async def review_application(
    application_id: uuid.UUID,
    payload: JobMatchUpdate,
    business: Annotated[HiringParty, Depends(get_current_business)],
    session: DBSession,
) -> JobMatch:
    """Business-only, and only for applications to a job that business
    owns (checked inside the service - JobMatchService.review_application).
    `payload.status` must be "accepted" or "rejected" - see
    docs/application-api.md for the full transition table."""
    return await JobMatchService(session).review_application(
        application_id, business.user_id, status=payload.status
    )
