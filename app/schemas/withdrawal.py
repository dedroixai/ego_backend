"""API schemas for WITHDRAWAL.

Source: app/models/withdrawal.py, docs/database-design.md Section 1.9.

`worker_id` is an ownership field - excluded from `WithdrawalCreate`, to be
set server-side from the authenticated worker. `status`/`requested_at` are
server-controlled (initial status set server-side; further transitions are
internal processing, not client update) - no `WithdrawalUpdate`.

`amount` must be `> 0`, mirroring the DB `CHECK` constraint
(`ck_withdrawals_amount_positive`) exactly.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import ORMModel, RequestModel


class WithdrawalCreate(RequestModel):
    amount: Decimal = Field(gt=0)


class WithdrawalResponse(ORMModel):
    withdrawal_id: uuid.UUID
    worker_id: uuid.UUID
    amount: Decimal
    status: str
    requested_at: datetime
