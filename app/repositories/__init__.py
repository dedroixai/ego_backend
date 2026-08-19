"""Repository / data-access layer.

Repositories deal with Application <-> Database only - see
docs/repository-layer.md for the full design (responsibilities,
transaction strategy, error handling).
"""

from app.repositories.base import BaseRepository
from app.repositories.business_repository import HiringPartyRepository
from app.repositories.completion_verification_repository import CompletionVerificationRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.dispute_repository import DisputeRepository
from app.repositories.exceptions import (
    ConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
    RecordNotFoundError,
    RepositoryError,
)
from app.repositories.job_category_repository import JobCategoryRepository
from app.repositories.job_match_repository import JobMatchRepository
from app.repositories.job_repository import JobRepository
from app.repositories.kyc_repository import KYCRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.rating_repository import RatingRepository
from app.repositories.user_repository import UserRepository
from app.repositories.withdrawal_repository import WithdrawalRepository
from app.repositories.worker_repository import WorkerRepository

__all__ = [
    "BaseRepository",
    "RepositoryError",
    "RecordNotFoundError",
    "DuplicateRecordError",
    "ForeignKeyViolationError",
    "ConstraintViolationError",
    "UserRepository",
    "WorkerRepository",
    "HiringPartyRepository",
    "JobCategoryRepository",
    "JobRepository",
    "JobMatchRepository",
    "MessageRepository",
    "PaymentRepository",
    "WithdrawalRepository",
    "RatingRepository",
    "KYCRepository",
    "CompletionVerificationRepository",
    "ConnectionRepository",
    "NotificationRepository",
    "DisputeRepository",
]
