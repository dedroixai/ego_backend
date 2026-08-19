"""Service / business-logic layer.

Coordinates repositories, enforces ownership/business rules, and owns the
transaction boundary (commit/rollback) - see docs/service-layer.md.
"""

from app.services.base import BaseService
from app.services.business_service import HiringPartyService
from app.services.completion_verification_service import CompletionVerificationService
from app.services.dispute_service import DisputeService
from app.services.exceptions import (
    BusinessRuleViolationError,
    DuplicateOperationError,
    InvalidStateTransitionError,
    ResourceNotFoundError,
    ServiceError,
    UnauthorizedOperationError,
)
from app.services.job_category_service import JobCategoryService
from app.services.job_match_service import JobMatchService
from app.services.job_service import JobService
from app.services.kyc_service import KYCService
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService
from app.services.rating_service import RatingService
from app.services.user_service import UserService
from app.services.withdrawal_service import WithdrawalService
from app.services.worker_service import WorkerService

__all__ = [
    "BaseService",
    "ServiceError",
    "ResourceNotFoundError",
    "UnauthorizedOperationError",
    "InvalidStateTransitionError",
    "DuplicateOperationError",
    "BusinessRuleViolationError",
    "UserService",
    "WorkerService",
    "HiringPartyService",
    "JobCategoryService",
    "JobService",
    "JobMatchService",
    "MessageService",
    "WithdrawalService",
    "RatingService",
    "KYCService",
    "CompletionVerificationService",
    "NotificationService",
    "DisputeService",
]
