"""FastAPI authentication dependencies.

    Firebase ID Token -> verify -> Firebase UID -> find/create EGO User -> User

`get_current_firebase_user` handles the first half (pure Firebase identity
verification, no database access). `get_current_user` handles the second
half: mapping that identity to an EGO `User` row via `users.firebase_uid`,
auto-provisioning one on first sign-in (see its own docstring) - see
docs/authentication.md "AUTHENTICATION SCHEMA DECISION" for the history of
why this was deliberately deferred until the schema decision was made.
"""

import logging
from typing import Annotated

from fastapi import Depends, Request
from firebase_admin import auth as firebase_auth

from app.api.deps import DBSession
from app.auth.exceptions import (
    BusinessProfileRequiredError,
    ExpiredTokenError,
    InvalidTokenError,
    MalformedAuthorizationHeaderError,
    MissingAuthorizationHeaderError,
    RevokedTokenError,
    UserMappingNotConfiguredError,
    WorkerProfileRequiredError,
)
from app.auth.schemas import FirebaseUser
from app.core.firebase import get_firebase_app
from app.models.business import HiringParty
from app.models.user import User
from app.models.worker import Worker
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.exceptions import DuplicateRecordError
from app.repositories.user_repository import UserRepository
from app.repositories.worker_repository import WorkerRepository

logger = logging.getLogger(__name__)


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise MissingAuthorizationHeaderError()

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise MalformedAuthorizationHeaderError()

    return parts[1].strip()


async def get_current_firebase_user(request: Request) -> FirebaseUser:
    """Verify the request's Firebase ID token and return the caller's
    verified Firebase identity. Never logs the token or the Authorization
    header (Step 9)."""
    token = _extract_bearer_token(request)

    try:
        decoded = firebase_auth.verify_id_token(token, app=get_firebase_app(), check_revoked=True)
    except firebase_auth.ExpiredIdTokenError as exc:
        raise ExpiredTokenError() from exc
    except firebase_auth.RevokedIdTokenError as exc:
        raise RevokedTokenError() from exc
    except firebase_auth.InvalidIdTokenError as exc:
        raise InvalidTokenError() from exc
    except firebase_auth.CertificateFetchError as exc:
        logger.warning("Firebase certificate fetch failed while verifying a token")
        raise InvalidTokenError("Could not verify authentication token - try again shortly.") from exc
    # Deliberately NOT a blanket `except Exception` here: anything other
    # than the specific Firebase token-verification failures above (e.g. a
    # server misconfiguration such as Firebase Admin SDK credentials not
    # being set) is a server-side bug, not a client auth failure - it
    # should surface as a 500 via the app's existing unhandled-exception
    # handler (app/core/exceptions.py), not be mislabeled as "invalid
    # token". Verified manually: without FIREBASE_CREDENTIALS_*
    # configured, this now correctly produces a 500 with a logged
    # traceback instead of a misleading 401.

    return FirebaseUser(
        uid=decoded["uid"],
        phone_number=decoded.get("phone_number"),
        email=decoded.get("email"),
        email_verified=decoded.get("email_verified", False),
    )


async def get_current_user(
    firebase_user: Annotated[FirebaseUser, Depends(get_current_firebase_user)],
    session: DBSession,
) -> User:
    """Map the verified Firebase identity to the corresponding EGO `User`,
    auto-provisioning one on first sign-in.

    Firebase Phone Auth (the app's only sign-in method - see
    docs/flutter-authentication.md) never distinguishes a new account from
    a returning one: the first successful phone verification for a number
    IS the registration. This mirrors that on the backend - there is no
    separate "create my EGO account" endpoint; the first authenticated
    request from a never-before-seen Firebase identity creates the row.

    Explicitly commits after creating a new row (rather than leaving it to
    the caller, the usual repository-layer convention - see
    docs/repository-layer.md) because this dependency runs for read-only
    routes too (`GET /api/v1/users/me` above all), which never call a
    service that would otherwise commit - without an explicit commit here,
    a freshly auto-provisioned user would be visible for the one request
    that created it and then silently vanish (rolled back when the
    session closes) on every request after.

    Handles the race where two concurrent requests for the same
    never-before-seen Firebase identity (e.g. two device tabs/app
    instances signing in at once) both attempt to create - the loser hits
    a unique-constraint violation on `firebase_uid`, which is caught and
    turned into a re-lookup of the row the winner just committed, rather
    than a spurious error.
    """
    repository = UserRepository(session)
    user = await repository.get_by_firebase_uid(firebase_user.uid)
    if user is not None:
        return user

    if not firebase_user.phone_number:
        # Can't happen via this app's own phone+OTP sign-in (the token
        # always carries a phone_number) - defensive only, in case a
        # differently-configured Firebase project ever issues a token
        # from another sign-in method.
        raise UserMappingNotConfiguredError(
            "This Firebase identity has no phone number, and phone is required "
            "to create an EGO account. See docs/authentication.md."
        )

    try:
        user = await repository.create(
            firebase_uid=firebase_user.uid,
            phone=firebase_user.phone_number,
            language="en",
            role="worker",
        )
        await session.commit()
    except DuplicateRecordError:
        await session.rollback()
        user = await repository.get_by_firebase_uid(firebase_user.uid)
        if user is None:
            raise
    return user


# --- Authorization (Task 10) ------------------------------------------
#
# Everything above is AUTHENTICATION - "who is this user?" (Firebase).
# Everything below is AUTHORIZATION - "what is this user allowed to do?"
# (EGO's own database). The backend never trusts a `role="worker"` or
# `role="business"` claim from Flutter - these dependencies re-derive
# permission from whether a Worker/HiringParty *row exists* for the
# already-authenticated user (docs/user-role-architecture.md Part 1/2).
#
# Both depend on `get_current_user` (not `get_current_firebase_user`) -
# authorization only makes sense once identity is resolved - so they
# inherit the same "AUTHENTICATION SCHEMA DECISION REQUIRED" block until
# that's unblocked; nothing new is broken by that, they simply can't be
# reached yet either, exactly like `get_current_user` itself.


async def get_current_worker(
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> Worker:
    """A route depending on this only runs for a user who HAS a Worker
    profile - anyone else gets 403 `WorkerProfileRequiredError`, not 404
    (they're authenticated; they're just not permitted)."""
    worker = await WorkerRepository(session).get_by_id(current_user.user_id)
    if worker is None:
        raise WorkerProfileRequiredError()
    return worker


async def get_current_business(
    current_user: Annotated[User, Depends(get_current_user)],
    session: DBSession,
) -> HiringParty:
    """Business-profile counterpart to `get_current_worker`."""
    business = await HiringPartyRepository(session).get_by_id(current_user.user_id)
    if business is None:
        raise BusinessProfileRequiredError()
    return business
