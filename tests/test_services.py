"""Tests for the service / business-logic layer.

Runs against the same disposable local test database as
tests/test_repositories.py (see conftest.py / docs/repository-layer.md) -
never against the app's Supabase DATABASE_URL. Skipped automatically if
TEST_DATABASE_URL isn't configured.

Tests verify BUSINESS BEHAVIOR (ownership, duplicate prevention,
transactional coordination, documented gaps) rather than SQL details -
those are already covered in test_repositories.py.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.business_repository import HiringPartyRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.worker_repository import WorkerRepository
from app.services.business_service import HiringPartyService
from app.services.completion_verification_service import CompletionVerificationService
from app.services.exceptions import (
    BusinessRuleViolationError,
    DuplicateOperationError,
    InvalidStateTransitionError,
    ResourceNotFoundError,
    UnauthorizedOperationError,
)
from app.services.job_category_service import JobCategoryService
from app.services.job_match_service import JobMatchService
from app.services.job_service import JobService
from app.services.message_service import MessageService
from app.services.rating_service import RatingService
from app.services.user_service import UserService
from app.services.worker_service import WorkerService


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


async def _make_user(session: AsyncSession, *, role: str = "worker") -> uuid.UUID:
    user = await UserRepository(session).create(phone=_phone(), language="en", role=role)
    return user.user_id


async def _make_worker(session: AsyncSession) -> uuid.UUID:
    user_id = await _make_user(session, role="worker")
    worker = await WorkerService(session).create_profile(user_id, user_id, name="Test Worker")
    return worker.user_id


async def _make_hiring_party(session: AsyncSession) -> uuid.UUID:
    user_id = await _make_user(session, role="hiring_party")
    hp = await HiringPartyService(session).create_profile(user_id, user_id, account_type="business")
    return hp.user_id


async def _make_category(session: AsyncSession) -> uuid.UUID:
    category = await JobCategoryService(session).create_category(f"Category {uuid.uuid4()}")
    return category.category_id


async def _make_job(session: AsyncSession, hiring_party_id: uuid.UUID, category_id: uuid.UUID) -> uuid.UUID:
    # No `status` kwarg - Task 11 changed JobService.create_job to always
    # start a job as "draft" internally. See app/services/job_service.py.
    job = await JobService(session).create_job(
        hiring_party_id,
        hiring_party_id,
        category_id=category_id,
        title="Fix leaking pipe",
        description="desc",
        budget=Decimal("100"),
        location="Mumbai",
    )
    return job.job_id


# --- 1. Successful operations -------------------------------------------


async def test_create_worker_profile_success(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session, role="worker")
    worker = await WorkerService(db_session).create_profile(user_id, user_id, name="Jane")
    assert worker.name == "Jane"
    assert worker.user_id == user_id


async def test_create_job_success(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job = await JobService(db_session).create_job(
        hiring_party_id,
        hiring_party_id,
        category_id=category_id,
        title="Fix leaking pipe",
        description="desc",
        budget=Decimal("1500"),
        location="Mumbai",
    )
    assert job.hiring_party_id == hiring_party_id
    assert job.title == "Fix leaking pipe"
    assert job.status == "draft"  # Task 11: every new job starts as "draft"


# --- 2. Invalid operations ------------------------------------------------


async def test_cannot_message_yourself(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)

    with pytest.raises(BusinessRuleViolationError):
        await MessageService(db_session).send_message(hiring_party_id, hiring_party_id, "hello", job_id=job_id)


async def test_cannot_rate_yourself(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)

    with pytest.raises(BusinessRuleViolationError):
        await RatingService(db_session).submit_rating(
            job_id, hiring_party_id, hiring_party_id, to_user_id=hiring_party_id, score=5
        )


# --- 3. Ownership violations ---------------------------------------------


async def test_cannot_update_another_users_profile(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session)
    other_user_id = await _make_user(db_session)

    with pytest.raises(UnauthorizedOperationError):
        await UserService(db_session).update_profile(user_id, other_user_id, language="hi")


async def test_cannot_update_another_hiring_partys_job(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)
    other_hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)

    with pytest.raises(UnauthorizedOperationError):
        await JobService(db_session).update_job(job_id, other_hiring_party_id, title="Hijacked title")


async def test_worker_cannot_withdraw_another_workers_application(db_session: AsyncSession) -> None:
    """Updated by Task 12: JobMatchService.respond_to_match (Task 7) was
    superseded by the more specific withdraw_application/review_application
    - see app/services/job_match_service.py and docs/application-api.md."""
    hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)
    worker_id = await _make_worker(db_session)
    other_worker_id = await _make_worker(db_session)

    from app.repositories.job_match_repository import JobMatchRepository

    match = await JobMatchRepository(db_session).create(job_id=job_id, worker_id=worker_id, status="pending")
    await db_session.commit()

    with pytest.raises(UnauthorizedOperationError):
        await JobMatchService(db_session).withdraw_application(match.match_id, other_worker_id)


# --- 4. Invalid status transitions ---------------------------------------


async def test_job_status_transitions_are_now_validated(db_session: AsyncSession) -> None:
    """Updated by Task 11: unlike when this test was first written (Task 7 -
    see git history / docs/service-layer.md for that original reasoning),
    Job.status now has an adopted, flagged-as-provisional vocabulary and a
    validated transition graph (docs/job-lifecycle.md). A new job starts
    "draft"; "draft" -> "open" (publish) is valid; "open" -> "draft"
    (Task 11's own "Completed -> Open should not be possible" example,
    generalized) is not."""
    hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)

    published = await JobService(db_session).update_status(job_id, hiring_party_id, status="open")
    assert published.status == "open"

    with pytest.raises(InvalidStateTransitionError):
        await JobService(db_session).update_status(job_id, hiring_party_id, status="draft")


# --- 5. Missing related entities ------------------------------------------


async def test_create_job_with_nonexistent_category_raises_not_found(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)

    with pytest.raises(ResourceNotFoundError):
        await JobService(db_session).create_job(
            hiring_party_id,
            hiring_party_id,
            category_id=uuid.uuid4(),
            title="Fix leaking pipe",
            description="desc",
            budget=Decimal("100"),
            location="Mumbai",
        )


async def test_create_worker_profile_for_nonexistent_user_raises_not_found(db_session: AsyncSession) -> None:
    ghost_user_id = uuid.uuid4()

    with pytest.raises(ResourceNotFoundError):
        await WorkerService(db_session).create_profile(ghost_user_id, ghost_user_id, name="Ghost")


async def test_send_message_to_nonexistent_job_raises_not_found(db_session: AsyncSession) -> None:
    sender_id = await _make_user(db_session)
    receiver_id = await _make_user(db_session)

    with pytest.raises(ResourceNotFoundError):
        await MessageService(db_session).send_message(sender_id, receiver_id, "hello", job_id=uuid.uuid4())


# --- 6. Duplicate operations -----------------------------------------------


async def test_cannot_create_worker_profile_twice(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session, role="worker")
    await WorkerService(db_session).create_profile(user_id, user_id, name="Jane")

    with pytest.raises(DuplicateOperationError):
        await WorkerService(db_session).create_profile(user_id, user_id, name="Jane Again")


async def test_cannot_rate_same_job_direction_twice(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)
    worker_user_id = await _make_user(db_session, role="worker")
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)

    rating_service = RatingService(db_session)
    await rating_service.submit_rating(
        job_id, hiring_party_id, hiring_party_id, to_user_id=worker_user_id, score=5
    )

    with pytest.raises(DuplicateOperationError):
        await rating_service.submit_rating(
            job_id, hiring_party_id, hiring_party_id, to_user_id=worker_user_id, score=3
        )


async def test_cannot_initiate_completion_verification_twice(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)

    service = CompletionVerificationService(db_session)
    await service.initiate_verification(job_id, hiring_party_id, method="qr")

    with pytest.raises(DuplicateOperationError):
        await service.initiate_verification(job_id, hiring_party_id, method="qr")


# --- 7. Transaction rollback ------------------------------------------------


async def test_duplicate_category_name_rolls_back_and_session_stays_usable(db_session: AsyncSession) -> None:
    """Unlike WorkerService (which pre-checks for duplicates before writing),
    JobCategoryService relies entirely on the DB UNIQUE constraint + the
    repository/service error-translation-and-rollback path - a genuine
    exercise of BaseService._rollback_and_raise, not a proactive guard."""
    service = JobCategoryService(db_session)
    name = f"Category {uuid.uuid4()}"
    await service.create_category(name)

    with pytest.raises(DuplicateOperationError):
        await service.create_category(name)

    # The session must still be usable after the rollback - prove it by
    # successfully creating something else immediately afterward.
    other = await service.create_category(f"Category {uuid.uuid4()}")
    assert other.name != name

    categories = await service.list_categories(limit=1000)
    assert sum(1 for c in categories if c.name == name) == 1


# --- 8. Important business rules: the transactional completion flow -------


async def test_confirm_completion_by_both_parties_records_connection(db_session: AsyncSession) -> None:
    """The flagship transactional test (Step 7): confirming completion from
    both sides atomically creates/increments the CONNECTION record tracking
    this worker/hiring-party pair's work history - two repository writes
    (CompletionVerification + Connection) committed together."""
    hiring_party_id = await _make_hiring_party(db_session)
    worker_id = await _make_worker(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)

    from app.repositories.job_match_repository import JobMatchRepository

    await JobMatchRepository(db_session).create(job_id=job_id, worker_id=worker_id, status="pending")
    await db_session.commit()

    verification_service = CompletionVerificationService(db_session)
    await verification_service.initiate_verification(job_id, hiring_party_id, method="qr")

    # Only the hiring party has confirmed so far - no connection yet.
    connection = await ConnectionRepository(db_session).get_by_pair(worker_id, hiring_party_id)
    assert connection is None

    await verification_service.confirm_completion(job_id, hiring_party_id)
    connection = await ConnectionRepository(db_session).get_by_pair(worker_id, hiring_party_id)
    assert connection is None  # still not complete - only one side confirmed

    final = await verification_service.confirm_completion(job_id, worker_id)
    assert final.worker_confirmed is True
    assert final.hiring_party_confirmed is True

    connection = await ConnectionRepository(db_session).get_by_pair(worker_id, hiring_party_id)
    assert connection is not None
    assert connection.jobs_completed == 1

    # A second completed job between the same pair increments, not resets.
    job_id_2 = await _make_job(db_session, hiring_party_id, category_id)
    await JobMatchRepository(db_session).create(job_id=job_id_2, worker_id=worker_id, status="pending")
    await db_session.commit()
    await verification_service.initiate_verification(job_id_2, hiring_party_id, method="qr")
    await verification_service.confirm_completion(job_id_2, hiring_party_id)
    await verification_service.confirm_completion(job_id_2, worker_id)

    connection = await ConnectionRepository(db_session).get_by_pair(worker_id, hiring_party_id)
    assert connection is not None
    assert connection.jobs_completed == 2


async def test_only_hiring_party_or_assigned_worker_can_confirm_completion(db_session: AsyncSession) -> None:
    hiring_party_id = await _make_hiring_party(db_session)
    category_id = await _make_category(db_session)
    job_id = await _make_job(db_session, hiring_party_id, category_id)
    unrelated_user_id = await _make_user(db_session)

    service = CompletionVerificationService(db_session)
    await service.initiate_verification(job_id, hiring_party_id, method="qr")

    with pytest.raises(UnauthorizedOperationError):
        await service.confirm_completion(job_id, unrelated_user_id)
