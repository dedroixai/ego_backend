"""Tests for Firebase authentication (app/auth/).

Never uses real Firebase credentials or makes real network calls -
`firebase_admin.auth.verify_id_token` and Firebase app initialization are
both mocked. Hits the real GET /api/v1/users/me endpoint via FastAPI's
TestClient to exercise the full dependency chain (header parsing -> token
verification -> EGO user mapping) end to end, not just the dependency
function in isolation.

Tests 1-4 and 8 below fail INSIDE `get_current_firebase_user` (missing/
malformed/invalid/expired/revoked token, or no header at all) - the
`get_current_user` dependency's body never runs for these, so a plain
sync `TestClient` is safe (no database is ever queried, exactly as
before `get_current_user` gained real auto-provisioning logic).

Tests 5+ use a VALID token, so `get_current_user` now actually queries -
and, on first sign-in, writes to - the database (auto-provisioning, see
`app/auth/dependencies.py`). Those use the disposable test Postgres via
the shared `db_session`/`get_db` override (see `conftest.py` and
`docs/repository-layer.md`), never the real Supabase `DATABASE_URL` - the
same "never let a repository/integration test touch production" rule the
rest of this suite already follows.
"""

import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth as firebase_auth
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.main import app
from app.repositories.user_repository import UserRepository

client = TestClient(app)

_FAKE_FIREBASE_APP = object()


def _decoded_token(uid: str = "firebase-uid-123", **extra: object) -> dict:
    return {"uid": uid, **extra}


def _patched_firebase(verify_result=None, verify_side_effect=None):
    return (
        patch("app.auth.dependencies.get_firebase_app", return_value=_FAKE_FIREBASE_APP),
        patch(
            "app.auth.dependencies.firebase_auth.verify_id_token",
            return_value=verify_result,
            side_effect=verify_side_effect,
        ),
    )


async def _client_with_db(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _teardown() -> None:
    app.dependency_overrides.clear()


# --- 1. Missing Authorization header ---------------------------------------


def test_missing_authorization_header() -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Missing Authorization header."}


# --- 2. Malformed Authorization header --------------------------------------


@pytest.mark.parametrize(
    "header_value",
    ["not-a-bearer-token", "Bearer", "Bearer ", "Basic abcdef", "bearer   "],
)
def test_malformed_authorization_header(header_value: str) -> None:
    response = client.get("/api/v1/users/me", headers={"Authorization": header_value})
    assert response.status_code == 401
    assert "Bearer <token>" in response.json()["detail"]


# --- 3. Invalid token --------------------------------------------------------


def test_invalid_token() -> None:
    p1, p2 = _patched_firebase(verify_side_effect=firebase_auth.InvalidIdTokenError("bad token"))
    with p1, p2:
        response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token."}


# --- 4. Expired token (and revoked, same category of failure) --------------


def test_expired_token() -> None:
    p1, p2 = _patched_firebase(verify_side_effect=firebase_auth.ExpiredIdTokenError("expired", cause=None))
    with p1, p2:
        response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer expired-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication token has expired."}


def test_revoked_token() -> None:
    p1, p2 = _patched_firebase(verify_side_effect=firebase_auth.RevokedIdTokenError("revoked"))
    with p1, p2:
        response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer revoked-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication token has been revoked."}


# --- 5. Valid token, never-before-seen identity -> auto-provisioned --------


async def test_valid_token_auto_provisions_a_new_ego_user(db_session: AsyncSession, caplog) -> None:
    """A valid token must authenticate successfully (never 401) and, for a
    Firebase UID with no existing EGO User, create one automatically
    (Firebase Phone Auth's own "first verification = registration"
    semantics, mirrored on the backend). Also asserts the raw token/header
    value is never written to the logs."""
    p1, p2 = _patched_firebase(
        verify_result=_decoded_token(uid="firebase-uid-new-1", phone_number="+919876500001")
    )
    with caplog.at_level(logging.DEBUG):
        with p1, p2:
            async with await _client_with_db(db_session) as ac:
                try:
                    response = await ac.get(
                        "/api/v1/users/me", headers={"Authorization": "Bearer super-secret-valid-token-value"}
                    )
                finally:
                    await _teardown()

    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+919876500001"

    created = await UserRepository(db_session).get_by_firebase_uid("firebase-uid-new-1")
    assert created is not None
    assert created.phone == "+919876500001"

    for record in caplog.records:
        assert "super-secret-valid-token-value" not in record.getMessage()


# --- 6/7. A returning identity maps to the SAME EGO User, not a new one ---


async def test_valid_token_for_an_existing_identity_returns_the_same_user_not_a_duplicate(
    db_session: AsyncSession,
) -> None:
    p1, p2 = _patched_firebase(verify_result=_decoded_token(uid="firebase-uid-returning", phone_number="+919876500002"))

    async def _call() -> str:
        with p1, p2:
            async with await _client_with_db(db_session) as ac:
                try:
                    response = await ac.get(
                        "/api/v1/users/me", headers={"Authorization": "Bearer valid-token"}
                    )
                finally:
                    await _teardown()
        assert response.status_code == 200
        return response.json()["user_id"]

    first_user_id = await _call()
    second_user_id = await _call()

    assert first_user_id == second_user_id


# --- 8. Protected endpoint without authentication ---------------------------


def test_protected_endpoint_without_authentication() -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


# --- 9. Protected endpoint with authentication ------------------------------


async def test_protected_endpoint_with_authentication_reaches_full_dependency_chain(
    db_session: AsyncSession,
) -> None:
    """Proves the full chain - Authorization header -> Firebase token
    verification -> EGO user lookup/auto-provisioning - is wired end to
    end: a valid token never gets a 401, and reaches a real 200 with a
    real EGO user, not an earlier failure."""
    p1, p2 = _patched_firebase(verify_result=_decoded_token(uid="firebase-uid-full-chain", phone_number="+919876500003"))
    with p1, p2:
        async with await _client_with_db(db_session) as ac:
            try:
                response = await ac.get("/api/v1/users/me", headers={"Authorization": "Bearer valid-token"})
            finally:
                await _teardown()

    assert response.status_code == 200
    assert response.json()["phone"] == "+919876500003"
