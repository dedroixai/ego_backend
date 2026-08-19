"""API schemas for COMPLETION_VERIFICATION.

Source: app/models/completion_verification.py, docs/database-design.md Section 1.12.

No `CompletionVerificationCreate` - this record is created as part of the
job lifecycle (mandatory 1:1 with JOB), not as a standalone client-initiated
resource.

`CompletionVerificationUpdate` models the worker/hiring-party confirmation
action (`confirmCompletion()`/`markJobComplete()` in the class diagram).

`qr_code` functions as a verification secret and is excluded from the
general `CompletionVerificationResponse` (Step 4/5: don't expose sensitive
fields unnecessarily). `CompletionVerificationInternal` is the
backend-only variant that includes it.
"""

import uuid

from app.schemas.base import ORMModel, RequestModel


class CompletionVerificationUpdate(RequestModel):
    worker_confirmed: bool | None = None
    hiring_party_confirmed: bool | None = None


class CompletionVerificationResponse(ORMModel):
    verification_id: uuid.UUID
    job_id: uuid.UUID
    method: str
    worker_confirmed: bool
    hiring_party_confirmed: bool


class CompletionVerificationInternal(CompletionVerificationResponse):
    """Internal/backend-only - includes the verification secret (`qr_code`)."""

    qr_code: str | None
