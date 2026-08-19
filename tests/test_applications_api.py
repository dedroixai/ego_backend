"""Integration tests for the Job Application API
(POST/GET /api/v1/jobs/{job_id}/applications, GET /api/v1/applications/me,
GET/DELETE/PATCH /api/v1/applications/{application_id}).

Mirrors the strategy established in tests/test_jobs_api.py (see
tests/test_users_api.py's module docstring for the full rationale).
Skipped automatically if TEST_DATABASE_URL isn't configured; never
touches Supabase DATABASE_URL.
"""

import uuid
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.dependencies import get_db
from app.main import app
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.job_category_repository import JobCategoryRepository
from app.repositories.job_match_repository import JobMatchRepository
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


async def _seed_worker(db_session: AsyncSession) -> User:
    user = await _seed_user(db_session, role="worker")
    await WorkerRepository(db_session).create(user_id=user.user_id, name="Jane", skills=[], service_locations=[])
    await db_session.commit()
    return user


async def _seed_category(db_session: AsyncSession) -> uuid.UUID:
    category = await JobCategoryRepository(db_session).create(name=f"Category {uuid.uuid4()}")
    await db_session.commit()
    return category.category_id


async def _seed_job(
    db_session: AsyncSession, hiring_party_id: uuid.UUID, category_id: uuid.UUID, *, status: str = "open"
) -> Job:
    job = await JobRepository(db_session).create(
        hiring_party_id=hiring_party_id,
        category_id=category_id,
        title="Fix leaking pipe",
        description="desc",
        budget=Decimal("1500.00"),
        location="Mumbai",
        status=status,
    )
    await db_session.commit()
    return job


async def _seed_application(
    db_session: AsyncSession, job_id: uuid.UUID, worker_id: uuid.UUID, *, status: str = "pending"
) -> JobMatch:
    application = await JobMatchRepository(db_session).create(job_id=job_id, worker_id=worker_id, status=status)
    await db_session.commit()
    return application


def _authenticate_as(user: User, db_session: AsyncSession) -> None:
    async def override_get_current_user() -> User:
        return user

    async def override_get_db() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _teardown() -> None:
    app.dependency_overrides.clear()


# =====================================================================
# Worker - apply (Step 12, items 1-6)
# =====================================================================


async def test_unauthenticated_user_cannot_apply(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)

    async with await _client() as client:
        response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
    assert response.status_code == 401


async def test_business_user_cannot_apply(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    _authenticate_as(other_business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_worker_can_apply_to_open_job(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["worker_id"] == str(worker.user_id)
    assert body["job_id"] == str(job.job_id)


async def test_worker_cannot_apply_to_nonexistent_job(db_session: AsyncSession) -> None:
    worker = await _seed_worker(db_session)
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.post(f"/api/v1/jobs/{uuid.uuid4()}/applications")
    finally:
        await _teardown()
    assert response.status_code == 404


async def test_worker_cannot_apply_when_job_not_open(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    draft_job = await _seed_job(db_session, business.user_id, category_id, status="draft")
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.post(f"/api/v1/jobs/{draft_job.job_id}/applications")
    finally:
        await _teardown()
    assert response.status_code == 422


async def test_worker_cannot_apply_twice(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            first = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
            second = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()

    assert first.status_code == 201
    assert second.status_code == 409


# =====================================================================
# Worker - view / withdraw (Step 12, items 7-9)
# =====================================================================


async def test_worker_can_view_their_applications(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/applications/me")
    finally:
        await _teardown()

    assert response.status_code == 200
    ids = {a["match_id"] for a in response.json()}
    assert str(application.match_id) in ids


async def test_worker_cannot_view_another_workers_application(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    other_worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(other_worker, db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/applications/{application.match_id}")
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_worker_can_withdraw_application(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.delete(f"/api/v1/applications/{application.match_id}")
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"

    # Not physically deleted - the row still exists.
    persisted = await JobMatchRepository(db_session).get_by_id(application.match_id)
    assert persisted is not None
    assert persisted.status == "withdrawn"


# =====================================================================
# Business (Step 12, items 10-13)
# =====================================================================


async def test_business_can_view_applications_for_own_job(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()

    assert response.status_code == 200
    ids = {a["match_id"] for a in response.json()}
    assert str(application.match_id) in ids


async def test_business_cannot_view_another_businesss_applications(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(other_business, db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_worker_cannot_view_business_applicant_list(db_session: AsyncSession) -> None:
    """Task 19 Step 18 security test - a Worker (no Business profile) must
    never reach the Business-only applicant-listing endpoint, even for a
    job it legitimately applied to itself."""
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()
    assert response.status_code == 403


async def test_business_can_accept_application(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                f"/api/v1/applications/{application.match_id}", json={"status": "accepted"}
            )
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    # Task 19 Step 19 - verify the actual persisted row, not just the API
    # response: correct record, correct new status, correct job/worker
    # relationship (worker/job ids on the row are unchanged by the review).
    persisted = await JobMatchRepository(db_session).get_by_id(application.match_id)
    assert persisted is not None
    assert persisted.status == "accepted"
    assert persisted.job_id == job.job_id
    assert persisted.worker_id == worker.user_id


async def test_business_can_reject_application(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                f"/api/v1/applications/{application.match_id}", json={"status": "rejected"}
            )
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    persisted = await JobMatchRepository(db_session).get_by_id(application.match_id)
    assert persisted is not None
    assert persisted.status == "rejected"


async def test_business_cannot_modify_unauthorized_application(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    other_business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(other_business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                f"/api/v1/applications/{application.match_id}", json={"status": "accepted"}
            )
    finally:
        await _teardown()
    assert response.status_code == 403

    unchanged = await JobMatchRepository(db_session).get_by_id(application.match_id)
    assert unchanged is not None
    assert unchanged.status == "pending"


async def test_business_applicant_list_includes_worker_summary(db_session: AsyncSession) -> None:
    """Task 19 - GET /jobs/{job_id}/applications must return enough for a
    Business to identify the applicant (name, skills, etc.), not just an
    opaque worker_id - see app/schemas/job_match.py's
    JobMatchWithWorkerResponse."""
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()

    assert response.status_code == 200
    body = response.json()[0]
    assert body["worker"]["user_id"] == str(worker.user_id)
    assert body["worker"]["name"] == "Jane"
    # Never leaked: bank_details is not on WorkerSummary at all.
    assert "bank_details" not in body["worker"]


async def test_application_detail_includes_worker_summary_for_business_viewer(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.get(f"/api/v1/applications/{application.match_id}")
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json()["worker"]["name"] == "Jane"


async def test_invalid_review_transition_rejected(db_session: AsyncSession) -> None:
    """A rejected application cannot later be accepted - Task 12 Step 7's
    own example question, resolved conservatively (no transition out of a
    terminal state) - see docs/application-api.md."""
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id, status="rejected")
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.patch(
                f"/api/v1/applications/{application.match_id}", json={"status": "accepted"}
            )
    finally:
        await _teardown()
    assert response.status_code == 409


# =====================================================================
# Security (Step 12, items 14-15)
# =====================================================================


async def test_application_ownership_always_derived_from_authenticated_worker(db_session: AsyncSession) -> None:
    """POST /jobs/{job_id}/applications takes no request body at all - a
    client cannot supply a worker_id even if they try; any JSON body sent
    is simply not read by the route (no Pydantic body parameter exists)."""
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    other_worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                f"/api/v1/jobs/{job.job_id}/applications",
                json={"worker_id": str(other_worker.user_id)},
            )
    finally:
        await _teardown()

    assert response.status_code == 201
    assert response.json()["worker_id"] == str(worker.user_id)  # never other_worker


async def test_business_review_ignores_client_supplied_ids(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            # business_id/worker_id aren't fields on JobMatchUpdate at all -
            # attempting to supply them is rejected outright (extra="forbid").
            response = await client.patch(
                f"/api/v1/applications/{application.match_id}",
                json={"status": "accepted", "business_id": str(uuid.uuid4())},
            )
    finally:
        await _teardown()
    assert response.status_code == 422


# =====================================================================
# End-to-end (Task 19 Step 17) - the full user journey in one test,
# against the real disposable Postgres (never Supabase DATABASE_URL),
# each step re-authenticating as whichever party would really make that
# specific request (no real Firebase project in this sandbox - dependency
# override on `get_current_user` is the established substitute, same as
# every other test in this file and every prior task's backend work).
# =====================================================================


async def test_end_to_end_business_reviews_worker_application(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)

    # Step 1-2: Business creates (seeds, standing in for POST /jobs -
    # already covered end to end in tests/test_jobs_api.py) an open job.
    job = await _seed_job(db_session, business.user_id, category_id, status="open")

    # Step 3-5: Worker finds the job and applies.
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            apply_response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()
    assert apply_response.status_code == 201
    match_id = apply_response.json()["match_id"]
    assert apply_response.json()["status"] == "pending"

    # Step 6: Business opens My Jobs -> Job -> Applicants.
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            applicants_response = await client.get(f"/api/v1/jobs/{job.job_id}/applications")
    finally:
        await _teardown()
    assert applicants_response.status_code == 200
    applicants = applicants_response.json()
    assert len(applicants) == 1
    assert applicants[0]["match_id"] == match_id
    assert applicants[0]["worker"]["name"] == "Jane"  # see _seed_worker

    # Step 7: Business opens the Worker's application.
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            detail_response = await client.get(f"/api/v1/applications/{match_id}")
    finally:
        await _teardown()
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "pending"

    # Step 8: Business accepts.
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            accept_response = await client.patch(f"/api/v1/applications/{match_id}", json={"status": "accepted"})
    finally:
        await _teardown()
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    # Step 9-10: Worker opens My Applications and sees the updated status -
    # a fresh GET, not a cached/local value, proving the change is really
    # persisted in Postgres and re-readable, not just echoed back once.
    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            my_applications_response = await client.get("/api/v1/applications/me")
    finally:
        await _teardown()
    assert my_applications_response.status_code == 200
    [my_application] = [a for a in my_applications_response.json() if a["match_id"] == match_id]
    assert my_application["status"] == "accepted"

    # Step 19: verify the actual database row directly, not just API responses.
    persisted = await JobMatchRepository(db_session).get_by_id(uuid.UUID(match_id))
    assert persisted is not None
    assert persisted.status == "accepted"
    assert persisted.job_id == job.job_id
    assert persisted.worker_id == worker.user_id
