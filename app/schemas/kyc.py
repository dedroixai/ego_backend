"""API schemas for KYC.

Source: app/models/kyc.py, docs/database-design.md Section 1.11.

`user_id` is an ownership field - excluded from `KYCCreate`, to be set
server-side from the authenticated user. `status` is server-controlled
(defaults to 'pending', advanced via admin verification - `verifyKYC()` in
the class diagram) - no client-facing `KYCUpdate`.
"""

import uuid

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class KYCCreate(RequestModel):
    document_type: str = Field(min_length=1, max_length=50)


class KYCResponse(ORMModel):
    kyc_id: uuid.UUID
    user_id: uuid.UUID
    document_type: str
    status: str
