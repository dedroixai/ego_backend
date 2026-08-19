"""API schemas for DISPUTE.

Source: app/models/dispute.py, docs/database-design.md Section 1.15.

`raised_by` is an ownership field - excluded from `DisputeCreate`, to be set
server-side from the authenticated user. `status` is server-controlled
(defaults to 'open', managed via `manageDispute()` in the class diagram) -
no client-facing `DisputeUpdate`.

`DisputeCreate` is intentionally minimal (`job_id` only): `reason` exists in
the class diagram but was excluded from the SQLAlchemy model in the
previous task (docs/database-design.md Section 7.8, not yet confirmed), so
it isn't available here either - raising a dispute with no reason text is
awkward but accurately reflects the current data model. Worth revisiting
once that field is confirmed.

`job_id` stays optional here, matching the model's nullable `job_id`
(itself a direct, deliberately-not-silently-fixed implementation of the ER
diagram's literal `JOB |o--o| DISPUTE` notation - see
docs/database-design.md Section 7.14).
"""

import uuid

from app.schemas.base import ORMModel, RequestModel


class DisputeCreate(RequestModel):
    job_id: uuid.UUID | None = None


class DisputeResponse(ORMModel):
    dispute_id: uuid.UUID
    job_id: uuid.UUID | None
    raised_by: uuid.UUID
    status: str
