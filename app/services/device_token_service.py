"""Business logic for DEVICE_TOKEN (Task 21).

Source: app/models/device_token.py, docs/notifications.md.

`register` is an upsert, not a plain create - Step 5 ("token refresh")
and the simple "app launches, re-sends its current token every time"
pattern both mean the SAME token value can arrive more than once. If the
token already exists (regardless of which user it was previously
attached to - a device can be signed into a different EGO account than
before, e.g. after a logout/login as someone else on the same physical
phone), it's reassigned to the current requester rather than rejected as
a duplicate; if not, a new row is created. Either way the end state is
exactly one row for this token, owned by whoever is registering it now -
never two rows for the same physical device.
"""

import uuid

from app.models.device_token import DeviceToken
from app.repositories.device_token_repository import DeviceTokenRepository
from app.repositories.exceptions import RepositoryError
from app.services.base import BaseService


class DeviceTokenService(BaseService):
    def __init__(self, session) -> None:  # noqa: ANN001
        super().__init__(session)
        self._tokens = DeviceTokenRepository(session)

    async def register(self, user_id: uuid.UUID, *, token: str, platform: str) -> DeviceToken:
        existing = await self._tokens.get_by_token(token)
        try:
            if existing is not None:
                updated = await self._tokens.update(existing, user_id=user_id, platform=platform)
            else:
                updated = await self._tokens.create(user_id=user_id, token=token, platform=platform)
        except RepositoryError as exc:
            await self._rollback_and_raise(exc)
        await self._commit()
        return updated
