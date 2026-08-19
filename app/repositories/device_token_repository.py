"""Data access for DEVICE_TOKEN (Task 21).

`get_by_token` backs the upsert semantics in `DeviceTokenService.register` -
`token` is unique (the model's own constraint), so re-registering the same
device (a fresh app launch, or a token-refresh event re-sending the SAME
value) must update the existing row, not violate the unique constraint by
inserting a duplicate.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.device_token import DeviceToken
from app.repositories.base import BaseRepository


class DeviceTokenRepository(BaseRepository[DeviceToken]):
    model = DeviceToken

    async def get_by_token(self, token: str) -> DeviceToken | None:
        result = await self.session.execute(select(DeviceToken).where(DeviceToken.token == token))
        return result.scalars().first()

    async def list_by_user(self, user_id: uuid.UUID) -> Sequence[DeviceToken]:
        result = await self.session.execute(select(DeviceToken).where(DeviceToken.user_id == user_id))
        return result.scalars().all()

    async def delete_by_token(self, token: str) -> None:
        """Step 15 - invalid-token cleanup removes ONLY this one token,
        never every token belonging to its user."""
        existing = await self.get_by_token(token)
        if existing is not None:
            await self.delete(existing)
