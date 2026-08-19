"""Tests for the Pydantic API schemas in app/schemas/.

Covers: valid input, missing required fields, invalid data types, invalid
values, optional fields, response serialization (from real SQLAlchemy ORM
instances, no DB needed), and sensitive fields not being exposed.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.completion_verification import CompletionVerification
from app.models.job import Job
from app.models.worker import Worker
from app.schemas.completion_verification import (
    CompletionVerificationInternal,
    CompletionVerificationResponse,
)
from app.schemas.dispute import DisputeCreate
from app.schemas.job import JobCreate, JobResponse
from app.schemas.job_match import JobMatchUpdate
from app.schemas.notification import NotificationUpdate
from app.schemas.rating import RatingCreate
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.withdrawal import WithdrawalCreate
from app.schemas.worker import WorkerCreate, WorkerResponse, WorkerWithBankDetails

# --- UserCreate -----------------------------------------------------------


def test_user_create_valid_input() -> None:
    user = UserCreate(phone="+91 9876543210", language="en", role="worker", dob=date(1995, 1, 1))
    assert user.phone == "+91 9876543210"
    assert user.role == "worker"


def test_user_create_optional_field_omitted() -> None:
    user = UserCreate(phone="+91 9876543210", language="en", role="worker")
    assert user.dob is None


def test_user_create_missing_required_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(language="en", role="worker")  # type: ignore[call-arg]
    assert any(e["loc"] == ("phone",) for e in exc_info.value.errors())


def test_user_create_invalid_phone_format() -> None:
    with pytest.raises(ValidationError):
        UserCreate(phone="not-a-phone-number!!", language="en", role="worker")


def test_user_create_invalid_dob_in_future() -> None:
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        UserCreate(phone="+919876543210", language="en", role="worker", dob=future)


def test_user_update_rejects_ownership_and_identity_fields() -> None:
    """A client must not be able to sneak `phone`, `role`, or `user_id` into
    an update - RequestModel's extra="forbid" should reject them outright."""
    with pytest.raises(ValidationError):
        UserUpdate(phone="+919999999999")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        UserUpdate(role="admin")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        UserUpdate(user_id=str(uuid.uuid4()))  # type: ignore[call-arg]


# --- WorkerCreate / WorkerResponse -----------------------------------------


def test_worker_create_valid_input() -> None:
    worker = WorkerCreate(
        name="Jane Doe",
        skills=["plumbing", "electrical"],
        experience=5,
        expected_wage=Decimal("500.00"),
        availability="full-time",
        service_locations=["Mumbai"],
        bank_details="acct-1234",
    )
    assert worker.skills == ["plumbing", "electrical"]


def test_worker_create_only_required_field() -> None:
    worker = WorkerCreate(name="Jane Doe")
    assert worker.skills == []
    assert worker.service_locations == []
    assert worker.experience is None


def test_worker_create_negative_experience_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkerCreate(name="Jane Doe", experience=-1)


def test_worker_create_negative_wage_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkerCreate(name="Jane Doe", expected_wage=Decimal("-1"))


def test_worker_create_invalid_experience_type() -> None:
    with pytest.raises(ValidationError):
        WorkerCreate(name="Jane Doe", experience="five")  # type: ignore[arg-type]


def test_worker_create_rejects_server_controlled_fields() -> None:
    """A client must not be able to self-assign rating/verified_badge/user_id."""
    with pytest.raises(ValidationError):
        WorkerCreate(name="Jane Doe", rating="5.0")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        WorkerCreate(name="Jane Doe", verified_badge=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        WorkerCreate(name="Jane Doe", user_id=str(uuid.uuid4()))  # type: ignore[call-arg]


def test_worker_response_serializes_from_orm_instance_without_bank_details() -> None:
    """Response schemas must build from a real SQLAlchemy instance (no DB
    needed - plain column attributes only) and must NOT expose bank_details."""
    worker = Worker(
        user_id=uuid.uuid4(),
        name="Jane Doe",
        skills=["plumbing"],
        experience=5,
        expected_wage=Decimal("500.00"),
        availability="full-time",
        rating=Decimal("4.50"),
        service_locations=["Mumbai"],
        bank_details="super-secret-account-number",
        verified_badge=True,
    )

    response = WorkerResponse.model_validate(worker)

    assert response.name == "Jane Doe"
    assert response.rating == Decimal("4.50")
    assert "bank_details" not in response.model_dump()
    assert not hasattr(response, "bank_details")


def test_worker_with_bank_details_includes_it_for_internal_use() -> None:
    worker = Worker(
        user_id=uuid.uuid4(),
        name="Jane Doe",
        skills=[],
        service_locations=[],
        bank_details="super-secret-account-number",
        verified_badge=False,
    )

    internal = WorkerWithBankDetails.model_validate(worker)

    assert internal.bank_details == "super-secret-account-number"


# --- JobCreate / JobResponse -----------------------------------------------


def test_job_create_valid_input() -> None:
    job = JobCreate(
        category_id=uuid.uuid4(),
        title="Fix leaking pipe",
        description="Kitchen sink is leaking, needs urgent repair.",
        budget=Decimal("1500.00"),
        duration="1 day",
        location="Mumbai, Maharashtra",
    )
    assert job.title == "Fix leaking pipe"


def test_job_create_missing_required_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        JobCreate(
            category_id=uuid.uuid4(),
            description="desc",
            budget=Decimal("100"),
            location="Mumbai",
        )  # type: ignore[call-arg]
    assert any(e["loc"] == ("title",) for e in exc_info.value.errors())


def test_job_create_negative_budget_rejected() -> None:
    with pytest.raises(ValidationError):
        JobCreate(
            category_id=uuid.uuid4(),
            title="Fix leaking pipe",
            description="desc",
            budget=Decimal("-1"),
            location="Mumbai",
        )


def test_job_create_invalid_budget_type() -> None:
    with pytest.raises(ValidationError):
        JobCreate(
            category_id=uuid.uuid4(),
            title="Fix leaking pipe",
            description="desc",
            budget="not-a-number",  # type: ignore[arg-type]
            location="Mumbai",
        )


def test_job_create_rejects_ownership_and_internal_fields() -> None:
    """A client must not be able to set hiring_party_id (ownership) or
    status (internal lifecycle field) when creating a job."""
    base_kwargs = dict(
        category_id=uuid.uuid4(),
        title="Fix leaking pipe",
        description="desc",
        budget=Decimal("100"),
        location="Mumbai",
    )
    with pytest.raises(ValidationError):
        JobCreate(**base_kwargs, hiring_party_id=str(uuid.uuid4()))  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        JobCreate(**base_kwargs, status="open")  # type: ignore[call-arg]


def test_job_response_serializes_from_orm_instance() -> None:
    job = Job(
        job_id=uuid.uuid4(),
        hiring_party_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        title="Fix leaking pipe",
        description="desc",
        budget=Decimal("1500.00"),
        duration="1 day",
        status="open",
        location="Mumbai",
        created_at=datetime.now(timezone.utc),
    )

    response = JobResponse.model_validate(job)

    assert response.title == "Fix leaking pipe"
    assert response.status == "open"
    assert response.budget == Decimal("1500.00")


# --- RatingCreate ------------------------------------------------------


def test_rating_create_valid_input() -> None:
    rating = RatingCreate(job_id=uuid.uuid4(), to_user_id=uuid.uuid4(), score=5, comment="Great work")
    assert rating.score == 5


def test_rating_create_optional_comment_omitted() -> None:
    rating = RatingCreate(job_id=uuid.uuid4(), to_user_id=uuid.uuid4(), score=3)
    assert rating.comment is None


def test_rating_create_invalid_score_type() -> None:
    with pytest.raises(ValidationError):
        RatingCreate(job_id=uuid.uuid4(), to_user_id=uuid.uuid4(), score="five")  # type: ignore[arg-type]


def test_rating_create_score_beyond_smallint_range_rejected() -> None:
    """No business-defined range exists (deliberately unconstrained - see
    docs/database-design.md 7.10), but the underlying SMALLINT column can't
    store values outside its own storage range."""
    with pytest.raises(ValidationError):
        RatingCreate(job_id=uuid.uuid4(), to_user_id=uuid.uuid4(), score=32768)


def test_rating_create_rejects_ownership_field() -> None:
    with pytest.raises(ValidationError):
        RatingCreate(
            job_id=uuid.uuid4(),
            to_user_id=uuid.uuid4(),
            score=5,
            from_user_id=str(uuid.uuid4()),  # type: ignore[call-arg]
        )


# --- CompletionVerification: sensitive field exclusion ----------------------


def test_completion_verification_response_excludes_qr_code() -> None:
    verification = CompletionVerification(
        verification_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        method="qr",
        qr_code="super-secret-qr-payload",
        worker_confirmed=True,
        hiring_party_confirmed=False,
    )

    response = CompletionVerificationResponse.model_validate(verification)

    assert "qr_code" not in response.model_dump()
    assert not hasattr(response, "qr_code")


def test_completion_verification_internal_includes_qr_code() -> None:
    verification = CompletionVerification(
        verification_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        method="qr",
        qr_code="super-secret-qr-payload",
        worker_confirmed=True,
        hiring_party_confirmed=False,
    )

    internal = CompletionVerificationInternal.model_validate(verification)

    assert internal.qr_code == "super-secret-qr-payload"


# --- Narrow action schemas: required fields ---------------------------


def test_job_match_update_requires_status() -> None:
    with pytest.raises(ValidationError):
        JobMatchUpdate()  # type: ignore[call-arg]
    update = JobMatchUpdate(status="accepted")
    assert update.status == "accepted"


def test_notification_update_requires_is_read() -> None:
    with pytest.raises(ValidationError):
        NotificationUpdate()  # type: ignore[call-arg]
    update = NotificationUpdate(is_read=True)
    assert update.is_read is True


# --- WithdrawalCreate ----------------------------------------------------


def test_withdrawal_create_valid_amount() -> None:
    withdrawal = WithdrawalCreate(amount=Decimal("100.00"))
    assert withdrawal.amount == Decimal("100.00")


def test_withdrawal_create_zero_amount_rejected() -> None:
    with pytest.raises(ValidationError):
        WithdrawalCreate(amount=Decimal("0"))


def test_withdrawal_create_negative_amount_rejected() -> None:
    with pytest.raises(ValidationError):
        WithdrawalCreate(amount=Decimal("-50"))


# --- DisputeCreate (optional job_id, matching the model's nullable FK) --


def test_dispute_create_with_job_id() -> None:
    dispute = DisputeCreate(job_id=uuid.uuid4())
    assert dispute.job_id is not None


def test_dispute_create_without_job_id() -> None:
    dispute = DisputeCreate()
    assert dispute.job_id is None


def test_dispute_create_rejects_ownership_and_status_fields() -> None:
    with pytest.raises(ValidationError):
        DisputeCreate(raised_by=str(uuid.uuid4()))  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        DisputeCreate(status="closed")  # type: ignore[call-arg]
