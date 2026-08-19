"""Tests for the repository / data-access layer.

Runs against a disposable local test database (see conftest.py /
docs/repository-layer.md) - never against the app's Supabase DATABASE_URL.
Every test is skipped automatically if TEST_DATABASE_URL isn't configured.

Covers: create, retrieve, retrieve-nonexistent, update, delete,
relationship queries, unique constraint violations, foreign key constraint
behavior, and transaction rollback.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import HiringParty
from app.models.user import User
from app.models.worker import Worker
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.exceptions import (
    ConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
    RecordNotFoundError,
)
from app.repositories.job_category_repository import JobCategoryRepository
from app.repositories.job_repository import JobRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


async def _make_user(session: AsyncSession, *, role: str = "worker") -> User:
    return await UserRepository(session).create(phone=_phone(), language="en", role=role)


async def _make_worker(session: AsyncSession) -> Worker:
    user = await _make_user(session, role="worker")
    worker = Worker(user_id=user.user_id, name="Test Worker", skills=[], service_locations=[])
    session.add(worker)
    await session.flush()
    return worker


async def _make_hiring_party(session: AsyncSession) -> HiringParty:
    user = await _make_user(session, role="hiring_party")
    return await HiringPartyRepository(session).create(user_id=user.user_id, account_type="business")


# --- 1/2/3: create, retrieve, retrieve-nonexistent -------------------


async def test_create_user_populates_generated_fields(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    user = await repo.create(phone=_phone(), language="en", role="worker")

    assert user.user_id is not None
    assert user.kyc_status == "pending"  # model default


async def test_get_by_id_retrieves_created_record(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    created = await repo.create(phone=_phone(), language="en", role="worker")

    found = await repo.get_by_id(created.user_id)

    assert found is not None
    assert found.user_id == created.user_id


async def test_get_by_phone_unique_field_lookup(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    phone = _phone()
    created = await repo.create(phone=phone, language="en", role="worker")

    found = await repo.get_by_phone(phone)

    assert found is not None
    assert found.user_id == created.user_id


async def test_get_by_id_nonexistent_returns_none(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)

    found = await repo.get_by_id(uuid.uuid4())

    assert found is None


async def test_get_by_id_or_raise_raises_for_nonexistent(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)

    with pytest.raises(RecordNotFoundError):
        await repo.get_by_id_or_raise(uuid.uuid4())


# --- 4: update ----------------------------------------------------------


async def test_update_record_changes_field(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    user = await repo.create(phone=_phone(), language="en", role="worker")

    updated = await repo.update(user, language="hi")

    assert updated.language == "hi"
    found = await repo.get_by_id(user.user_id)
    assert found is not None
    assert found.language == "hi"


# --- 5: delete where applicable ------------------------------------------


async def test_delete_notification(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    repo = NotificationRepository(db_session)
    notification = await repo.create(user_id=user.user_id, type="job_match", message="Test notification", is_read=False)

    await repo.delete(notification)

    found = await repo.get_by_id(notification.notification_id)
    assert found is None


# --- 6: relationship-based queries ------------------------------------


async def test_list_jobs_by_hiring_party(db_session: AsyncSession) -> None:
    hiring_party = await _make_hiring_party(db_session)
    category = await JobCategoryRepository(db_session).create(name=f"Category {uuid.uuid4()}")
    job_repo = JobRepository(db_session)
    await job_repo.create(
        hiring_party_id=hiring_party.user_id,
        category_id=category.category_id,
        title="Fix leaking pipe",
        description="desc",
        budget=100,
        status="open",
        location="Mumbai",
    )
    other_hiring_party = await _make_hiring_party(db_session)
    await job_repo.create(
        hiring_party_id=other_hiring_party.user_id,
        category_id=category.category_id,
        title="Paint wall",
        description="desc",
        budget=200,
        status="open",
        location="Delhi",
    )

    jobs = await job_repo.list_by_hiring_party(hiring_party.user_id)

    assert len(jobs) == 1
    assert jobs[0].title == "Fix leaking pipe"


async def test_connection_get_by_pair(db_session: AsyncSession) -> None:
    worker = await _make_worker(db_session)
    hiring_party = await _make_hiring_party(db_session)
    connection_repo = ConnectionRepository(db_session)
    await connection_repo.create(worker_id=worker.user_id, hiring_party_id=hiring_party.user_id, jobs_completed=1)

    found = await connection_repo.get_by_pair(worker.user_id, hiring_party.user_id)

    assert found is not None
    assert found.jobs_completed == 1


# --- 7: unique constraint violation ------------------------------------


async def test_duplicate_phone_raises_duplicate_record_error(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    phone = _phone()
    await repo.create(phone=phone, language="en", role="worker")

    with pytest.raises(DuplicateRecordError):
        await repo.create(phone=phone, language="en", role="worker")

    await db_session.rollback()  # required after a failed flush before reusing the session


async def test_duplicate_connection_pair_raises_duplicate_record_error(db_session: AsyncSession) -> None:
    worker = await _make_worker(db_session)
    hiring_party = await _make_hiring_party(db_session)
    connection_repo = ConnectionRepository(db_session)
    await connection_repo.create(worker_id=worker.user_id, hiring_party_id=hiring_party.user_id, jobs_completed=0)

    with pytest.raises(DuplicateRecordError):
        await connection_repo.create(
            worker_id=worker.user_id, hiring_party_id=hiring_party.user_id, jobs_completed=0
        )

    await db_session.rollback()


# --- 8: foreign key constraint behavior --------------------------------


async def test_job_with_invalid_category_raises_foreign_key_violation(db_session: AsyncSession) -> None:
    hiring_party = await _make_hiring_party(db_session)
    job_repo = JobRepository(db_session)

    with pytest.raises(ForeignKeyViolationError):
        await job_repo.create(
            hiring_party_id=hiring_party.user_id,
            category_id=uuid.uuid4(),  # does not exist
            title="Fix leaking pipe",
            description="desc",
            budget=100,
            status="open",
            location="Mumbai",
        )

    await db_session.rollback()


async def test_deleting_referenced_category_is_blocked(db_session: AsyncSession) -> None:
    """Deleting a JobCategory that still has Jobs pointing at it is blocked.

    Surfaces as ConstraintViolationError (a NOT NULL violation), not
    ForeignKeyViolationError: SQLAlchemy's default relationship handling
    tries to null out `jobs.category_id` before issuing the delete (no
    `passive_deletes=True` configured on `JobCategory.jobs` - a models-layer
    detail out of scope to change here), and that nulling attempt itself
    fails since `category_id` is NOT NULL. Either way the delete is
    correctly rejected - see docs/repository-layer.md.
    """
    hiring_party = await _make_hiring_party(db_session)
    category_repo = JobCategoryRepository(db_session)
    category = await category_repo.create(name=f"Category {uuid.uuid4()}")
    await JobRepository(db_session).create(
        hiring_party_id=hiring_party.user_id,
        category_id=category.category_id,
        title="Fix leaking pipe",
        description="desc",
        budget=100,
        status="open",
        location="Mumbai",
    )

    with pytest.raises(ConstraintViolationError):
        await category_repo.delete(category)

    await db_session.rollback()


# --- 9: transaction rollback --------------------------------------------


async def test_transaction_rollback_discards_uncommitted_work(db_session: AsyncSession) -> None:
    """Repositories only flush, never commit - simulates a service catching
    a mid-operation failure and rolling back."""
    repo = UserRepository(db_session)
    user = await repo.create(phone=_phone(), language="en", role="worker")
    user_id = user.user_id

    await db_session.rollback()  # what a service would do on failure

    found = await repo.get_by_id(user_id)
    assert found is None


async def test_commit_persists_work_within_the_test_transaction(db_session: AsyncSession) -> None:
    """Contrast case for the rollback test above - commit keeps the data
    visible (still discarded at the very end by the fixture's outer
    transaction, not by anything this test does)."""
    repo = UserRepository(db_session)
    user = await repo.create(phone=_phone(), language="en", role="worker")
    user_id = user.user_id

    await db_session.commit()

    found = await repo.get_by_id(user_id)
    assert found is not None
