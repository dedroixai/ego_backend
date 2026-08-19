"""Integration tests for the User/Profile API vertical slice
(GET/PATCH /api/v1/users/me).

Two distinct testing strategies, both against the REAL running FastAPI app
via an ASGI-transport httpx client (never bypassing routing/schema
validation):

- "Not authenticated" / "authenticated but unmapped" cases hit the REAL,
  unmodified dependency chain (Firebase verification mocked, exactly like
  tests/test_auth.py - never real Firebase network calls).
- "Authenticated and mapped to an EGO user" cases use FastAPI's
  `app.dependency_overrides` for `get_current_user` (a standard, correct
  testing technique - not a shortcut in the *application* architecture,
  which is untouched) combined with the REAL disposable test database (see
  tests/conftest.py / docs/repository-layer.md), so the rest of the stack
  - Route -> Schema -> Service -> Repository -> SQLAlchemy -> Postgres -
  is exercised for real. This is necessary because `get_current_user`
  itself is currently blocked (docs/authentication.md "AUTHENTICATION
  SCHEMA DECISION REQUIRED") - there is no real code path that produces a
  mapped user yet to test against otherwise.

Uses `httpx.AsyncClient` + `ASGITransport` (not the sync `TestClient`)
specifically so the app runs in the SAME asyncio event loop as the test
function and the shared `db_session` fixture - the sync `TestClient` runs
the app in its own internal event-loop portal, which caused a genuine
cross-loop asyncpg error when a route (PATCH) actually used the shared
session (discovered while writing these tests).

Skipped automatically if TEST_DATABASE_URL isn't configured. Never touches
the app's Supabase DATABASE_URL for these DB-backed cases.
"""

import uuid
from unittest.mock import patch

import pytest
from firebase_admin import auth as firebase_auth
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.dependencies import get_db
from app.main import app
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.exceptions import BusinessRuleViolationError

_FAKE_FIREBASE_APP = object()


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


def _patched_firebase(verify_result=None, verify_side_effect=None):
    return (
        patch("app.auth.dependencies.get_firebase_app", return_value=_FAKE_FIREBASE_APP),
        patch(
            "app.auth.dependencies.firebase_auth.verify_id_token",
            return_value=verify_result,
            side_effect=verify_side_effect,
        ),
    )


async def _seed_user(db_session: AsyncSession, **overrides: object) -> User:
    defaults = {"phone": _phone(), "language": "en", "role": "worker"}
    defaults.update(overrides)
    user = await UserRepository(db_session).create(**defaults)
    await db_session.commit()
    return user


def _override_authenticated_as(user: User, db_session: AsyncSession) -> None:
    async def override_get_current_user() -> User:
        return user

    async def override_get_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# =====================================================================
# GET /api/v1/users/me
# =====================================================================


async def test_get_me_no_authentication() -> None:
    async with await _client() as client:
        response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_get_me_invalid_authentication() -> None:
    p1, p2 = _patched_firebase(verify_side_effect=firebase_auth.InvalidIdTokenError("bad"))
    with p1, p2:
        async with await _client() as client:
            response = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


async def test_get_me_valid_firebase_auth_but_not_mapped_to_ego_user() -> None:
    """Cases 3 + 5 together: a genuinely valid Firebase token, verified for
    real by the real dependency chain, that currently cannot be mapped to
    an EGO user - see docs/authentication.md."""
    p1, p2 = _patched_firebase(verify_result={"uid": "some-firebase-uid"})
    with p1, p2:
        async with await _client() as client:
            response = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer valid-token"})
    assert response.status_code == 501


async def test_get_me_firebase_user_mapped_to_ego_user(db_session: AsyncSession) -> None:
    """Case 4: simulates what `get_current_user` will return once the
    schema gap is resolved, via dependency override - see module docstring."""
    user = await _seed_user(db_session, language="en", role="worker")
    _override_authenticated_as(user, db_session)

    async with await _client() as client:
        response = await client.get("/api/v1/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.user_id)
    assert body["phone"] == user.phone
    assert body["role"] == "worker"
    # No internal/unexpected fields leak through.
    assert set(body.keys()) == {"user_id", "phone", "language", "role", "kyc_status", "created_at", "dob"}


# =====================================================================
# PATCH /api/v1/users/me
# =====================================================================


async def test_patch_me_unauthenticated() -> None:
    async with await _client() as client:
        response = await client.patch("/api/v1/users/me", json={"language": "hi"})
    assert response.status_code == 401


async def test_patch_me_valid_update_persists_to_database(db_session: AsyncSession) -> None:
    """Cases 1 + 5: a valid update succeeds and the database write is real
    - verified by re-fetching the row through the repository afterward."""
    user = await _seed_user(db_session, language="en")
    _override_authenticated_as(user, db_session)

    async with await _client() as client:
        response = await client.patch("/api/v1/users/me", json={"language": "hi"})

    assert response.status_code == 200
    assert response.json()["language"] == "hi"

    refetched = await UserRepository(db_session).get_by_id(user.user_id)
    assert refetched is not None
    assert refetched.language == "hi"


async def test_patch_me_invalid_input_rejected(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _override_authenticated_as(user, db_session)

    async with await _client() as client:
        response = await client.patch(
            "/api/v1/users/me", json={"language": "this-is-way-too-long-for-the-field"}
        )

    assert response.status_code == 422


async def test_patch_me_cannot_modify_protected_fields(db_session: AsyncSession) -> None:
    """Client-supplied `user_id`, `phone`, `role`, `kyc_status`, `created_at`
    are all rejected outright (RequestModel's extra="forbid") - not
    silently ignored, not applied."""
    user = await _seed_user(db_session)
    _override_authenticated_as(user, db_session)

    async with await _client() as client:
        for field, value in [
            ("user_id", str(uuid.uuid4())),
            ("phone", "+15559999999"),
            ("role", "hiring_party"),
            ("kyc_status", "verified"),
            ("created_at", "2020-01-01T00:00:00Z"),
        ]:
            response = await client.patch("/api/v1/users/me", json={field: value})
            assert response.status_code == 422, f"expected {field} to be rejected"

    # Confirm nothing was changed despite the attempts.
    unchanged = await UserRepository(db_session).get_by_id(user.user_id)
    assert unchanged is not None
    assert unchanged.role == user.role
    assert unchanged.phone == user.phone


async def test_patch_me_database_failure_does_not_leak_raw_details(db_session: AsyncSession) -> None:
    """Simulates a repository-translated DB error surfacing through the
    service layer (app.services.exceptions.BusinessRuleViolationError may
    carry raw Postgres error text - see app/api/exception_handlers.py) and
    asserts the client never sees that raw text, only a generic message."""
    user = await _seed_user(db_session)
    _override_authenticated_as(user, db_session)

    with patch(
        "app.services.user_service.UserService.update_profile",
        side_effect=BusinessRuleViolationError(
            "duplicate key value violates unique constraint \"uq_users_phone\" DETAIL: Key (phone)=(...) already exists."
        ),
    ):
        async with await _client() as client:
            response = await client.patch("/api/v1/users/me", json={"language": "hi"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "duplicate key" not in detail
    assert "constraint" not in detail
    assert detail == "This operation could not be completed."
