"""API schemas for DEVICE_TOKEN (Task 21).

Source: app/models/device_token.py, docs/notifications.md.

No `user_id` field on `DeviceTokenRegister` - same reasoning as every
other write schema in this project (`WorkerCreate`, `JobCreate`, ...):
ownership is derived server-side from the authenticated Firebase user,
never accepted from the client (Step 4: "Do NOT allow Flutter to submit
an arbitrary user_id").
"""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class DeviceTokenRegister(RequestModel):
    token: str = Field(min_length=1, max_length=4096)
    platform: str = Field(min_length=1, max_length=20)


class DeviceTokenResponse(ORMModel):
    device_token_id: uuid.UUID
    user_id: uuid.UUID
    token: str
    platform: str
    created_at: datetime
    updated_at: datetime
