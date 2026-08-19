"""API schemas for CONNECTION.

Source: app/models/connection.py, docs/database-design.md Section 1.13.

Response-only - this is a fully system-derived record (worker/hiring-party
work history, incremented as jobs complete), never client-created or
client-updated.
"""

import uuid

from app.schemas.base import ORMModel


class ConnectionResponse(ORMModel):
    connection_id: uuid.UUID
    worker_id: uuid.UUID
    hiring_party_id: uuid.UUID
    jobs_completed: int
