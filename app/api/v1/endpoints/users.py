"""User/Profile API - the first complete vertical slice through the
architecture:

    Route -> Pydantic Schema -> Service -> Repository -> SQLAlchemy -> Supabase

Both endpoints depend on `get_current_user` (app/auth/dependencies.py):
the authenticated Firebase identity determines which EGO user is acted on
- the client can never supply a user ID. See docs/user-api.md.

Supersedes the temporary `GET /api/v1/auth/me` from the previous task
(Step 8 there explicitly called it "temporary") - `GET /api/v1/users/me`
is the permanent, canonical endpoint for this now; the old route was
removed to avoid duplicating identical functionality (Step 1 of this task).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DBSession
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> User:
    service = UserService(session)
    return await service.update_profile(
        current_user.user_id,
        current_user.user_id,
        **payload.model_dump(exclude_unset=True),
    )
