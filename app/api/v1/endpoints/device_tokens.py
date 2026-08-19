"""Device Token API (Task 21) - registers a Firebase Cloud Messaging token
for the authenticated user.

    Route -> Pydantic Schema -> DeviceTokenService -> DeviceTokenRepository -> SQLAlchemy -> Supabase

Uses `get_current_user` (any authenticated EGO user, not
`get_current_worker`/`get_current_business`) - registering a device for
push notifications isn't Worker/Business-specific, matching
`users.py`'s `GET/PATCH /users/me` treatment.

One route only: registering IS the upsert (Step 5's "token refresh" is
just calling this again with the new token value - see
`DeviceTokenService.register`'s doc comment). No `GET`/`DELETE` here -
nothing in this task's instructions asks a client to list or deregister
its own tokens, and inventing that isn't needed for push notifications to
work (Step 15's cleanup is a backend-internal action, not a client-facing
endpoint).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DBSession
from app.auth.dependencies import get_current_user
from app.models.device_token import DeviceToken
from app.models.user import User
from app.schemas.device_token import DeviceTokenRegister, DeviceTokenResponse
from app.services.device_token_service import DeviceTokenService

router = APIRouter(prefix="/device-tokens", tags=["device-tokens"])


@router.post("", response_model=DeviceTokenResponse, status_code=status.HTTP_201_CREATED)
async def register_device_token(
    payload: DeviceTokenRegister,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> DeviceToken:
    return await DeviceTokenService(session).register(
        current_user.user_id, token=payload.token, platform=payload.platform
    )
