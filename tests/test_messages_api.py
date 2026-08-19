"""Integration tests for the Chat/Messaging API
(POST /api/v1/messages, GET /api/v1/messages/conversations,
GET /api/v1/messages/thread/{other_user_id}).

Mirrors the strategy established in tests/test_jobs_api.py (see
tests/test_users_api.py's module docstring for the full rationale).
Skipped automatically if TEST_DATABASE_URL isn't configured; never
touches Supabase DATABASE_URL.
"""

import uuid
from datetime import UTC, datetime, timedelta
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
from app.repositories.message_repository import MessageRepository
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


async def _seed_job(db_session: AsyncSession, hiring_party_id: uuid.UUID, category_id: uuid.UUID) -> Job:
    job = await JobRepository(db_session).create(
        hiring_party_id=hiring_party_id,
        category_id=category_id,
        title="Fix leaking pipe",
        description="desc",
        budget=Decimal("1500.00"),
        location="Mumbai",
        status="open",
    )
    await db_session.commit()
    return job


async def _seed_match(
    db_session: AsyncSession, job_id: uuid.UUID, worker_id: uuid.UUID, *, status: str
) -> JobMatch:
    match = await JobMatchRepository(db_session).create(job_id=job_id, worker_id=worker_id, status=status)
    await db_session.commit()
    return match


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
# Job-less messages ("contact this person directly")
# =====================================================================


async def test_job_less_message_succeeds_with_no_match_or_job(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/messages", json={"receiver_id": str(worker.user_id), "content": "Are you free this week?"}
            )
    finally:
        await _teardown()

    assert response.status_code == 201
    body = response.json()
    assert body["job_id"] is None
    assert body["sender_id"] == str(business.user_id)
    assert body["receiver_id"] == str(worker.user_id)
    assert body["content"] == "Are you free this week?"


async def test_unauthenticated_user_cannot_send_message(db_session: AsyncSession) -> None:
    worker = await _seed_worker(db_session)
    async with await _client() as client:
        response = await client.post(
            "/api/v1/messages", json={"receiver_id": str(worker.user_id), "content": "hello"}
        )
    assert response.status_code == 401


async def test_cannot_message_yourself(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/messages", json={"receiver_id": str(business.user_id), "content": "hello"}
            )
    finally:
        await _teardown()
    assert response.status_code == 422  # BusinessRuleViolationError (see app/api/exception_handlers.py)


async def test_cannot_message_nonexistent_user(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/messages", json={"receiver_id": str(uuid.uuid4()), "content": "hello"}
            )
    finally:
        await _teardown()
    assert response.status_code == 404


# =====================================================================
# Job-scoped messages (require an accepted JobMatch)
# =====================================================================


async def test_job_scoped_message_rejected_without_accepted_match(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    await _seed_match(db_session, job.job_id, worker.user_id, status="pending")

    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/messages",
                json={"receiver_id": str(worker.user_id), "content": "hello", "job_id": str(job.job_id)},
            )
    finally:
        await _teardown()

    assert response.status_code == 403


async def test_job_scoped_message_succeeds_after_accepted_match(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    await _seed_match(db_session, job.job_id, worker.user_id, status="accepted")

    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/messages",
                json={
                    "receiver_id": str(worker.user_id),
                    "content": "Can you start Monday?",
                    "job_id": str(job.job_id),
                },
            )
    finally:
        await _teardown()

    assert response.status_code == 201
    assert response.json()["job_id"] == str(job.job_id)


async def test_job_scoped_message_works_from_worker_side_too(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    await _seed_match(db_session, job.job_id, worker.user_id, status="accepted")

    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/messages",
                json={"receiver_id": str(business.user_id), "content": "Yes, Monday works!", "job_id": str(job.job_id)},
            )
    finally:
        await _teardown()

    assert response.status_code == 201


async def test_job_scoped_message_rejected_for_nonexistent_job(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.post(
                "/api/v1/messages",
                json={"receiver_id": str(worker.user_id), "content": "hello", "job_id": str(uuid.uuid4())},
            )
    finally:
        await _teardown()
    assert response.status_code == 404


# =====================================================================
# Reading a thread
# =====================================================================


async def test_thread_returns_only_messages_between_the_two_users(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    other_worker = await _seed_worker(db_session)

    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            await client.post("/api/v1/messages", json={"receiver_id": str(worker.user_id), "content": "hi worker"})
            await client.post(
                "/api/v1/messages", json={"receiver_id": str(other_worker.user_id), "content": "hi other worker"}
            )
            thread_response = await client.get(f"/api/v1/messages/thread/{worker.user_id}")
    finally:
        await _teardown()

    assert thread_response.status_code == 200
    messages = thread_response.json()
    assert len(messages) == 1
    assert messages[0]["content"] == "hi worker"


async def test_job_scoped_and_job_less_threads_with_same_person_are_separate(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    await _seed_match(db_session, job.job_id, worker.user_id, status="accepted")

    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            await client.post(
                "/api/v1/messages", json={"receiver_id": str(worker.user_id), "content": "general hello"}
            )
            await client.post(
                "/api/v1/messages",
                json={"receiver_id": str(worker.user_id), "content": "about the job", "job_id": str(job.job_id)},
            )
            general_thread = await client.get(f"/api/v1/messages/thread/{worker.user_id}")
            job_thread = await client.get(f"/api/v1/messages/thread/{worker.user_id}?job_id={job.job_id}")
    finally:
        await _teardown()

    assert [m["content"] for m in general_thread.json()] == ["general hello"]
    assert [m["content"] for m in job_thread.json()] == ["about the job"]


async def test_thread_requires_authentication(db_session: AsyncSession) -> None:
    worker = await _seed_worker(db_session)
    async with await _client() as client:
        response = await client.get(f"/api/v1/messages/thread/{worker.user_id}")
    assert response.status_code == 401


# =====================================================================
# Conversation list
# =====================================================================


async def test_conversations_lists_distinct_counterparts_most_recent_first(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker_a = await _seed_worker(db_session)
    worker_b = await _seed_worker(db_session)

    # Seeded directly with explicit, clearly-separated timestamps rather
    # than three real `POST`s: Postgres `now()` (this model's
    # `server_default`) is transaction-start-time, not wall-clock-per-
    # statement - every row created in `db_session`'s single
    # per-test transaction (see conftest.py's `db_session` fixture)
    # would otherwise get the IDENTICAL timestamp, making "most recent
    # first" genuinely untestable here even though real, separate-request
    # traffic wouldn't collide like this.
    now = datetime.now(UTC)
    messages = MessageRepository(db_session)
    await messages.create(sender_id=business.user_id, receiver_id=worker_a.user_id, content="first", timestamp=now)
    await messages.create(
        sender_id=business.user_id, receiver_id=worker_b.user_id, content="second", timestamp=now + timedelta(minutes=1)
    )
    await messages.create(
        sender_id=business.user_id,
        receiver_id=worker_a.user_id,
        content="third, latest with A",
        timestamp=now + timedelta(minutes=2),
    )
    await db_session.commit()

    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/messages/conversations")
    finally:
        await _teardown()

    assert response.status_code == 200
    conversations = response.json()
    assert len(conversations) == 2
    # Most-recently-active thread first.
    assert conversations[0]["other_user_id"] == str(worker_a.user_id)
    assert conversations[0]["last_message"]["content"] == "third, latest with A"
    assert conversations[1]["other_user_id"] == str(worker_b.user_id)


async def test_conversations_never_leak_other_users_threads(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    another_business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)

    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            await client.post("/api/v1/messages", json={"receiver_id": str(worker.user_id), "content": "hi"})
    finally:
        await _teardown()

    _authenticate_as(another_business, db_session)
    try:
        async with await _client() as client:
            response = await client.get("/api/v1/messages/conversations")
    finally:
        await _teardown()

    assert response.status_code == 200
    assert response.json() == []
