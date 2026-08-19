"""API schemas for PAYMENT.

Source: app/models/payment.py, docs/database-design.md Section 1.8.

No `PaymentCreate`/`PaymentUpdate` - nothing in either diagram describes a
client-facing payment-creation flow, and payment/escrow fields are
exactly the kind of "internal status fields" Step 4 says clients must not
be able to set or change directly. Payment records are expected to be
created and mutated by dedicated financial service operations (e.g.
`releasePayment()` in the class diagram), which are business logic and out
of scope for this task. Response-only for now.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.base import ORMModel


class PaymentResponse(ORMModel):
    payment_id: uuid.UUID
    job_id: uuid.UUID
    amount: Decimal
    platform_fee: Decimal | None
    escrow_status: str
    status: str
    release_date: datetime | None
