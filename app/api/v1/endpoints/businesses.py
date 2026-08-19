"""Business (HiringParty) Profile API.

    Route -> Pydantic Schema -> HiringPartyService -> HiringPartyRepository -> SQLAlchemy -> Supabase

Mirrors app/api/v1/endpoints/workers.py exactly - same reasoning for using
`get_current_user` rather than `get_current_business` here (see that
file's docstring). Ownership enforced inside `HiringPartyService`
(`requester_id == user_id`, Task 7); `user_id` is never accepted from the
client. See docs/user-role-architecture.md.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DBSession
from app.auth.dependencies import get_current_user
from app.models.business import HiringParty
from app.models.user import User
from app.schemas.business import HiringPartyCreate, HiringPartyResponse, HiringPartyUpdate
from app.services.business_service import HiringPartyService

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("/me", response_model=HiringPartyResponse)
async def read_current_business_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> HiringParty:
    return await HiringPartyService(session).get_profile(current_user.user_id)


@router.post("/me", response_model=HiringPartyResponse, status_code=status.HTTP_201_CREATED)
async def create_current_business_profile(
    payload: HiringPartyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> HiringParty:
    return await HiringPartyService(session).create_profile(
        current_user.user_id,
        current_user.user_id,
        **payload.model_dump(),
    )


@router.patch("/me", response_model=HiringPartyResponse)
async def update_current_business_profile(
    payload: HiringPartyUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> HiringParty:
    return await HiringPartyService(session).update_profile(
        current_user.user_id,
        current_user.user_id,
        **payload.model_dump(exclude_unset=True),
    )
