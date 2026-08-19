"""Chat/Messaging API.

    Route -> Pydantic Schema -> MessageService -> MessageRepository -> SQLAlchemy -> Supabase

All three routes use `get_current_user` (not `get_current_worker`/
`get_current_business`) - either kind of user can send/read messages, and
which specific thread a request can see is scoped by the authenticated
user's own ID, never a client-supplied one (`sender_id`/`requester_id`
always come from `current_user`, matching every other "derive identity
server-side" endpoint in this app).

No `DELETE`/`PATCH` - messages aren't editable/removable (see
app/repositories/message_repository.py's module docstring).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DBSession
from app.auth.dependencies import get_current_user
from app.models.message import Message
from app.models.user import User
from app.schemas.message import ConversationSummary, MessageCreate, MessageResponse
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageResponse, status_code=201)
async def send_message(
    payload: MessageCreate, current_user: Annotated[User, Depends(get_current_user)], session: DBSession
) -> Message:
    """`sender_id` is always `current_user` - never accepted from the
    client. See `MessageService.send_message`'s docstring for the
    job-scoped-vs-job-less authorization rule."""
    return await MessageService(session).send_message(
        current_user.user_id, payload.receiver_id, payload.content, job_id=payload.job_id
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)], session: DBSession
) -> list[dict]:
    """The inbox/thread-list view - every distinct (counterpart, job)
    conversation this user has, most-recently-active first."""
    return await MessageService(session).list_conversations(current_user.user_id)


@router.get("/thread/{other_user_id}", response_model=list[MessageResponse])
async def read_thread(
    other_user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
    job_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Message]:
    """One conversation with `other_user_id` - pass `job_id` for that
    job's thread, omit it for the general (job-less) thread with this
    person; these are separate conversations (see
    app/models/message.py's doc comment). Inherently scoped to
    `current_user` - there is no way to pass someone else's ID and read
    their thread, since the query only ever matches messages between
    `current_user` and `other_user_id`."""
    return await MessageService(session).list_thread(
        current_user.user_id, other_user_id, job_id=job_id, limit=limit, offset=offset
    )
