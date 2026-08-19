"""Firebase Cloud Messaging delivery (Task 21 Step 8).

    NotificationService.notify() -> PushService.send_to_user()
    -> firebase_admin.messaging -> FCM -> device(s)

This is the ONLY place `firebase_admin.messaging` is imported anywhere in
this codebase - Step 8's "Do NOT put FCM sending logic directly inside...
routers" applies just as much to scattering it across services; every
service that wants to push a notification goes through
`NotificationService.notify`, which is the only caller of this class.

Reuses `app.core.firebase.get_firebase_app()` (Step 1: "Do NOT create
duplicate Firebase initialization") - the exact same `lru_cache`d Admin
SDK app already used for ID-token verification (`app/auth/dependencies.py`).
No new Firebase project, no new credentials, no new settings.

Never raises. Every failure mode here (an individual token being
unregistered, FCM being unreachable, a malformed payload) is caught and
logged, never propagated - Step 18: "Notification delivery failure must
NOT cause the core business operation to fail." A caller that wants to
know whether ANY device actually received the push can inspect the
returned `PushResult`, but nothing here ever raises up into
`NotificationService`/the business-action service that triggered it.
"""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from firebase_admin import messaging

from app.core.firebase import get_firebase_app
from app.models.device_token import DeviceToken
from app.repositories.device_token_repository import DeviceTokenRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushResult:
    attempted: int
    sent: int
    invalid_tokens_removed: int


class PushService:
    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session
        self._tokens = DeviceTokenRepository(session)

    async def send_to_user(
        self,
        user_id: uuid.UUID,
        *,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> PushResult:
        """Fans out to EVERY device this user has registered (Step 16 -
        "a notification should be delivered to both valid devices", not
        just the most-recently-registered one)."""
        tokens = await self._tokens.list_by_user(user_id)
        if not tokens:
            # Not an error - a user with no registered device (never
            # opened the app, or opted out of notifications - Step 6:
            # "the application should remain usable if notifications are
            # disabled") simply has nothing to push to.
            return PushResult(attempted=0, sent=0, invalid_tokens_removed=0)

        try:
            return await self._send(tokens, title=title, body=body, data=data)
        except Exception:
            # Anything unexpected here (FCM unreachable, a library bug) -
            # logged, never raised (Step 18).
            logger.exception("Unexpected error sending push notification to user %s", user_id)
            return PushResult(attempted=len(tokens), sent=0, invalid_tokens_removed=0)

    async def _send(
        self,
        tokens: Sequence[DeviceToken],
        *,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> PushResult:
        messages = [
            messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data,
                token=device_token.token,
            )
            for device_token in tokens
        ]

        try:
            response = messaging.send_each(messages, app=get_firebase_app())
        except Exception:
            logger.exception("FCM send_each failed for %d token(s)", len(tokens))
            return PushResult(attempted=len(tokens), sent=0, invalid_tokens_removed=0)

        invalid_removed = 0
        for device_token, result in zip(tokens, response.responses, strict=True):
            if result.success:
                continue
            error = result.exception
            if isinstance(error, messaging.UnregisteredError):
                # Step 15 - remove ONLY this token, never every token this
                # user has (a stale token on Device A must not affect
                # delivery to Device B).
                await self._tokens.delete_by_token(device_token.token)
                invalid_removed += 1
                logger.info("Removed invalid/unregistered device token for user %s", device_token.user_id)
            else:
                logger.warning(
                    "Push delivery failed for a device token (user %s): %s", device_token.user_id, error
                )

        if invalid_removed:
            await self.session.commit()

        return PushResult(attempted=len(tokens), sent=response.success_count, invalid_tokens_removed=invalid_removed)
