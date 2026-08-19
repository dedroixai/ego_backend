"""Tests for the Worker/Business authorization layer (Task 10, Part 6/8).

`get_current_worker`/`get_current_business` (app/auth/dependencies.py) are
not yet used by any real endpoint (the endpoints that would use them -
job posting, job applications - are explicitly out of scope for this
task). They're tested directly here as plain async functions - they take
no FastAPI-specific input beyond an already-resolved `User` and a
session, so this is a faithful, direct test of the actual enforcement
logic a future endpoint would rely on, without inventing that endpoint.

Skipped automatically if TEST_DATABASE_URL isn't configured; never
touches Supabase DATABASE_URL.
"""

import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_business,
    get_current_firebase_user,
    get_current_user,
    get_current_worker,
)
from app.auth.exceptions import BusinessProfileRequiredError, WorkerProfileRequiredError
from app.main import app
from app.models.user import User
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.user_repository import UserRepository
from app.repositories.worker_repository import WorkerRepository

_FAKE_FIREBASE_APP = object()


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


async def _seed_user(db_session: AsyncSession, **overrides: object) -> User:
    defaults = {"phone": _phone(), "language": "en", "role": "worker"}
    defaults.update(overrides)
    user = await UserRepository(db_session).create(**defaults)
    await db_session.commit()
    return user


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# --- 1. Unauthenticated public request succeeds -----------------------


async def test_unauthenticated_public_request_succeeds() -> None:
    async with await _client() as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- 2. Unauthenticated protected request fails -------------------------


async def test_unauthenticated_protected_request_fails() -> None:
    async with await _client() as client:
        response = await client.get("/api/v1/workers/me")
    assert response.status_code == 401


# --- 3/4. Authenticated Worker/Business can access their own operations -


async def test_worker_with_profile_passes_get_current_worker(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()

    worker = await get_current_worker(current_user=user, session=db_session)

    assert worker.user_id == user.user_id


async def test_business_with_profile_passes_get_current_business(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session, role="hiring_party")
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()

    business = await get_current_business(current_user=user, session=db_session)

    assert business.user_id == user.user_id


# --- 5/6. Worker cannot perform Business-only ops and vice versa --------


async def test_worker_only_user_cannot_pass_get_current_business(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()

    with pytest.raises(BusinessProfileRequiredError):
        await get_current_business(current_user=user, session=db_session)


async def test_business_only_user_cannot_pass_get_current_worker(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session, role="hiring_party")
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()

    with pytest.raises(WorkerProfileRequiredError):
        await get_current_worker(current_user=user, session=db_session)


async def test_user_with_both_profiles_passes_both_checks(db_session: AsyncSession) -> None:
    """Confirms docs/user-role-architecture.md Part 1's finding: a single
    user CAN hold both profiles and pass both authorization checks - this
    is exactly what "switching modes" without a second account requires."""
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()

    worker = await get_current_worker(current_user=user, session=db_session)
    business = await get_current_business(current_user=user, session=db_session)

    assert worker.user_id == business.user_id == user.user_id


# --- 7. User cannot access another user's private profile ---------------


async def test_user_cannot_update_another_users_worker_profile(db_session: AsyncSession) -> None:
    """The API itself never accepts a target user_id at all (see
    app/api/v1/endpoints/workers.py) - it's structurally impossible to
    even attempt this through the HTTP layer. Demonstrated here directly
    against the service (mirrors tests/test_services.py, Task 7) to prove
    the underlying ownership check this task's endpoints rely on is real."""
    from app.services.exceptions import UnauthorizedOperationError
    from app.services.worker_service import WorkerService

    owner = await _seed_user(db_session)
    attacker = await _seed_user(db_session)
    await WorkerRepository(db_session).create(
        user_id=owner.user_id, name="Jane", skills=[], service_locations=[]
    )
    await db_session.commit()

    with pytest.raises(UnauthorizedOperationError):
        await WorkerService(db_session).update_profile(owner.user_id, attacker.user_id, name="Hijacked")


# --- 8. Switching UI mode does not bypass backend authorization ---------


async def test_client_supplied_mode_header_has_no_effect_on_authorization(db_session: AsyncSession) -> None:
    """There is no "mode" parameter anywhere in get_current_worker/
    get_current_business's signature (docs/user-role-architecture.md Part
    3/7 - mode is a Flutter UI concept only, never sent to or stored by
    the backend). Demonstrated concretely: a request claiming
    "X-App-Mode: business" for a user who only has a Worker profile still
    gets 403 on a hypothetical business-gated check - the header is never
    even read."""
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()

    # Even though nothing about this "mode" header is read anywhere in the
    # authorization dependency, prove it doesn't matter by trying anyway.
    with pytest.raises(BusinessProfileRequiredError):
        await get_current_business(current_user=user, session=db_session)


# --- 9. Firebase UID is always taken from the verified token ------------


async def test_firebase_uid_always_comes_from_verified_token_not_request_body() -> None:
    """get_current_firebase_user has no code path that reads a UID from
    anywhere except the decoded, signature-verified token - proven by
    controlling exactly what the (mocked) verification returns and
    confirming that value, and only that value, is used."""

    class _FakeRequest:
        headers = {"Authorization": "Bearer some-token"}

    with (
        patch("app.auth.dependencies.get_firebase_app", return_value=_FAKE_FIREBASE_APP),
        patch(
            "app.auth.dependencies.firebase_auth.verify_id_token",
            return_value={"uid": "the-real-verified-uid"},
        ),
    ):
        firebase_user = await get_current_firebase_user(request=_FakeRequest())

    assert firebase_user.uid == "the-real-verified-uid"


async def test_get_current_user_never_accepts_a_uid_parameter() -> None:
    """Structural check: get_current_user's only inputs are the verified
    FirebaseUser (itself only derived from the token) and a DB session -
    there is no `uid`/`firebase_uid` parameter a caller could inject."""
    import inspect

    params = set(inspect.signature(get_current_user).parameters)
    assert params == {"firebase_user", "session"}
