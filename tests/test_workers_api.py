"""Integration tests for the Worker Profile API (GET/POST/PATCH
/api/v1/workers/me). Mirrors tests/test_users_api.py's strategy - see its
module docstring for why `httpx.AsyncClient`/`ASGITransport` and
dependency-override-with-real-test-database are used together. Skipped
automatically if TEST_DATABASE_URL isn't configured; never touches
Supabase DATABASE_URL.
"""

import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.dependencies import get_db
from app.main import app
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.worker_repository import WorkerRepository


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


async def _seed_user(db_session: AsyncSession, **overrides: object) -> User:
    defaults = {"phone": _phone(), "language": "en", "role": "worker"}
    defaults.update(overrides)
    user = await UserRepository(db_session).create(**defaults)
    await db_session.commit()
    return user


def _use_test_db(db_session: AsyncSession) -> None:
    """Public endpoints take no auth dependency at all, so `_authenticate_as`
    (which also overrides `get_current_user`) doesn't apply - but they
    still need to query the same test database that seeded their fixture
    data, not the app's real (production Supabase) `get_db`."""

    async def override_get_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_db] = override_get_db


def _authenticate_as(user: User, db_session: AsyncSession) -> None:
    async def override_get_current_user() -> User:
        return user

    _use_test_db(db_session)
    app.dependency_overrides[get_current_user] = override_get_current_user


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _teardown():
    app.dependency_overrides.clear()


# =====================================================================
# GET /api/v1/workers (public listing - browse/nearby workers)
# =====================================================================


async def test_list_workers_without_authentication_succeeds(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    worker = await WorkerRepository(db_session).create(
        user_id=user.user_id, name="Jane Doe", skills=["Electrician"], service_locations=["Mumbai"]
    )
    await db_session.commit()
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/workers")
    finally:
        await _teardown()

    assert response.status_code == 200
    assert str(worker.user_id) in {w["user_id"] for w in response.json()}


async def test_list_workers_filters_by_location(db_session: AsyncSession) -> None:
    repo = WorkerRepository(db_session)
    mumbai_user = await _seed_user(db_session)
    mumbai_worker = await repo.create(
        user_id=mumbai_user.user_id, name="Mumbai Worker", skills=[], service_locations=["Mumbai, Maharashtra"]
    )
    delhi_user = await _seed_user(db_session)
    await repo.create(user_id=delhi_user.user_id, name="Delhi Worker", skills=[], service_locations=["Delhi"])
    await db_session.commit()
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/workers", params={"location": "Mumbai"})
    finally:
        await _teardown()

    ids = {w["user_id"] for w in response.json()}
    assert ids == {str(mumbai_worker.user_id)}


async def test_list_workers_filters_by_search_matching_skills(db_session: AsyncSession) -> None:
    repo = WorkerRepository(db_session)
    electrician_user = await _seed_user(db_session)
    electrician = await repo.create(
        user_id=electrician_user.user_id, name="Amit", skills=["Electrician", "Wiring"], service_locations=[]
    )
    plumber_user = await _seed_user(db_session)
    await repo.create(user_id=plumber_user.user_id, name="Ravi", skills=["Plumbing"], service_locations=[])
    await db_session.commit()
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/workers", params={"search": "electric"})
    finally:
        await _teardown()

    ids = {w["user_id"] for w in response.json()}
    assert ids == {str(electrician.user_id)}


async def test_list_workers_response_never_includes_bank_details(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(
        user_id=user.user_id, name="Jane Doe", skills=[], service_locations=[], bank_details="secret-account-number"
    )
    await db_session.commit()
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/workers")
    finally:
        await _teardown()

    body = response.text
    assert "secret-account-number" not in body
    assert "bank_details" not in response.json()[0]


# =====================================================================
# GET /api/v1/workers/me
# =====================================================================


async def test_get_worker_me_no_authentication() -> None:
    async with await _client() as client:
        response = await client.get("/api/v1/workers/me")
    assert response.status_code == 401


async def test_get_worker_me_no_profile_yet_returns_404(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/workers/me")
    finally:
        await _teardown()
    assert response.status_code == 404


async def test_get_worker_me_with_profile_returns_200(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/workers/me")
    finally:
        await _teardown()

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.user_id)
    assert body["name"] == "Jane"
    assert "bank_details" not in body


# =====================================================================
# POST /api/v1/workers/me
# =====================================================================


async def test_post_worker_me_creates_profile(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post("/api/v1/workers/me", json={"name": "Jane Doe"})
    finally:
        await _teardown()

    assert response.status_code == 201
    assert response.json()["name"] == "Jane Doe"

    persisted = await WorkerRepository(db_session).get_by_id(user.user_id)
    assert persisted is not None


async def test_post_worker_me_twice_conflicts(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            first = await client.post("/api/v1/workers/me", json={"name": "Jane Doe"})
            second = await client.post("/api/v1/workers/me", json={"name": "Jane Again"})
    finally:
        await _teardown()

    assert first.status_code == 201
    assert second.status_code == 409


async def test_post_worker_me_missing_required_field(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post("/api/v1/workers/me", json={})
    finally:
        await _teardown()
    assert response.status_code == 422


async def test_post_worker_me_cannot_self_assign_verified_badge(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/workers/me", json={"name": "Jane", "verified_badge": True}
            )
    finally:
        await _teardown()
    assert response.status_code == 422


async def test_post_worker_me_unauthenticated() -> None:
    async with await _client() as client:
        response = await client.post("/api/v1/workers/me", json={"name": "Jane"})
    assert response.status_code == 401


# =====================================================================
# PATCH /api/v1/workers/me
# =====================================================================


async def test_patch_worker_me_updates_and_persists(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.patch("/api/v1/workers/me", json={"availability": "full-time"})
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["availability"] == "full-time"

    refetched = await WorkerRepository(db_session).get_by_id(user.user_id)
    assert refetched is not None
    assert refetched.availability == "full-time"


async def test_patch_worker_me_cannot_modify_protected_fields(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            for field, value in [
                ("user_id", str(uuid.uuid4())),
                ("rating", "5.0"),
                ("verified_badge", True),
            ]:
                response = await client.patch("/api/v1/workers/me", json={field: value})
                assert response.status_code == 422, f"expected {field} to be rejected"
    finally:
        await _teardown()


# =====================================================================
# profile_image_url (Task 20)
# =====================================================================


async def test_post_worker_me_with_profile_image_url(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/workers/me",
                json={"name": "Jane", "profile_image_url": "https://firebasestorage.googleapis.com/v0/b/x/o/y.jpg"},
            )
    finally:
        await _teardown()

    assert response.status_code == 201
    assert response.json()["profile_image_url"] == "https://firebasestorage.googleapis.com/v0/b/x/o/y.jpg"


async def test_patch_worker_me_updates_profile_image_url_and_persists(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()
    _authenticate_as(user, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                "/api/v1/workers/me",
                json={"profile_image_url": "https://firebasestorage.googleapis.com/v0/b/x/o/new.jpg"},
            )
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["profile_image_url"] == "https://firebasestorage.googleapis.com/v0/b/x/o/new.jpg"

    refetched = await WorkerRepository(db_session).get_by_id(user.user_id)
    assert refetched is not None
    assert refetched.profile_image_url == "https://firebasestorage.googleapis.com/v0/b/x/o/new.jpg"


async def test_worker_cannot_set_another_workers_profile_image(db_session: AsyncSession) -> None:
    """Task 20 Step 14 - there is no `user_id`/`worker_id` field on
    `WorkerUpdate` at all (same structural guarantee as every other
    Worker field - see `test_patch_worker_me_cannot_modify_protected_fields`) -
    Worker A's PATCH can only ever affect Worker A's own row, regardless
    of what it sends."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    await WorkerRepository(db_session).create(user_id=user_a.user_id, name="A", skills=[], service_locations=[])
    await WorkerRepository(db_session).create(user_id=user_b.user_id, name="B", skills=[], service_locations=[])
    await db_session.commit()

    _authenticate_as(user_a, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                "/api/v1/workers/me", json={"profile_image_url": "https://example.com/a.jpg"}
            )
    finally:
        await _teardown()
    assert response.status_code == 200

    b_profile = await WorkerRepository(db_session).get_by_id(user_b.user_id)
    assert b_profile is not None
    assert b_profile.profile_image_url is None  # unaffected by A's update
