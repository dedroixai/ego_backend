"""API schemas for JOB_MATCH.

Source: app/models/job_match.py, docs/database-design.md Section 1.6.

No `JobMatchCreate` - match records are produced by matching logic (out of
scope: "do not implement matching logic"), not created directly by a client
request body.

`JobMatchUpdate` models the worker accepting/declining a match (`acceptJob`/
`declineJob` in the class diagram) - `status` is required here (this is a
narrow, single-purpose action schema, not a general partial-update).

`JobMatchWithWorkerResponse` (Task 19) - a Business reviewing an applicant
needs to see who they are, not just an opaque `worker_id`
(`JobMatchResponse` alone). Reuses the existing, previously-unwired
`WorkerSummary` schema (no bank details/sensitive fields) rather than
inventing a new one or a new standalone worker-lookup endpoint - the two
endpoints that use this response (`GET /jobs/{job_id}/applications`,
`GET /applications/{id}`) already establish "business owns this job" /
"worker or owning business" authorization before this field is populated,
so embedding it introduces no new authorization surface. Populated from
`JobMatch.worker` (`app/models/job_match.py`'s existing relationship,
eager-loaded in `JobMatchRepository` - see its module docstring).
"""

import uuid
from decimal import Decimal

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel
from app.schemas.worker import WorkerSummary


class JobMatchUpdate(RequestModel):
    status: str = Field(min_length=1, max_length=30)


class JobMatchResponse(ORMModel):
    match_id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID
    match_score: Decimal | None
    status: str


class JobMatchWithWorkerResponse(JobMatchResponse):
    worker: WorkerSummary
