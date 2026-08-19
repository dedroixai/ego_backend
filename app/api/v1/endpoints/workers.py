"""Worker Profile API.

    Route -> Pydantic Schema -> WorkerService -> WorkerRepository -> SQLAlchemy -> Supabase

Uses `get_current_user` (Task 8/9) for authentication - not
`get_current_worker` (Task 10): these endpoints are how a user GETS a
Worker profile in the first place (`POST`) or manages their own
possibly-not-yet-existing one (`GET`/`PATCH`), so requiring one to already
exist would be self-defeating. Ownership is enforced inside
`WorkerService` itself (`requester_id == user_id`, Task 7) - the
authenticated user can only ever act on their own profile; a `user_id`
is never accepted from the client. See docs/user-role-architecture.md.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.worker import Worker
from app.schemas.worker import WorkerCreate, WorkerListResponse, WorkerResponse, WorkerUpdate
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=list[WorkerListResponse])
async def list_workers(
    session: DBSession,
    location: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Worker]:
    """Public - powers the business dashboard's "nearby workers"
    browsing (mirrors `GET /api/v1/jobs`'s public listing exactly, same
    "no auth, no complex search/ranking" shape). Registered before `/me`
    would ever matter here - unlike jobs.py, there's no `/{worker_id}`
    dynamic route in this file to accidentally shadow."""
    workers = await WorkerService(session).list_public_workers(location=location, search=search, limit=limit, offset=offset)
    return list(workers)


@router.get("/me", response_model=WorkerResponse)
async def read_current_worker_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> Worker:
    return await WorkerService(session).get_profile(current_user.user_id)


@router.post("/me", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
async def create_current_worker_profile(
    payload: WorkerCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> Worker:
    return await WorkerService(session).create_profile(
        current_user.user_id,
        current_user.user_id,
        **payload.model_dump(),
    )


@router.patch("/me", response_model=WorkerResponse)
async def update_current_worker_profile(
    payload: WorkerUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> Worker:
    return await WorkerService(session).update_profile(
        current_user.user_id,
        current_user.user_id,
        **payload.model_dump(exclude_unset=True),
    )
