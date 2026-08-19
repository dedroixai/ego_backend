"""Pydantic API schemas - the API data contract layer.

These are separate from `app/models/` (the SQLAlchemy database layer) by
design: SQLAlchemy models are never returned directly from an endpoint.

    Database Model -> Service -> Pydantic Response Schema -> FastAPI -> Flutter
    Flutter -> Pydantic Request Schema -> Service -> SQLAlchemy Model -> PostgreSQL
"""

from app.schemas.base import ORMModel, RequestModel
from app.schemas.business import (
    HiringPartyCreate,
    HiringPartyResponse,
    HiringPartySummary,
    HiringPartyUpdate,
)
from app.schemas.completion_verification import (
    CompletionVerificationInternal,
    CompletionVerificationResponse,
    CompletionVerificationUpdate,
)
from app.schemas.connection import ConnectionResponse
from app.schemas.device_token import DeviceTokenRegister, DeviceTokenResponse
from app.schemas.dispute import DisputeCreate, DisputeResponse
from app.schemas.job import JobCreate, JobListResponse, JobPatchRequest, JobResponse, JobUpdate
from app.schemas.job_category import JobCategoryCreate, JobCategoryResponse, JobCategoryUpdate
from app.schemas.job_match import JobMatchResponse, JobMatchUpdate, JobMatchWithWorkerResponse
from app.schemas.kyc import KYCCreate, KYCResponse
from app.schemas.message import ConversationSummary, MessageCreate, MessageResponse
from app.schemas.notification import NotificationResponse, NotificationUpdate
from app.schemas.payment import PaymentResponse
from app.schemas.rating import RatingCreate, RatingResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.withdrawal import WithdrawalCreate, WithdrawalResponse
from app.schemas.worker import (
    WorkerCreate,
    WorkerListResponse,
    WorkerResponse,
    WorkerSummary,
    WorkerUpdate,
    WorkerWithBankDetails,
)

__all__ = [
    "ORMModel",
    "RequestModel",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "WorkerCreate",
    "WorkerUpdate",
    "WorkerResponse",
    "WorkerSummary",
    "WorkerListResponse",
    "WorkerWithBankDetails",
    "HiringPartyCreate",
    "HiringPartyUpdate",
    "HiringPartyResponse",
    "HiringPartySummary",
    "JobCategoryCreate",
    "JobCategoryUpdate",
    "JobCategoryResponse",
    "JobCreate",
    "JobUpdate",
    "JobPatchRequest",
    "JobResponse",
    "JobListResponse",
    "JobMatchUpdate",
    "JobMatchResponse",
    "JobMatchWithWorkerResponse",
    "ConversationSummary",
    "MessageCreate",
    "MessageResponse",
    "PaymentResponse",
    "WithdrawalCreate",
    "WithdrawalResponse",
    "RatingCreate",
    "RatingResponse",
    "KYCCreate",
    "KYCResponse",
    "CompletionVerificationUpdate",
    "CompletionVerificationResponse",
    "CompletionVerificationInternal",
    "ConnectionResponse",
    "NotificationUpdate",
    "NotificationResponse",
    "DeviceTokenRegister",
    "DeviceTokenResponse",
    "DisputeCreate",
    "DisputeResponse",
]
