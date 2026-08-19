"""ORM models.

Every model must be imported here so `Base.metadata` is fully populated -
this is what lets Alembic (configured in a later task) discover every table
for autogeneration, and what lets SQLAlchemy resolve the string-based
relationship() targets used across model modules.
"""

from app.db.base import Base
from app.models.business import HiringParty
from app.models.completion_verification import CompletionVerification
from app.models.connection import Connection
from app.models.device_token import DeviceToken
from app.models.dispute import Dispute
from app.models.job import Job
from app.models.job_category import JobCategory
from app.models.job_match import JobMatch
from app.models.kyc import KYC
from app.models.message import Message
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.rating import Rating
from app.models.user import User
from app.models.withdrawal import Withdrawal
from app.models.worker import Worker

__all__ = [
    "Base",
    "CompletionVerification",
    "Connection",
    "DeviceToken",
    "Dispute",
    "HiringParty",
    "Job",
    "JobCategory",
    "JobMatch",
    "KYC",
    "Message",
    "Notification",
    "Payment",
    "Rating",
    "User",
    "Withdrawal",
    "Worker",
]
