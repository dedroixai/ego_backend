"""Integration tests for the Business (HiringParty) Profile API
(GET/POST/PATCH /api/v1/businesses/me). Mirrors tests/test_workers_api.py -
see tests/test_users_api.py's module docstring for the overall testing
strategy. Skipped automatically if TEST_DATABASE_URL isn't configured;
never touches Supabase DATABASE_URL.
"""

import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.dependencies import get_db
from app.main import app
from app.models.user import User
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.user_repository import UserRepository


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


async def _seed_user(db_session: AsyncSession, **overrides: object) -> User:
    defaults = {"phone": _phone(), "language": "en", "role": "hiring_party"}
    defaults.update(overrides)
    user = await UserRepository(db_session).create(**defaults)
    await db_session.commit()
    return user


def _authenticate_as(user: User, db_session: AsyncSession) -> None:
    async def override_get_current_user() -> User:
        return user

    async def override_get_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _teardown():
    app.dependency_overrides.clear()


# =====================================================================
# GET /api/v1/businesses/me
# =====================================================================


async def test_get_business_me_no_authentication() -> None:
    async with await _client() as client:
        response = await client.get("/api/v1/businesses/me")
    assert response.status_code == 401


async def test_get_business_me_no_profile_yet_returns_404(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/businesses/me")
    finally:
        await _teardown()
    assert response.status_code == 404


async def test_get_business_me_with_profile_returns_200(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/businesses/me")
    finally:
        await _teardown()

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.user_id)
    assert body["account_type"] == "business"


# =====================================================================
# POST /api/v1/businesses/me
# =====================================================================


async def test_post_business_me_creates_profile(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post("/api/v1/businesses/me", json={"account_type": "business"})
    finally:
        await _teardown()

    assert response.status_code == 201
    assert response.json()["account_type"] == "business"

    persisted = await HiringPartyRepository(db_session).get_by_id(user.user_id)
    assert persisted is not None


async def test_post_business_me_twice_conflicts(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            first = await client.post("/api/v1/businesses/me", json={"account_type": "business"})
            second = await client.post("/api/v1/businesses/me", json={"account_type": "business"})
    finally:
        await _teardown()

    assert first.status_code == 201
    assert second.status_code == 409


async def test_post_business_me_missing_required_field(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post("/api/v1/businesses/me", json={})
    finally:
        await _teardown()
    assert response.status_code == 422


async def test_post_business_me_cannot_self_assign_verified_badge(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/businesses/me", json={"account_type": "business", "verified_badge": True}
            )
    finally:
        await _teardown()
    assert response.status_code == 422


async def test_post_business_me_unauthenticated() -> None:
    async with await _client() as client:
        response = await client.post("/api/v1/businesses/me", json={"account_type": "business"})
    assert response.status_code == 401


# =====================================================================
# PATCH /api/v1/businesses/me
# =====================================================================


async def test_patch_business_me_updates_and_persists(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.patch("/api/v1/businesses/me", json={"business_name": "Acme Co"})
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["business_name"] == "Acme Co"

    refetched = await HiringPartyRepository(db_session).get_by_id(user.user_id)
    assert refetched is not None
    assert refetched.business_name == "Acme Co"


async def test_patch_business_me_cannot_modify_protected_fields(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            for field, value in [
                ("user_id", str(uuid.uuid4())),
                ("rating", "5.0"),
                ("verified_badge", True),
                ("verification_level", "gold"),
            ]:
                response = await client.patch("/api/v1/businesses/me", json={field: value})
                assert response.status_code == 422, f"expected {field} to be rejected"
    finally:
        await _teardown()


# =====================================================================
# profile_image_url (Task 20)
# =====================================================================


async def test_post_business_me_with_profile_image_url(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/businesses/me",
                json={
                    "account_type": "business",
                    "profile_image_url": "https://firebasestorage.googleapis.com/v0/b/x/o/logo.jpg",
                },
            )
    finally:
        await _teardown()

    assert response.status_code == 201
    assert response.json()["profile_image_url"] == "https://firebasestorage.googleapis.com/v0/b/x/o/logo.jpg"


async def test_patch_business_me_updates_profile_image_url_and_persists(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                "/api/v1/businesses/me",
                json={"profile_image_url": "https://firebasestorage.googleapis.com/v0/b/x/o/new_logo.jpg"},
            )
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["profile_image_url"] == "https://firebasestorage.googleapis.com/v0/b/x/o/new_logo.jpg"

    refetched = await HiringPartyRepository(db_session).get_by_id(user.user_id)
    assert refetched is not None
    assert refetched.profile_image_url == "https://firebasestorage.googleapis.com/v0/b/x/o/new_logo.jpg"


async def test_business_cannot_set_another_businesss_profile_image(db_session: AsyncSession) -> None:
    """Task 20 Step 14 - same structural guarantee as Worker (no
    `user_id`/`business_id` field on `HiringPartyUpdate` at all)."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    await HiringPartyRepository(db_session).create(user_id=user_a.user_id, account_type="business")
    await HiringPartyRepository(db_session).create(user_id=user_b.user_id, account_type="business")
    await db_session.commit()

    _authenticate_as(user_a, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                "/api/v1/businesses/me", json={"profile_image_url": "https://example.com/a-logo.jpg"}
            )
    finally:
        await _teardown()
    assert response.status_code == 200

    b_profile = await HiringPartyRepository(db_session).get_by_id(user_b.user_id)
    assert b_profile is not None
    assert b_profile.profile_image_url is None  # unaffected by A's update
