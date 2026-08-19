"""Integration tests for Task 21's notification events - application
created/accepted/rejected triggering a `Notification` row + an FCM push
attempt. Mirrors the strategy established in tests/test_applications_api.py.

No FCM emulator exists (unlike Firebase Storage's - see
docs/storage-architecture.md) - `firebase_admin.messaging.send_each` is
mocked (`unittest.mock.patch`) rather than actually contacting Firebase,
consistent with never sending real pushes from an automated test run.
What's verified here is this app's OWN logic: the right `Notification`
row is created for the right recipient, the right FCM `Message`s are
constructed and handed to `send_each`, invalid-token responses are
handled correctly, and a notification-layer failure never undoes the
already-committed business transaction that triggered it.

Skipped automatically if TEST_DATABASE_URL isn't configured; never
touches Supabase DATABASE_URL.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.dependencies import get_db
from app.main import app
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.user import User
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.device_token_repository import DeviceTokenRepository
from app.repositories.job_category_repository import JobCategoryRepository
from app.repositories.job_match_repository import JobMatchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.notification_repository import NotificationRepository
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


async def _seed_device_token(db_session: AsyncSession, user_id: uuid.UUID, token: str) -> None:
    await DeviceTokenRepository(db_session).create(user_id=user_id, token=token, platform="android")
    await db_session.commit()


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


@dataclass
class _FakeSendResponse:
    success: bool
    exception: Exception | None = None


@dataclass
class _FakeBatchResponse:
    responses: list
    success_count: int


def _all_succeed(messages, **_kwargs):
    return _FakeBatchResponse(responses=[_FakeSendResponse(success=True) for _ in messages], success_count=len(messages))


# =====================================================================
# 1-2. Application creation triggers a notification for the CORRECT business
# =====================================================================


async def test_application_creation_notifies_the_owning_business(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    await _seed_device_token(db_session, business.user_id, "business-device-token")
    _authenticate_as(worker, db_session)

    with patch("app.services.push_service.messaging.send_each", side_effect=_all_succeed) as mock_send:
        try:
            async with await _client() as client:
                response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
        finally:
            await _teardown()

    assert response.status_code == 201
    match_id = uuid.UUID(response.json()["match_id"])

    notifications = await NotificationRepository(db_session).list_by_user(business.user_id)
    assert len(notifications) == 1
    assert notifications[0].type == "APPLICATION_RECEIVED"
    assert notifications[0].entity_type == "job_match"
    assert notifications[0].entity_id == match_id
    assert "Fix leaking pipe" in notifications[0].message
    mock_send.assert_called_once()


async def test_business_b_does_not_receive_business_as_application_notification(db_session: AsyncSession) -> None:
    """Task 21 Step 20 test 3."""
    business_a = await _seed_business(db_session)
    business_b = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business_a.user_id, category_id, status="open")
    _authenticate_as(worker, db_session)

    with patch("app.services.push_service.messaging.send_each", side_effect=_all_succeed):
        try:
            async with await _client() as client:
                response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
        finally:
            await _teardown()
    assert response.status_code == 201

    business_a_notifications = await NotificationRepository(db_session).list_by_user(business_a.user_id)
    business_b_notifications = await NotificationRepository(db_session).list_by_user(business_b.user_id)
    assert len(business_a_notifications) == 1
    assert len(business_b_notifications) == 0


# =====================================================================
# 4-5. Accept/reject trigger a Worker notification
# =====================================================================


async def test_application_acceptance_notifies_the_worker(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)

    with patch("app.services.push_service.messaging.send_each", side_effect=_all_succeed):
        try:
            async with await _client() as client:
                response = await client.patch(
                    f"/api/v1/applications/{application.match_id}", json={"status": "accepted"}
                )
        finally:
            await _teardown()
    assert response.status_code == 200

    notifications = await NotificationRepository(db_session).list_by_user(worker.user_id)
    assert len(notifications) == 1
    assert notifications[0].type == "APPLICATION_ACCEPTED"
    assert notifications[0].entity_id == application.match_id


async def test_application_rejection_notifies_the_worker(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id)
    application = await _seed_application(db_session, job.job_id, worker.user_id)
    _authenticate_as(business, db_session)

    with patch("app.services.push_service.messaging.send_each", side_effect=_all_succeed):
        try:
            async with await _client() as client:
                response = await client.patch(
                    f"/api/v1/applications/{application.match_id}", json={"status": "rejected"}
                )
        finally:
            await _teardown()
    assert response.status_code == 200

    notifications = await NotificationRepository(db_session).list_by_user(worker.user_id)
    assert len(notifications) == 1
    assert notifications[0].type == "APPLICATION_REJECTED"


# =====================================================================
# 6. Invalid token is handled - removed, not repeatedly retried, and
#    other tokens are unaffected.
# =====================================================================


async def test_invalid_device_token_is_removed_not_the_whole_users_tokens(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    await _seed_device_token(db_session, business.user_id, "stale-token")
    await _seed_device_token(db_session, business.user_id, "valid-token")
    _authenticate_as(worker, db_session)

    from firebase_admin import messaging

    def _one_invalid(messages, **_kwargs):
        responses = []
        for message in messages:
            if message.token == "stale-token":
                responses.append(_FakeSendResponse(success=False, exception=messaging.UnregisteredError("gone")))
            else:
                responses.append(_FakeSendResponse(success=True))
        return _FakeBatchResponse(responses=responses, success_count=len(messages) - 1)

    with patch("app.services.push_service.messaging.send_each", side_effect=_one_invalid):
        try:
            async with await _client() as client:
                response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
        finally:
            await _teardown()
    assert response.status_code == 201

    remaining = await DeviceTokenRepository(db_session).list_by_user(business.user_id)
    remaining_values = {t.token for t in remaining}
    assert remaining_values == {"valid-token"}  # stale-token removed, valid-token untouched


# =====================================================================
# 7. Notification failure does not roll back the business transaction.
# =====================================================================


async def test_notification_failure_does_not_roll_back_the_application(db_session: AsyncSession) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    _authenticate_as(worker, db_session)

    with patch("app.services.push_service.messaging.send_each", side_effect=RuntimeError("FCM is down")):
        try:
            async with await _client() as client:
                response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
        finally:
            await _teardown()

    # The application itself succeeded despite the notification layer
    # blowing up completely.
    assert response.status_code == 201
    assert response.json()["status"] == "pending"

    persisted = await JobMatchRepository(db_session).get_by_job_and_worker(job.job_id, worker.user_id)
    assert persisted is not None
    assert persisted.status == "pending"


# =====================================================================
# End-to-end: the full apply -> accept journey, chaining both MVP
# events through the real HTTP routes (including the notification-
# history endpoints Task 21 Step 14 wired up), mirroring Task 19's
# test_end_to_end_business_reviews_worker_application.
# =====================================================================


async def test_end_to_end_apply_then_accept_notifies_both_sides_and_supports_multi_device(
    db_session: AsyncSession,
) -> None:
    business = await _seed_business(db_session)
    worker = await _seed_worker(db_session)
    category_id = await _seed_category(db_session)
    job = await _seed_job(db_session, business.user_id, category_id, status="open")
    await _seed_device_token(db_session, business.user_id, "business-device-1")
    await _seed_device_token(db_session, business.user_id, "business-device-2")

    # 1. Worker applies -> business is notified (APPLICATION_RECEIVED),
    #    on BOTH of its registered devices.
    _authenticate_as(worker, db_session)
    with patch("app.services.push_service.messaging.send_each", side_effect=_all_succeed) as mock_send:
        try:
            async with await _client() as client:
                apply_response = await client.post(f"/api/v1/jobs/{job.job_id}/applications")
        finally:
            await _teardown()
    assert apply_response.status_code == 201
    match_id = uuid.UUID(apply_response.json()["match_id"])
    sent_messages = mock_send.call_args.args[0]
    assert {message.token for message in sent_messages} == {"business-device-1", "business-device-2"}

    # Business can see the notification via the real GET /notifications route.
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            list_response = await client.get("/api/v1/notifications")
    finally:
        await _teardown()
    assert list_response.status_code == 200
    business_notifications = list_response.json()
    assert len(business_notifications) == 1
    assert business_notifications[0]["type"] == "APPLICATION_RECEIVED"
    assert business_notifications[0]["entity_id"] == str(match_id)

    # 2. Business accepts -> worker is notified (APPLICATION_ACCEPTED).
    _authenticate_as(business, db_session)
    with patch("app.services.push_service.messaging.send_each", side_effect=_all_succeed):
        try:
            async with await _client() as client:
                accept_response = await client.patch(f"/api/v1/applications/{match_id}", json={"status": "accepted"})
        finally:
            await _teardown()
    assert accept_response.status_code == 200

    _authenticate_as(worker, db_session)
    try:
        async with await _client() as client:
            worker_list_response = await client.get("/api/v1/notifications")
    finally:
        await _teardown()
    assert worker_list_response.status_code == 200
    worker_notifications = worker_list_response.json()
    assert len(worker_notifications) == 1
    assert worker_notifications[0]["type"] == "APPLICATION_ACCEPTED"
    assert worker_notifications[0]["entity_id"] == str(match_id)

    # The business's own notification history is unaffected by the accept.
    _authenticate_as(business, db_session)
    try:
        async with await _client() as client:
            final_business_list = await client.get("/api/v1/notifications")
    finally:
        await _teardown()
    assert len(final_business_list.json()) == 1
