"""Notification API (Task 21 Step 14) - notification HISTORY, i.e. the
persisted `Notification` rows `NotificationService.notify` creates as a
side effect of a push (see app/services/notification_service.py). This is
NOT how push delivery itself works (that's Firebase Cloud Messaging,
already fired by the time these rows exist) - this is what backs an
in-app `/notifications` screen so a user can see what they already
missed/read.

    Route -> Pydantic Schema -> NotificationService -> NotificationRepository -> SQLAlchemy -> Supabase

`NotificationService` (list_for_user/mark_read/dismiss) already existed
before this task (an earlier task built the service/repository layer but
explicitly deferred both creation logic and route exposure - see that
service's own module docstring) - this file is the first thing that
actually wires it to the API, the same "expose an already-built,
already-correct capability" pattern as Task 18's `GET /jobs/me` and
Task 19's worker-summary enrichment.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession
from app.auth.dependencies import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationUpdate
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_my_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Notification]:
    notifications = await NotificationService(session).list_for_user(
        current_user.user_id, current_user.user_id, unread_only=unread_only, limit=limit, offset=offset
    )
    return list(notifications)


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: uuid.UUID,
    payload: NotificationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> Notification:
    """Own notifications only - enforced inside `NotificationService`
    (403 for anyone else's), the same ownership shape as every other
    per-resource endpoint in this API."""
    return await NotificationService(session).mark_read(
        notification_id, current_user.user_id, is_read=payload.is_read
    )


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_notification(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> None:
    await NotificationService(session).dismiss(notification_id, current_user.user_id)
