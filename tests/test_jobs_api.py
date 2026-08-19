"""Integration tests for the Job Management API
(GET/POST/PATCH /api/v1/jobs, GET /api/v1/jobs/{job_id}).

Mirrors the strategy established in tests/test_users_api.py (see its
module docstring): `httpx.AsyncClient`/`ASGITransport` + FastAPI
dependency overrides against a real disposable test database. Skipped
automatically if TEST_DATABASE_URL isn't configured; never touches
Supabase DATABASE_URL.
"""

import uuid
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.dependencies import get_db
from app.main import app
from app.models.job import Job
from app.models.user import User
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.job_category_repository import JobCategoryRepository
from app.repositories.job_repository import JobRepository
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


async def _seed_business(db_session: AsyncSession) -> User:
    user = await _seed_user(db_session, role="hiring_party")
    await HiringPartyRepository(db_session).create(user_id=user.user_id, account_type="business")
    await db_session.commit()
    return user


async def _seed_worker_only(db_session: AsyncSession) -> User:
    user = await _seed_user(db_session, role="worker")
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()
    return user


async def _seed_category(db_session: AsyncSession) -> uuid.UUID:
    category = await JobCategoryRepository(db_session).create(name=f"Category {uuid.uuid4()}")
    await db_session.commit()
    return category.category_id


async def _seed_job(
    db_session: AsyncSession, hiring_party_id: uuid.UUID, category_id: uuid.UUID, *, status: str = "draft"
) -> Job:
    job = await JobRepository(db_session).create(
        hiring_party_id=hiring_party_id,
        category_id=category_id,
        title="Fix leaking pipe",
        description="Kitchen sink leaking",
        budget=Decimal("1500.00"),
        location="Mumbai",
        status=status,
    )
    await db_session.commit()
    return job


def _use_test_db(db_session: AsyncSession) -> None:
    """Public endpoints take no auth dependency at all, so `_authenticate_as`
    (which also overrides `get_current_user`) doesn't apply - but they still
    need to query the same test database that seeded their fixture data,
    not the app's real (production Supabase) `get_db`."""

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


async def _teardown() -> None:
    app.dependency_overrides.clear()


# =====================================================================
# Public listing (Step 9, items 1-4)
# =====================================================================


async def test_list_jobs_without_authentication_succeeds(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/jobs")
    finally:
        await _teardown()

    assert response.status_code == 200
    assert str(job.job_id) in {j["job_id"] for j in response.json()}


async def test_list_jobs_default_hides_draft_and_closed(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    open_job = await _seed_job(db_session, business.user_id, category_id, status="open")
    await _seed_job(db_session, business.user_id, category_id, status="draft")
    await _seed_job(db_session, business.user_id, category_id, status="closed")
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/jobs")
    finally:
        await _teardown()

    ids = {job["job_id"] for job in response.json()}
    assert str(open_job.job_id) in ids
    assert len(ids) == 1


async def test_list_jobs_pagination(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    for _ in range(3):
        await _seed_job(db_session, business.user_id, category_id, status="open")
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            page1 = await client.get("/api/v1/jobs", params={"limit": 2, "offset": 0})
            page2 = await client.get("/api/v1/jobs", params={"limit": 2, "offset": 2})
    finally:
        await _teardown()

    assert len(page1.json()) == 2
    assert len(page2.json()) == 1
    assert {j["job_id"] for j in page1.json()}.isdisjoint({j["job_id"] for j in page2.json()})


async def test_list_jobs_search_matches_title_case_insensitively(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    matching = await JobRepository(db_session).create(
        hiring_party_id=business.user_id,
        category_id=category_id,
        title="Weekend Party Catering Help",
        description="Cook for a birthday party",
        budget=Decimal("950.00"),
        location="Mumbai",
        status="open",
    )
    await db_session.commit()
    await _seed_job(db_session, business.user_id, category_id, status="open")  # "Fix leaking pipe" - no match
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/jobs", params={"search": "party"})
    finally:
        await _teardown()

    ids = {job["job_id"] for job in response.json()}
    assert ids == {str(matching.job_id)}


async def test_get_job_by_id_returns_full_detail(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="draft")
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/jobs/{job.job_id}")
    finally:
        await _teardown()

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(job.job_id)
    assert body["description"] == "Kitchen sink leaking"
    assert body["status"] == "draft"  # detail view shows any status, unlike the listing default


async def test_get_nonexistent_job_returns_404(db_session: AsyncSession) -> None:
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    finally:
        await _teardown()
    assert response.status_code == 404


# =====================================================================
# My Jobs - GET /jobs/me (Task 18 - added for the Flutter Business flow;
# JobService.list_by_hiring_party existed since Task 7 but had no route)
# =====================================================================


async def test_my_jobs_requires_authentication(db_session: AsyncSession) -> None:
    _use_test_db(db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/jobs/me")
    finally:
        await _teardown()
    assert response.status_code == 401


async def test_my_jobs_requires_business_profile(db_session: AsyncSession) -> None:
    worker_user = await _seed_worker_only(db_session)
    _authenticate_as(worker_user, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/jobs/me")
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_my_jobs_returns_only_the_authenticated_businesss_jobs_including_non_open(
    db_session: AsyncSession,
) -> None:
    owner = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    # Deliberately draft + closed, not open - proving this is NOT the
    # public listing (which defaults to status=open only).
    draft_job = await _seed_job(db_session, owner.user_id, category_id, status="draft")
    closed_job = await _seed_job(db_session, owner.user_id, category_id, status="closed")
    await _seed_job(db_session, other_business.user_id, category_id, status="open")  # someone else's job

    _authenticate_as(owner, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/jobs/me")
    finally:
        await _teardown()

    assert response.status_code == 200
    job_ids = {job["job_id"] for job in response.json()}
    assert job_ids == {str(draft_job.job_id), str(closed_job.job_id)}


async def test_my_jobs_pagination(db_session: AsyncSession) -> None:
    owner = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    for _ in range(3):
        await _seed_job(db_session, owner.user_id, category_id, status="open")

    _authenticate_as(owner, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/jobs/me", params={"limit": 2, "offset": 0})
    finally:
        await _teardown()

    assert response.status_code == 200
    assert len(response.json()) == 2


# =====================================================================
# Job creation (Step 9, items 5-9)
# =====================================================================


async def test_authenticated_business_creates_job(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/jobs",
                json={
                    "category_id": str(category_id),
                    "title": "Fix leaking pipe",
                    "description": "desc",
                    "budget": "1500.00",
                    "location": "Mumbai",
                },
            )
    finally:
        await _teardown()

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["hiring_party_id"] == str(business.user_id)


async def test_job_create_and_response_include_image_url(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            create_response = await client.post(
                "/api/v1/jobs",
                json={
                    "category_id": str(category_id),
                    "title": "Fix leaking pipe",
                    "description": "desc",
                    "budget": "1500.00",
                    "location": "Mumbai",
                    "image_url": "https://storage.example.com/jobs/photo.jpg",
                },
            )
            assert create_response.status_code == 201
            job_id = create_response.json()["job_id"]

            get_response = await client.get(f"/api/v1/jobs/{job_id}")
    finally:
        await _teardown()

    assert create_response.json()["image_url"] == "https://storage.example.com/jobs/photo.jpg"
    assert get_response.status_code == 200
    assert get_response.json()["image_url"] == "https://storage.example.com/jobs/photo.jpg"


async def test_job_created_without_image_url_returns_null(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/jobs",
                json={
                    "category_id": str(category_id),
                    "title": "Fix leaking pipe",
                    "description": "desc",
                    "budget": "1500.00",
                    "location": "Mumbai",
                },
            )
    finally:
        await _teardown()

    assert response.status_code == 201
    assert response.json()["image_url"] is None


async def test_unauthenticated_user_cannot_create_job(db_session: AsyncSession) -> None:
    category_id = await _seed_category(db_session)
    async with await _client() as client:
        response = await client.post(
            "/api/v1/jobs",
            json={
                "category_id": str(category_id),
                "title": "Fix leaking pipe",
                "description": "desc",
                "budget": "1500.00",
                "location": "Mumbai",
            },
        )
    assert response.status_code == 401


async def test_worker_cannot_create_job(db_session: AsyncSession) -> None:
    worker_user = await _seed_worker_only(db_session)
    category_id = await _seed_category(db_session)
    _authenticate_as(worker_user, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/jobs",
                json={
                    "category_id": str(category_id),
                    "title": "Fix leaking pipe",
                    "description": "desc",
                    "budget": "1500.00",
                    "location": "Mumbai",
                },
            )
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_invalid_job_data_rejected(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/jobs",
                json={"category_id": str(category_id), "description": "desc", "location": "Mumbai"},
            )
    finally:
        await _teardown()
    assert response.status_code == 422


async def test_job_ownership_automatically_assigned_not_client_supplied(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            # hiring_party_id isn't even a field on JobCreate - attempting
            # to supply one is rejected outright (extra="forbid"), proving
            # there is no way to spoof ownership at creation.
            response = await client.post(
                "/api/v1/jobs",
                json={
                    "category_id": str(category_id),
                    "title": "Fix leaking pipe",
                    "description": "desc",
                    "budget": "1500.00",
                    "location": "Mumbai",
                    "hiring_party_id": str(other_business.user_id),
                },
            )
    finally:
        await _teardown()
    assert response.status_code == 422


# =====================================================================
# Job modification (Step 9, items 10-13)
# =====================================================================


async def test_owner_can_update_job(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={"title": "Updated title"})
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"

    refetched = await JobRepository(db_session).get_by_id(job.job_id)
    assert refetched is not None
    assert refetched.title == "Updated title"


async def test_different_business_cannot_update_job(db_session: AsyncSession) -> None:
    owner = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, owner.user_id, category_id)
    _authenticate_as(other_business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={"title": "Hijacked"})
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_different_business_cannot_update_job_with_empty_body(db_session: AsyncSession) -> None:
    """Regression test (Task 13 audit): an empty PATCH body `{}` used to skip
    the ownership check entirely and fall through to an unauthenticated-
    equivalent read, letting a non-owner business get 200 instead of 403."""
    owner = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, owner.user_id, category_id)
    _authenticate_as(other_business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={})
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_worker_cannot_update_job(db_session: AsyncSession) -> None:
    owner = await _seed_business(db_session)
    worker_user = await _seed_worker_only(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, owner.user_id, category_id)
    _authenticate_as(worker_user, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={"title": "Hijacked"})
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_unauthenticated_user_cannot_update_job(db_session: AsyncSession) -> None:
    owner = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, owner.user_id, category_id)

    async with await _client() as client:
        response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={"title": "Hijacked"})
    assert response.status_code == 401


# =====================================================================
# Job lifecycle / status (Step 9, items 14-16)
# =====================================================================


async def test_owner_can_publish_draft_job(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="draft")
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={"status": "open"})
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["status"] == "open"


async def test_unauthorized_user_cannot_change_job_status(db_session: AsyncSession) -> None:
    owner = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, owner.user_id, category_id, status="draft")
    _authenticate_as(other_business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={"status": "open"})
    finally:
        await _teardown()
    assert response.status_code == 403

    unchanged = await JobRepository(db_session).get_by_id(job.job_id)
    assert unchanged is not None
    assert unchanged.status == "draft"


async def test_invalid_lifecycle_transition_rejected(db_session: AsyncSession) -> None:
    """Mirrors Task 11's own "Completed -> Open should not be possible"
    example: here, closed -> open."""
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="closed")
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(f"/api/v1/jobs/{job.job_id}", json={"status": "open"})
    finally:
        await _teardown()

    assert response.status_code == 409

    unchanged = await JobRepository(db_session).get_by_id(job.job_id)
    assert unchanged is not None
    assert unchanged.status == "closed"
